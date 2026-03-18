# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

from __future__ import annotations

import base64
import inspect
import io
from typing import Any, Callable

import dash
import matplotlib.pyplot as plt
from dash import Input, Output, State, dcc, html

from s5ndt._ids import id_generator
from s5ndt.config_builder import FromComponent, build_config
from s5ndt.dropdown import build_dropdown
from s5ndt.wizard import build_wizard

plt.switch_backend("agg")


class FromPlotly(FromComponent):
    """Read a value from the Plotly figure as the field default.

    Parameters
    ----------
    path :
        Dot-separated path into the figure dict, e.g. ``"layout.title.text"``.
    graph :
        The ``dcc.Graph`` component whose figure to read.
    """

    def __init__(self, path: str, graph: dcc.Graph):
        super().__init__(graph, "figure")
        self.path = path

    def get_default(self, *state_values: Any) -> Any:
        figure = state_values[0] if state_values else {}
        return _get_nested(figure, self.path)


def make_snapshot(browser_img: str):
    """Convert a browser-captured base64 PNG to a numpy image array.

    Parameters
    ----------
    browser_img :
        Base64 PNG data URL from ``Plotly.toImage()`` in the browser.

    Returns
    -------
    numpy.ndarray
        RGBA image array suitable for ``ax.imshow()``.
    """
    b64 = browser_img.split(",", 1)[1]
    return plt.imread(io.BytesIO(base64.b64decode(b64)))


def snapshot_renderer(_fig_data: dict, title: str = "", _img_b64: str = ""):
    """Render a Plotly figure as a matplotlib snapshot.

    Uses the browser-captured PNG — no kaleido required.
    Default renderer for :func:`mpl_export_button`.

    Parameters
    ----------
    _fig_data :
        Plotly figure dict (passed automatically by the export button).
    title :
        Axes title.
    _img_b64 :
        Browser-captured base64 PNG (passed automatically by the export button).

    Returns
    -------
    matplotlib.figure.Figure
    """
    img = make_snapshot(_img_b64)
    fig, ax = plt.subplots()
    ax.imshow(img)
    ax.axis("off")
    if title:
        ax.set_title(title)
    return fig


