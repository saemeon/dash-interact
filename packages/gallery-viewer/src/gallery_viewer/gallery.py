"""Gallery — configurable Dash dashboard for browsing versioned scripts.

Supports multiple named plots, each backed by its own ``StorageBackend``.

Usage::

    from gallery_viewer import Gallery, FileSystemBackend

    # Single plot
    gallery = Gallery(backend=FileSystemBackend("./my_project"))

    # Multiple plots (auto-discovered from subdirectories)
    gallery = Gallery(backends=FileSystemBackend.discover("./all_plots"))

    # From a config file (recommended for multi-plot galleries)
    gallery = Gallery.from_config("gallery.json")

    gallery.run()
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Callable

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html, dash_table, ctx

from gallery_viewer._types import RunResult, ScriptSections
from gallery_viewer.backend import StorageBackend, FileSystemBackend
from gallery_viewer.params import detect_params
from gallery_viewer.config import (
    add_plot_to_config,
    backends_from_config,
    load_config,
    save_config,
)

# ---------------------------------------------------------------------------
# Optional: dash-ace for syntax-highlighted editor
# ---------------------------------------------------------------------------

try:
    import dash_ace  # noqa: F401
    _HAS_ACE = True
except ImportError:
    _HAS_ACE = False


# ---------------------------------------------------------------------------
# Style constants
# ---------------------------------------------------------------------------

_MONOSPACE = {"fontFamily": "monospace", "fontSize": "13px"}
_CONSOLE_STYLE = {
    **_MONOSPACE,
    "backgroundColor": "#1a1a1a",
    "color": "#d4d4d4",
    "padding": "10px",
    "borderRadius": "4px",
    "minHeight": "80px",
    "whiteSpace": "pre-wrap",
    "overflowY": "auto",
    "maxHeight": "200px",
}
_SECTION_LABEL = {
    "color": "#888",
    "fontSize": "11px",
    "textTransform": "uppercase",
    "letterSpacing": "0.06em",
    "marginBottom": "2px",
    "marginTop": "10px",
}

def _editor_style(height: str = "200px") -> dict:
    return {
        **_MONOSPACE,
        "width": "100%",
        "height": height,
        "backgroundColor": "#1e1e1e",
        "color": "#d4d4d4",
        "border": "1px solid #444",
        "borderRadius": "4px",
        "padding": "10px",
        "resize": "vertical",
    }


def _make_editor(id: str, height: str = "200px") -> Any:
    """Create a code editor — DashAceEditor if available, else dcc.Textarea."""
    if _HAS_ACE:
        return dash_ace.DashAceEditor(
            id=id,
            value="",
            mode="python",
            theme="monokai",
            fontSize=13,
            style={"width": "100%", "height": height},
            enableBasicAutocompletion=False,
            enableLiveAutocompletion=False,
        )
    return dcc.Textarea(id=id, style=_editor_style(height))


# ---------------------------------------------------------------------------
# Gallery
# ---------------------------------------------------------------------------

class Gallery:
    """Configurable gallery dashboard with multi-plot support.

    Parameters
    ----------
    backend :
        Single storage backend (for one-plot galleries).
    backends :
        Dict of ``{plot_name: StorageBackend}`` for multi-plot galleries.
        Mutually exclusive with ``backend``.
    title :
        Dashboard title shown in the header.
    theme :
        A ``dbc.themes`` constant.  Defaults to ``SLATE`` (dark).
    export_fn :
        Optional ``(bytes) -> bytes`` that post-processes a plot image.
    extra_controls :
        Optional Dash component(s) inserted below the dropdowns.
    """

    def __init__(
        self,
        backend: StorageBackend | None = None,
        backends: dict[str, StorageBackend] | None = None,
        title: str = "Gallery Viewer",
        theme: Any = None,
        export_fn: Callable[[bytes], bytes] | None = None,
        extra_controls: Any = None,
        config_path: str | Path | None = None,
    ):
        if backends is not None:
            self.backends = backends
        elif backend is not None:
            self.backends = {"default": backend}
        else:
            self.backends = {"default": FileSystemBackend(".")}

        self.title = title
        self._config_path = Path(config_path) if config_path else None
        self.theme = theme or dbc.themes.SLATE
        self.export_fn = export_fn
        self.extra_controls = extra_controls
        self._multi = len(self.backends) > 1

        self._app: dash.Dash | None = None

    @classmethod
    def from_config(
        cls,
        config_path: str | Path,
        export_fn: Callable[[bytes], bytes] | None = None,
        extra_controls: Any = None,
        **backend_kwargs,
    ) -> "Gallery":
        """Create a Gallery from a ``gallery.json`` config file.

        Parameters
        ----------
        config_path :
            Path to the JSON config file.
        export_fn :
            Optional post-processing function for exports.
        **backend_kwargs :
            Extra kwargs forwarded to each ``FileSystemBackend()``.
        """
        config_path = Path(config_path)
        config = load_config(config_path)
        base_dir = config_path.parent
        backends = backends_from_config(config, base_dir=base_dir, **backend_kwargs)

        if not backends:
            # Empty config — start with no plots; user adds via dashboard
            pass

        return cls(
            backends=backends or {},
            title=config.get("title", "Gallery Viewer"),
            export_fn=export_fn,
            extra_controls=extra_controls,
            config_path=config_path,
        )

    @property
    def app(self) -> dash.Dash:
        if self._app is None:
            self._app = self._build_app()
        return self._app

    def run(self, debug: bool = False, host: str = "127.0.0.1", port: int = 8050, **kwargs):
        self.app.run(debug=debug, host=host, port=port, **kwargs)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_app(self) -> dash.Dash:
        app = dash.Dash(
            __name__,
            external_stylesheets=[self.theme],
            title=self.title,
        )
        app.layout = self._layout()
        self._register_callbacks(app)
        return app

    def _layout(self) -> dbc.Container:
        extra = self.extra_controls or html.Div()
        plot_names = list(self.backends.keys())

        export_btn = []
        if self.export_fn is not None:
            export_btn = [
                dbc.Button("Export", id="export-btn", color="warning", size="sm",
                           n_clicks=0, style={"marginLeft": "8px"}),
                dcc.Download(id="export-download"),
            ]

        # "Add Plot" button (only when config file is used)
        add_plot_btn = []
        if self._config_path:
            add_plot_btn = [
                dbc.Button(
                    "+ Add Plot", id="gv-add-plot-btn", color="secondary",
                    size="sm", n_clicks=0,
                    style={"width": "100%", "marginTop": "8px", "marginBottom": "8px"},
                ),
                dbc.Modal([
                    dbc.ModalHeader("Add New Plot"),
                    dbc.ModalBody([
                        dbc.Label("Plot name"),
                        dbc.Input(id="gv-add-plot-name", type="text", placeholder="e.g. revenue_chart"),
                        dbc.Label("Description", class_name="mt-2"),
                        dbc.Input(id="gv-add-plot-desc", type="text", placeholder="Optional description"),
                    ]),
                    dbc.ModalFooter([
                        dbc.Button("Create", id="gv-add-plot-submit", color="primary", size="sm"),
                        dbc.Button("Cancel", id="gv-add-plot-cancel", color="secondary", size="sm"),
                    ]),
                ], id="gv-add-plot-modal", is_open=False),
                html.Div(id="gv-add-plot-feedback", style={"fontSize": "12px", "color": "#aaa"}),
            ]

        return dbc.Container(
            fluid=True,
            style={"padding": "16px"},
            children=[
                dbc.Row(dbc.Col(
                    html.H3(self.title, style={"color": "#e0e0e0", "marginBottom": "12px"}),
                )),
                dbc.Row([
                    # ── GALLERY SIDEBAR ───────────────────────────────
                    dbc.Col(width=2, children=[
                        html.Label("Plots", style={
                            "color": "#aaa", "fontSize": "12px", "textTransform": "uppercase",
                            "letterSpacing": "0.06em", "marginBottom": "8px",
                        }),
                        dcc.Input(
                            id="gv-search", type="text", placeholder="Filter...",
                            debounce=False,
                            style={
                                "width": "100%", "marginBottom": "8px",
                                "backgroundColor": "#3a3a3a", "color": "#d4d4d4",
                                "border": "1px solid #555", "borderRadius": "4px",
                                "padding": "4px 8px", "fontSize": "12px",
                            },
                        ),
                        html.Div(
                            id="gv-gallery-sidebar",
                            style={
                                "overflowY": "auto", "maxHeight": "calc(100vh - 220px)",
                                "paddingRight": "4px",
                            },
                        ),
                        *add_plot_btn,
                        # Hidden store for selected plot name
                        dcc.Store(id="gv-plot-select", data=plot_names[0] if plot_names else None),
                        dcc.Store(id="gv-gallery-items"),
                    ]),

                    # ── EDITOR ────────────────────────────────────────
                    dbc.Col(width=4, children=[
                        dbc.Row([
                            dbc.Col(width=5, children=[
                                html.Label("Date", style={"color": "#aaa", "fontSize": "12px"}),
                                dcc.Dropdown(id="gv-date", placeholder="Select date...",
                                             clearable=False, style={"marginBottom": "6px"}),
                            ]),
                            dbc.Col(width=5, children=[
                                html.Label("Version", style={"color": "#aaa", "fontSize": "12px"}),
                                dcc.Dropdown(id="gv-version", clearable=False,
                                             style={"marginBottom": "6px"}),
                            ]),
                            dbc.Col(width=2, children=[
                                html.Label("\u00a0", style={"fontSize": "12px"}),
                                dbc.Button(
                                    "\u21bb", id="gv-refresh-btn",
                                    color="secondary", size="sm", n_clicks=0,
                                    style={"width": "100%", "fontSize": "16px", "padding": "4px"},
                                    title="Refresh dates & versions",
                                ),
                            ]),
                        ]),
                        extra,
                        html.Div(id="gv-param-fields", style={"marginBottom": "4px"}),
                        html.Div("Script", style=_SECTION_LABEL),
                        _make_editor("gv-editor-script", "500px"),
                        dbc.Row([
                            dbc.Col(dbc.Button(
                                [dbc.Spinner(size="sm", spinner_style={"marginRight": "6px"},
                                             id="gv-run-spinner"), "RUN"],
                                id="gv-run-btn", color="success", size="sm",
                                n_clicks=0, style={"width": "100%"},
                            ), width=6),
                            dbc.Col(dbc.Button(
                                "Save Version", id="gv-save-btn", color="primary",
                                size="sm", n_clicks=0, style={"width": "100%"},
                            ), width=6),
                        ], style={"marginTop": "8px", "marginBottom": "6px"}),
                        html.Label("Console", style={"color": "#aaa", "fontSize": "12px"}),
                        html.Div(id="gv-console", style=_CONSOLE_STYLE),
                        dcc.ConfirmDialog(id="gv-confirm-save",
                                          message="Save as a new version? The script and plot will be saved to disk."),
                    ]),

                    # ── PREVIEW ───────────────────────────────────────
                    dbc.Col(width=6, children=[
                        html.Div([
                            html.Label("Plot", style={"color": "#aaa", "fontSize": "12px"}),
                            *export_btn,
                        ], style={"display": "flex", "alignItems": "center", "marginBottom": "4px"}),
                        dcc.Loading(type="circle", color="#aaa", children=html.Div(
                            id="gv-plot-panel",
                            style={
                                "backgroundColor": "#2a2a2a", "borderRadius": "4px",
                                "padding": "8px", "minHeight": "300px",
                                "display": "flex", "alignItems": "center",
                                "justifyContent": "center", "marginBottom": "12px",
                            },
                            children=_no_plot(),
                        )),
                        html.Label("Data (first 50 rows)", style={"color": "#aaa", "fontSize": "12px"}),
                        html.Div(id="gv-data-panel",
                                 style={"overflowX": "auto", "maxHeight": "300px", "overflowY": "auto"},
                                 children=_no_data()),
                    ]),
                ]),
                dcc.Store(id="gv-plot-bytes-store"),
            ],
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_backend(self, plot_name: str | None) -> StorageBackend:
        """Resolve plot name to backend, fallback to first."""
        if plot_name and plot_name in self.backends:
            return self.backends[plot_name]
        return next(iter(self.backends.values()))

    def _build_plot_names(self) -> list[str]:
        """Return current plot names."""
        return list(self.backends.keys())

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _register_callbacks(self, app: dash.Dash):

        # -- Render sidebar nav list --
        @app.callback(
            Output("gv-gallery-sidebar", "children"),
            Input("gv-gallery-items", "data"),
            Input("gv-search", "value"),
        )
        def render_sidebar(_, search):
            names = self._build_plot_names()
            if search and search.strip():
                q = search.lower()
                names = [n for n in names if q in n.lower()]
            if not names:
                return html.Span("No plots", style={"color": "#666"})
            children = []
            for i, name in enumerate(names):
                desc = ""
                if self._config_path:
                    config = load_config(self._config_path)
                    desc = config.get("plots", {}).get(name, {}).get("description", "")
                children.append(
                    html.Div(
                        [
                            html.Div(name.replace("_", " ").title(),
                                     style={"fontWeight": "bold", "fontSize": "13px", "color": "#e0e0e0"}),
                            html.Div(desc, style={"fontSize": "11px", "color": "#888"}) if desc else None,
                        ],
                        id={"type": "gv-nav-item", "index": name},
                        n_clicks=0,
                        style={
                            "padding": "8px 10px", "marginBottom": "4px",
                            "borderRadius": "4px", "cursor": "pointer",
                            "backgroundColor": "#2a2a2a",
                            "borderLeft": "3px solid transparent",
                        },
                    )
                )
            return children

        # -- Click nav item → select plot, load its dates --
        @app.callback(
            Output("gv-plot-select", "data", allow_duplicate=True),
            Output("gv-date", "options"),
            Output("gv-date", "value"),
            Input({"type": "gv-nav-item", "index": dash.ALL}, "n_clicks"),
            prevent_initial_call=True,
        )
        def nav_click(n_clicks_list):
            if not any(n_clicks_list):
                return dash.no_update, dash.no_update, dash.no_update
            triggered = ctx.triggered_id
            if triggered is None:
                return dash.no_update, dash.no_update, dash.no_update
            plot_name = triggered["index"]
            backend = self._get_backend(plot_name)
            dates = backend.list_dates()
            opts = [{"label": d, "value": d} for d in dates]
            return plot_name, opts, (dates[0] if dates else None)

        # -- Also load dates on initial plot select --
        @app.callback(
            Output("gv-date", "options", allow_duplicate=True),
            Output("gv-date", "value", allow_duplicate=True),
            Input("gv-plot-select", "data"),
            prevent_initial_call=True,
        )
        def init_dates_for_plot(plot_name):
            if not plot_name:
                return [], None
            backend = self._get_backend(plot_name)
            dates = backend.list_dates()
            opts = [{"label": d, "value": d} for d in dates]
            return opts, (dates[0] if dates else None)

        # -- Refresh button → reload dates + versions for current plot --
        @app.callback(
            Output("gv-date", "options", allow_duplicate=True),
            Output("gv-date", "value", allow_duplicate=True),
            Output("gv-version", "options", allow_duplicate=True),
            Output("gv-version", "value", allow_duplicate=True),
            Input("gv-refresh-btn", "n_clicks"),
            State("gv-plot-select", "data"),
            State("gv-date", "value"),
            prevent_initial_call=True,
        )
        def refresh_dates(n_clicks, plot_name, current_date):
            if not plot_name:
                return [], None, [], None
            backend = self._get_backend(plot_name)
            dates = backend.list_dates()
            date_opts = [{"label": d, "value": d} for d in dates]
            # Keep current date if it still exists, otherwise pick newest
            date_val = current_date if current_date in dates else (dates[0] if dates else None)
            versions = backend.list_versions(date_val) if date_val else []
            ver_opts = [{"label": f"v{v}", "value": v} for v in versions]
            ver_val = versions[-1] if versions else None
            return date_opts, date_val, ver_opts, ver_val

        # -- Update version dropdown when date changes --
        @app.callback(
            Output("gv-version", "options"),
            Output("gv-version", "value", allow_duplicate=True),
            Input("gv-date", "value"),
            State("gv-plot-select", "data"),
            prevent_initial_call=True,
        )
        def update_versions(date, plot_name):
            if not date:
                return [], None
            backend = self._get_backend(plot_name)
            versions = backend.list_versions(date)
            opts = [{"label": f"v{v}", "value": v} for v in versions]
            return opts, versions[-1] if versions else None

        # -- Load script + data + plot + detect params --
        @app.callback(
            Output("gv-editor-script", "value"),
            Output("gv-param-fields", "children"),
            Output("gv-data-panel", "children"),
            Output("gv-plot-panel", "children"),
            Output("gv-plot-bytes-store", "data"),
            Input("gv-date", "value"),
            Input("gv-version", "value"),
            State("gv-plot-select", "data"),
        )
        def load_version(date, version, plot_name):
            if not date or not version:
                return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
            backend = self._get_backend(plot_name)
            version = str(version)
            sections = backend.load_script(date, str(version))
            script_text = sections.to_text()

            # Detect configurable params from the Configurator section
            param_fields = _build_param_fields(sections.configurator)

            data_children = _data_table(backend.load_data(date))
            plot_bytes = backend.load_plot(date, str(version))
            plot_children = _plot_img(plot_bytes)
            b64 = base64.b64encode(plot_bytes).decode() if plot_bytes else None
            return script_text, param_fields, data_children, plot_children, b64

        # -- RUN button --
        @app.callback(
            Output("gv-console", "children"),
            Output("gv-plot-panel", "children", allow_duplicate=True),
            Output("gv-plot-bytes-store", "data", allow_duplicate=True),
            Output("gv-editor-script", "value", allow_duplicate=True),
            Input("gv-run-btn", "n_clicks"),
            State("gv-editor-script", "value"),
            State({"type": "gv-param", "name": dash.ALL}, "value"),
            State("gv-plot-select", "data"),
            prevent_initial_call=True,
        )
        def run_script(n_clicks, script_code, param_values, plot_name):
            if not script_code:
                return "Nothing to run.", _no_plot(), None, dash.no_update
            backend = self._get_backend(plot_name)
            sections = ScriptSections.from_text(script_code)

            # Inject param field values into the Configurator section
            if param_values:
                sections = _inject_params(sections, param_values)
                script_code = sections.to_text()

            result = backend.run_preview(sections)
            console = result.output
            if not result.success:
                console += f"\n--- ERROR ---\n{result.error}"
            plot_children = _plot_img(result.plot_bytes)
            b64 = base64.b64encode(result.plot_bytes).decode() if result.plot_bytes else None
            return console or "(no output)", plot_children, b64, script_code

        # -- SAVE: step 1 — confirm --
        @app.callback(
            Output("gv-confirm-save", "displayed"),
            Input("gv-save-btn", "n_clicks"),
            prevent_initial_call=True,
        )
        def open_confirm_save(n_clicks):
            return True

        # -- SAVE: step 2 — actual save + refresh gallery --
        @app.callback(
            Output("gv-console", "children", allow_duplicate=True),
            Output("gv-plot-panel", "children", allow_duplicate=True),
            Output("gv-gallery-items", "data", allow_duplicate=True),
            Output("gv-date", "options", allow_duplicate=True),
            Output("gv-date", "value", allow_duplicate=True),
            Output("gv-version", "options", allow_duplicate=True),
            Output("gv-version", "value", allow_duplicate=True),
            Input("gv-confirm-save", "submit_n_clicks"),
            State("gv-editor-script", "value"),
            State("gv-plot-select", "data"),
            prevent_initial_call=True,
        )
        def save_version(submit_n_clicks, script_code, plot_name):
            if not script_code:
                return ("Nothing to save.", _no_plot(), dash.no_update, dash.no_update,
                        dash.no_update, dash.no_update, dash.no_update)

            from datetime import date as _date
            today = _date.today().strftime("%Y%m%d")
            backend = self._get_backend(plot_name)

            sections = ScriptSections.from_text(script_code)
            # save_version patches version/date, saves script, runs it, saves plot
            new_version = backend.save_version(today, sections)

            console = (
                f"Saved v{new_version}\n"
                f"  scripts/script_{today}_v{new_version}.py\n"
                f"  plots/plot_{today}_v{new_version}.png"
            )

            dates = backend.list_dates()
            date_opts = [{"label": d, "value": d} for d in dates]
            versions = backend.list_versions(today)
            ver_opts = [{"label": f"v{v}", "value": v} for v in versions]

            plot_bytes = backend.load_plot(today, str(new_version))
            plot_children = _plot_img(plot_bytes)

            # gallery-items triggers sidebar rebuild
            return (console, plot_children, self._build_plot_names(),
                    date_opts, today, ver_opts, new_version)

        # -- Export (only if export_fn provided) --
        if self.export_fn is not None:
            @app.callback(
                Output("export-download", "data"),
                Input("export-btn", "n_clicks"),
                State("gv-plot-bytes-store", "data"),
                prevent_initial_call=True,
            )
            def export_plot(n_clicks, b64_data):
                if not b64_data:
                    return dash.no_update
                raw_bytes = base64.b64decode(b64_data)
                exported = self.export_fn(raw_bytes)
                return dcc.send_bytes(exported, "exported_chart.png")

        # -- Add Plot (only if config file is used) --
        if self._config_path:
            @app.callback(
                Output("gv-add-plot-modal", "is_open"),
                Input("gv-add-plot-btn", "n_clicks"),
                Input("gv-add-plot-cancel", "n_clicks"),
                Input("gv-add-plot-submit", "n_clicks"),
                State("gv-add-plot-modal", "is_open"),
                prevent_initial_call=True,
            )
            def toggle_add_plot_modal(n_open, n_cancel, n_submit, is_open):
                trigger = ctx.triggered_id
                if trigger == "gv-add-plot-btn":
                    return True
                return False

            @app.callback(
                Output("gv-add-plot-feedback", "children"),
                Output("gv-plot-select", "data", allow_duplicate=True),
                Output("gv-gallery-items", "data", allow_duplicate=True),
                Input("gv-add-plot-submit", "n_clicks"),
                State("gv-add-plot-name", "value"),
                State("gv-add-plot-desc", "value"),
                prevent_initial_call=True,
            )
            def create_plot(n_clicks, name, desc):
                if not name or not name.strip():
                    return ("Please enter a plot name.",
                            dash.no_update, dash.no_update)

                name = name.strip().replace(" ", "_").lower()
                config = load_config(self._config_path)
                if name in config.get("plots", {}):
                    return (f"Plot '{name}' already exists.",
                            dash.no_update, dash.no_update)

                # Create directory + update config
                base = self._config_path.parent
                plot_path = base / name
                add_plot_to_config(config, name, str(plot_path), description=desc or "")
                save_config(config, self._config_path)

                # Register new backend
                self.backends[name] = FileSystemBackend(plot_path)
                self._multi = len(self.backends) > 1

                # Trigger sidebar rebuild by updating gallery-items
                return f"Created '{name}'", name, self._build_plot_names()


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def _inject_params(sections: ScriptSections, param_values: list) -> ScriptSections:
    """Inject parameter field values back into the Configurator section.

    Replaces the default values of typed assignments with the values
    from the UI input fields.
    """
    import ast
    import re as _re

    params = detect_params(sections.configurator)
    if not params:
        return sections

    param_names = list(params.keys())
    new_lines = []
    for line in sections.configurator.splitlines():
        replaced = False
        for i, name in enumerate(param_names):
            if i < len(param_values) and param_values[i] is not None:
                # Match pattern: name: type = value
                pattern = _re.compile(rf'^({_re.escape(name)}\s*:\s*\w+\s*=\s*)(.+)$')
                m = pattern.match(line.strip())
                if m:
                    val = param_values[i]
                    if isinstance(val, str):
                        new_lines.append(f'{m.group(1)}"{val}"')
                    elif isinstance(val, bool):
                        new_lines.append(f'{m.group(1)}{val}')
                    else:
                        new_lines.append(f'{m.group(1)}{val}')
                    replaced = True
                    break
        if not replaced:
            new_lines.append(line)

    return ScriptSections(
        configurator="\n".join(new_lines),
        code=sections.code,
        save=sections.save,
    )


def _build_param_fields(configurator_source: str) -> list:
    """Detect typed params and build input fields for them."""
    params = detect_params(configurator_source)
    if not params:
        return []

    fields = []
    for name, spec in params.items():
        label = name.replace("_", " ").title()
        if spec.annotation == bool:
            field = dbc.Checkbox(
                id={"type": "gv-param", "name": name},
                label=label,
                value=bool(spec.default),
                style={"marginBottom": "4px"},
            )
        elif spec.annotation in (int, float):
            field = html.Div([
                html.Label(label, style={"color": "#aaa", "fontSize": "11px"}),
                dbc.Input(
                    id={"type": "gv-param", "name": name},
                    type="number",
                    value=spec.default,
                    size="sm",
                    style={"marginBottom": "4px"},
                ),
            ])
        else:
            field = html.Div([
                html.Label(label, style={"color": "#aaa", "fontSize": "11px"}),
                dbc.Input(
                    id={"type": "gv-param", "name": name},
                    type="text",
                    value=str(spec.default),
                    size="sm",
                    style={"marginBottom": "4px"},
                ),
            ])
        fields.append(field)

    if fields:
        fields.insert(0, html.Div("Parameters", style=_SECTION_LABEL))
    return fields


def _no_plot():
    return html.Span("No plot available", style={"color": "#666"})


def _no_data():
    return html.Span("No data loaded", style={"color": "#666"})


def _plot_img(plot_bytes: bytes | None):
    if not plot_bytes:
        return _no_plot()
    b64 = base64.b64encode(plot_bytes).decode()
    return html.Img(
        src=f"data:image/png;base64,{b64}",
        style={"maxWidth": "100%", "maxHeight": "500px"},
    )


def _data_table(df):
    if df is None:
        return _no_data()
    df = df.head(50)
    return dash_table.DataTable(
        data=df.to_dict("records"),
        columns=[{"name": c, "id": c} for c in df.columns],
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": "#3a3a3a", "color": "#e0e0e0",
            "fontWeight": "bold", "fontFamily": "monospace", "fontSize": "12px",
        },
        style_cell={
            "backgroundColor": "#2a2a2a", "color": "#d4d4d4",
            "fontFamily": "monospace", "fontSize": "12px",
            "border": "1px solid #444", "padding": "4px 8px",
        },
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#252525"},
        ],
        page_size=50,
    )