def mpl_export_button(
    graph_id: str,
    renderer: Callable = snapshot_renderer,
    label: str = "Export",
    strip_title: bool = False,
) -> html.Div:
    """Add a matplotlib export wizard button for a dcc.Graph.

    Parameters
    ----------
    graph_id :
        The ``id`` of the ``dcc.Graph`` component in the layout.
    renderer :
        Callable ``(_fig_data, **kwargs) -> matplotlib.figure.Figure``.
        Parameters after ``_fig_data`` are introspected to build the wizard fields.
        Parameters whose default is a :class:`FromPlotly` instance are populated
        from the live Plotly figure when the wizard opens.
        Defaults to :func:`snapshot_renderer`.
    label :
        Label for the trigger button. Defaults to ``"Export"``.
    strip_title :
        Remove the Plotly figure title before capturing the browser snapshot.
        Use when the renderer adds its own title via matplotlib.

    Returns
    -------
    html.Div
        A component containing the trigger button and the self-contained modal.
        Place it anywhere in the layout.
    """
    uid = id_generator(graph_id)
    config_id = f"_s5ndt_cfg_{uid}"
    wizard_id = f"_s5ndt_mpl_{uid}"
    preview_id = f"_s5ndt_preview_{uid}"
    generate_id = f"_s5ndt_generate_{uid}"
    download_id = f"_s5ndt_download_{uid}"
    interval_id = f"_s5ndt_interval_{uid}"
    restore_id = f"_s5ndt_restore_{uid}"
    menu_id = f"_s5ndt_menu_{uid}"
    autogenerate_id = f"_s5ndt_autogen_{uid}"
    snapshot_store_id = f"_s5ndt_snapshot_{uid}"

    config = build_config(config_id, renderer)
    _renderer_accepts_img = "_img_b64" in inspect.signature(renderer).parameters

    menu = build_dropdown(
        menu_id,
        trigger_label="···",
        close_inputs=[Input(restore_id, "n_clicks")],
        children=[
            html.Button("Reset to defaults", id=restore_id),
            dcc.Checklist(
                id=autogenerate_id,
                options=[{"label": " Auto-generate", "value": "auto"}],
                value=[],
                style={"padding": "4px 8px"},
            ),
        ],
    )

    _extra_stores = [dcc.Store(id=snapshot_store_id)] if _renderer_accepts_img else []

    body = html.Div(
        style={"display": "flex", "gap": "24px"},
        children=[
            html.Div(
                style={
                    "display": "flex",
                    "flexDirection": "column",
                    "gap": "8px",
                    "minWidth": "160px",
                },
                children=[
                    config.div,
                    html.Button("Generate", id=generate_id),
                    dcc.Download(id=download_id),
                    html.Button("Download PNG", id=f"{download_id}_btn"),
                ],
            ),
            html.Div(
                style={"position": "relative", "width": "400px", "height": "300px"},
                children=[
                    dcc.Loading(
                        type="circle",
                        children=[html.Img(id=preview_id, style={"maxWidth": "400px"})],
                    ),
                ],
            ),
            dcc.Interval(
                id=interval_id,
                interval=500,
                n_intervals=0,
                max_intervals=1,
                disabled=True,
            ),
            *_extra_stores,
        ],
    )

    wizard = build_wizard(
        wizard_id,
        body,
        trigger_label=label,
        title="Export as matplotlib figure",
        header_actions=menu,
    )
    config.register_populate_callback(wizard.open_input)
    config.register_restore_callback(Input(restore_id, "n_clicks"))

    @dash.callback(
        Output(interval_id, "disabled"),
        Output(interval_id, "n_intervals"),
        wizard.open_input,
        prevent_initial_call=True,
    )
    def arm_interval(is_open):
        return (not is_open, 0)

    if _renderer_accepts_img:
        # Capture the browser-rendered Plotly figure as a base64 PNG.
        # Guard: !n_intervals skips the arm_interval reset-to-0 side-effect.
        _js_head = f"""
            async function(n_clicks, n_intervals) {{
                if (!n_clicks && !n_intervals) {{
                    return window.dash_clientside.no_update;
                }}
                const container = document.getElementById('{graph_id}');
                if (!container) return window.dash_clientside.no_update;
                const graphDiv = container.querySelector('.js-plotly-plot')
                    || container;
        """
        if strip_title:
            _capture_js = (
                _js_head
                + """
                const layout = JSON.parse(JSON.stringify(graphDiv.layout || {}));
                layout.title = {text: ''};
                layout.margin = {...(layout.margin || {}), t: 20};
                const tmp = document.createElement('div');
                tmp.style.cssText = 'position:fixed;left:-9999px;width:'
                    + graphDiv.offsetWidth + 'px;height:'
                    + graphDiv.offsetHeight + 'px';
                document.body.appendChild(tmp);
                await Plotly.newPlot(tmp, graphDiv.data, layout);
                const img = await Plotly.toImage(tmp, {format: 'png'});
                document.body.removeChild(tmp);
                return img;
            }"""
            )
        else:
            _capture_js = (
                _js_head
                + "return await Plotly.toImage(graphDiv, {format: 'png'});"
                + "\n            }"
            )

        dash.clientside_callback(
            _capture_js,
            Output(snapshot_store_id, "data"),
            Input(generate_id, "n_clicks"),
            Input(interval_id, "n_intervals"),
            prevent_initial_call=True,
        )

        @dash.callback(
            Output(preview_id, "src"),
            Input(snapshot_store_id, "data"),
            State(graph_id, "figure"),
            *config.states,
            prevent_initial_call=True,
        )
        def generate_preview(_img_b64, _fig_data, *field_values):
            if not _img_b64:
                return dash.no_update
            kwargs = config.build_kwargs(field_values)
            kwargs["_img_b64"] = _img_b64
            fig = renderer(_fig_data, **kwargs)
            return _fig_to_src(fig)

        @dash.callback(
            Output(preview_id, "src", allow_duplicate=True),
            *[Input(s.component_id, s.component_property) for s in config.states],
            State(autogenerate_id, "value"),
            State(snapshot_store_id, "data"),
            State(graph_id, "figure"),
            prevent_initial_call=True,
        )
        def autogenerate_preview(*args):
            *field_values, autogen, _img_b64, _fig_data = args
            if not autogen:
                return dash.no_update
            kwargs = config.build_kwargs(tuple(field_values))
            kwargs["_img_b64"] = _img_b64 or ""
            fig = renderer(_fig_data, **kwargs)
            return _fig_to_src(fig)

        @dash.callback(
            Output(download_id, "data"),
            Input(f"{download_id}_btn", "n_clicks"),
            State(snapshot_store_id, "data"),
            State(graph_id, "figure"),
            *config.states,
            prevent_initial_call=True,
        )
        def download_figure(n_clicks, _img_b64, _fig_data, *field_values):
            kwargs = config.build_kwargs(field_values)
            kwargs["_img_b64"] = _img_b64 or ""
            fig = renderer(_fig_data, **kwargs)
            return dcc.send_bytes(_fig_to_bytes(fig), "figure.png")

    else:
        # No browser capture needed — renderer works directly from figure data.
        @dash.callback(
            Output(preview_id, "src"),
            Input(generate_id, "n_clicks"),
            Input(interval_id, "n_intervals"),
            State(graph_id, "figure"),
            *config.states,
            prevent_initial_call=True,
        )
        def generate_preview(n_clicks, n_intervals, _fig_data, *field_values):
            if not n_clicks and not n_intervals:
                return dash.no_update
            kwargs = config.build_kwargs(field_values)
            fig = renderer(_fig_data, **kwargs)
            return _fig_to_src(fig)

        @dash.callback(
            Output(preview_id, "src", allow_duplicate=True),
            *[Input(s.component_id, s.component_property) for s in config.states],
            State(autogenerate_id, "value"),
            State(graph_id, "figure"),
            prevent_initial_call=True,
        )
        def autogenerate_preview(*args):
            *field_values, autogen, _fig_data = args
            if not autogen:
                return dash.no_update
            kwargs = config.build_kwargs(tuple(field_values))
            fig = renderer(_fig_data, **kwargs)
            return _fig_to_src(fig)

        @dash.callback(
            Output(download_id, "data"),
            Input(f"{download_id}_btn", "n_clicks"),
            State(graph_id, "figure"),
            *config.states,
            prevent_initial_call=True,
        )
        def download_figure(n_clicks, _fig_data, *field_values):
            kwargs = config.build_kwargs(field_values)
            fig = renderer(_fig_data, **kwargs)
            return dcc.send_bytes(_fig_to_bytes(fig), "figure.png")

    return wizard.div


def _fig_to_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _fig_to_src(fig) -> str:
    encoded = base64.b64encode(_fig_to_bytes(fig)).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def _get_nested(data: Any, path: str) -> Any:
    for key in path.split("."):
        if not isinstance(data, dict):
            return None
        data = data.get(key)
        if data is None:
            return None
    return data
