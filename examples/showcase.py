"""dash-fn-interact showcase.

Seven sections on one scrollable page:

  1. All field types  — every type FnForm supports, one function.
  2. Styling          — dark theme, type-level styles, 2-column grid.
  3. Field        — per-field label/description/min/max/component override.
  4. Runtime hooks    — FromComponent + register_populate/restore_callback.
  5. Dirty tracking   — register_dirty_tracking + dirty_states.
  6. Visibility rules — Field(visible=...) + register_visibility_callbacks.
  7. Validation       — build_kwargs_validated + validation_outputs + invalid_outputs.

Run:
    uv run python examples/showcase.py
then open http://localhost:1236
"""

from __future__ import annotations

import json
import pathlib
from datetime import date, datetime
from enum import Enum
from typing import Annotated, Literal

from dash import Dash, Input, Output, dcc, html

from dash_fn_interact import Field, FnForm, FromComponent

app = Dash(__name__, suppress_callback_exceptions=True)


# ── shared helpers ────────────────────────────────────────────────────────────


class LineStyle(Enum):
    solid = "solid"
    dashed = "dashed"
    dotted = "dotted"


def _to_json(kwargs: dict) -> str:
    """Serialize kwargs to a readable JSON string (handles Enum/date/datetime/Path)."""
    out = {}
    for k, v in kwargs.items():
        if isinstance(v, Enum):
            out[k] = f"{type(v).__name__}.{v.name}  (value={v.value!r})"
        elif isinstance(v, datetime) or isinstance(v, date):
            out[k] = v.isoformat()
        elif isinstance(v, pathlib.Path):
            out[k] = str(v)
        else:
            out[k] = v
    return json.dumps(out, indent=2, default=str)


def _section(title: str, *children) -> html.Div:
    return html.Div(
        style={"marginBottom": "48px"},
        children=[
            html.H2(
                title,
                style={
                    "borderBottom": "2px solid #e0e0e0",
                    "paddingBottom": "8px",
                    "marginBottom": "24px",
                },
            ),
            *children,
        ],
    )


def _row(*children) -> html.Div:
    return html.Div(
        style={"display": "flex", "gap": "32px", "alignItems": "flex-start"},
        children=list(children),
    )


def _form_panel(*children, bg: str = "#f9f9f9") -> html.Div:
    return html.Div(
        style={
            "background": bg,
            "border": "1px solid #e0e0e0",
            "borderRadius": "8px",
            "padding": "20px",
            "minWidth": "320px",
        },
        children=list(children),
    )


def _output_panel(output_id: str) -> html.Div:
    return html.Div(
        style={"flex": "1"},
        children=[
            html.P(
                "kwargs after build_kwargs(values)",
                style={"margin": "0 0 8px", "fontSize": "12px", "color": "#888"},
            ),
            html.Pre(
                id=output_id,
                style={
                    "background": "#1e1e2e",
                    "color": "#cdd6f4",
                    "borderRadius": "6px",
                    "padding": "16px",
                    "fontSize": "13px",
                    "minHeight": "200px",
                    "overflowX": "auto",
                },
            ),
        ],
    )


def _apply_btn(btn_id: str, label: str = "Apply") -> html.Button:
    return html.Button(
        label,
        id=btn_id,
        n_clicks=0,
        style={
            "marginTop": "12px",
            "padding": "8px 20px",
            "background": "#5c6bc0",
            "color": "white",
            "border": "none",
            "borderRadius": "4px",
            "cursor": "pointer",
            "fontWeight": "600",
        },
    )


# ── Section 1: all field types ────────────────────────────────────────────────


def all_types_fn(
    name: str = "Alice",
    count: int = 5,
    scale: float = 1.5,
    active: bool = True,
    report_date: date | None = None,
    scheduled_at: datetime | None = None,
    method: Literal["euler", "runge-kutta", "adams"] = "euler",
    line_style: LineStyle = LineStyle.solid,
    weights: list[float] | None = None,
    bounds: tuple[float, float] | None = None,
    metadata: dict | None = None,
    output_path: pathlib.Path = pathlib.Path("/tmp/result.png"),
    notes: str | None = None,
):
    """One parameter for every type FnForm supports.

    list / tuple  — comma-separated values: 0.2, 0.5, 0.3
    dict          — JSON object: {"key": "value"}
    Path          — coerced to pathlib.Path
    Optional      — returns None when left empty
    """
    ...


cfg1 = FnForm("types", all_types_fn)


@app.callback(
    Output("out1", "children"),
    Input("btn1", "n_clicks"),
    *cfg1.states,
    prevent_initial_call=True,
)
def apply1(_n, *values):
    return _to_json(cfg1.build_kwargs(values))


# ── Section 2: styling ────────────────────────────────────────────────────────


def export_fn(
    title: str = "My Chart",
    width: int = 1200,
    height: int = 800,
    dpi: float = 150.0,
    transparent: bool = False,
    fmt: Literal["png", "svg", "pdf"] = "png",
    line: LineStyle = LineStyle.solid,
):
    """Figure export parameters."""
    ...


_dark_input = {
    "background": "#313244",
    "border": "1px solid #45475a",
    "borderRadius": "4px",
    "color": "#cdd6f4",
    "padding": "3px 7px",
}

cfg2 = FnForm(
    "styled",
    export_fn,
    _cols=2,
    _styles={
        "str": _dark_input,
        "int": {**_dark_input, "width": "90px"},
        "float": {**_dark_input, "width": "90px"},
        "literal": {"background": "#313244", "color": "#cdd6f4"},
        "enum": {"background": "#313244", "color": "#cdd6f4"},
        "label": {
            "fontSize": "11px",
            "fontWeight": "700",
            "textTransform": "uppercase",
            "letterSpacing": "0.07em",
            "color": "#a6adc8",
        },
    },
)


# @app.callback(
#     Output("out2", "children"),
#     Input("btn2", "n_clicks"),
#     *cfg2.states,
#     prevent_initial_call=True,
# )
# def apply2(_n, *values):
#     return _to_json(cfg2.build_kwargs(values))


# ── Section 3: Field ──────────────────────────────────────────────────────


def analysis_fn(
    input_path: Annotated[
        str,
        Field(
            label="Input file",
            description="Path to the CSV or Parquet file",
            col_span=2,
        ),
    ] = "",
    tolerance: Annotated[
        float,
        Field(
            label="Tolerance",
            description="Convergence threshold (1e-9 … 1.0)",
            min=1e-9,
            max=1.0,
            step=1e-6,
        ),
    ] = 1e-4,
    max_iter: int = 100,
    method: Literal["gradient", "newton", "conjugate"] = "gradient",
    seed: int | None = None,
):
    """Numerical solver parameters.

    method is overridden with a RadioItems component via field_specs.
    seed is excluded from the form.
    """
    ...


cfg3 = FnForm(
    "spec",
    analysis_fn,
    _cols=2,
    _exclude=["seed"],
    max_iter=Field(
        label="Max iterations",
        description="Hard stop after N steps",
        min=1,
        max=10_000,
        step=1,
    ),
    method=Field(
        label="Solver method",
        component=dcc.RadioItems(
            options=["gradient", "newton", "conjugate"],
            value="gradient",
            inline=True,
            inputStyle={"marginRight": "4px"},
            labelStyle={"marginRight": "14px"},
        ),
    ),
)


@app.callback(
    Output("out3", "children"),
    Input("btn3", "n_clicks"),
    *cfg3.states,
    prevent_initial_call=True,
)
def apply3(_n, *values):
    return _to_json(cfg3.build_kwargs(values))


# ── Section 4: runtime hooks ──────────────────────────────────────────────────
# Source components — their values are read as field defaults when "Populate"
# is clicked.  They must be created before FnForm so FromComponent can
# capture their ids.

source_label = dcc.Input(
    id="src-label",
    type="text",
    value="Revenue Q1",
    debounce=True,
    style={"padding": "4px 8px", "borderRadius": "4px", "border": "1px solid #ccc"},
)

source_color = dcc.Dropdown(
    id="src-color",
    options=["#5c6bc0", "#e53935", "#43a047", "#fb8c00"],
    value="#5c6bc0",
    style={"width": "200px"},
    clearable=False,
)


def chart_fn(chart_label: str = "", color: str = ""):
    """Chart annotation parameters.

    Defaults are populated from source components on the left when
    "Populate" is clicked (only fills empty fields — preserves edits).
    "Reset" restores both fields to empty.
    """
    ...


cfg4 = FnForm(
    "hooks",
    chart_fn,
    chart_label=Field(label="Chart label", hook=FromComponent(source_label, "value")),
    color=Field(label="Color", hook=FromComponent(source_color, "value")),
)

cfg4.register_populate_callback(Input("btn4-populate", "n_clicks"))
cfg4.register_restore_callback(Input("btn4-reset", "n_clicks"))


@app.callback(
    Output("out4", "children"),
    Input("btn4-apply", "n_clicks"),
    *cfg4.states,
    prevent_initial_call=True,
)
def apply4(_n, *values):
    return _to_json(cfg4.build_kwargs(values))


# ── Section 5: dirty field tracking ──────────────────────────────────────────


def report_fn(
    title: str = "Q1 Report",
    author: str = "Alice",
    pages: int = 10,
    draft: bool = True,
    format: Literal["pdf", "docx", "html"] = "pdf",
):
    """Report parameters. Edit any field, then click Apply to see which are dirty."""
    ...


cfg5 = FnForm("report", report_fn)
cfg5.register_dirty_tracking()


@app.callback(
    Output("out5-kwargs", "children"),
    Output("out5-dirty", "children"),
    Input("btn5", "n_clicks"),
    *cfg5.states,
    *cfg5.dirty_states,
    prevent_initial_call=True,
)
def apply5(_n, *all_values):
    *field_values, dirty = all_values
    kwargs = cfg5.build_kwargs(tuple(field_values))
    dirty = dirty or {}

    # Resolve which named fields were touched using field_id()
    dirty_names = [
        f
        for f in ["title", "author", "pages", "draft", "format"]
        if dirty.get(getattr(cfg5, f))
    ]

    dirty_out = json.dumps(
        {
            "touched_fields": dirty_names,
            "raw_store": {str(k): v for k, v in dirty.items()},
        },
        indent=2,
    )
    return _to_json(kwargs), dirty_out


# ── Section 6: visibility rules ───────────────────────────────────────────────
# fmt controls which optional fields are shown:
#   "png"  → show dpi only
#   "svg"  → no extra fields
#   "pdf"  → show paper_size + landscape


def render_fn(
    fmt: Literal["png", "svg", "pdf"] = "png",
    dpi: Annotated[
        int,
        Field(
            label="DPI",
            description="Only shown for PNG",
            min=72,
            max=600,
            visible=("fmt", "==", "png"),
        ),
    ] = 150,
    paper_size: Annotated[
        Literal["A4", "A3", "Letter"],
        Field(label="Paper size", visible=("fmt", "==", "pdf")),
    ] = "A4",
    landscape: Annotated[
        bool,
        Field(label="Landscape", visible=("fmt", "==", "pdf")),
    ] = False,
    title: str = "Untitled",
):
    """Render parameters. Change the format dropdown to show/hide fields."""
    ...


cfg6 = FnForm("render", render_fn)
cfg6.register_visibility_callbacks()


@app.callback(
    Output("out6", "children"),
    Input("btn6", "n_clicks"),
    *cfg6.states,
    prevent_initial_call=True,
)
def apply6(_n, *values):
    return _to_json(cfg6.build_kwargs(values))


# ── Section 7: validation ─────────────────────────────────────────────────────
# Built-in: type coercion failures + required checks.
# Custom validators via Field(validator=...) and bare callable in Annotated.


def validated_fn(
    username: Annotated[str, lambda v: None if len(v) >= 3 else "Min 3 characters"],
    age: int,
    score: Annotated[
        float,
        Field(
            description="Must be between 0 and 100",
            validator=lambda v: None if 0 <= v <= 100 else "Must be 0–100",
        ),
    ] = 50.0,
    tags: list[str] | None = None,
):
    """Fields validated on Apply.

    username: required + min 3 chars (bare lambda in Annotated).
    age: required (no default), built-in int check.
    score: custom Field validator (0–100).
    Try leaving fields empty, entering bad values, or score=200.
    """
    ...


cfg7 = FnForm("validated", validated_fn, age=(0, 120, 1))


@app.callback(
    Output("out7", "children"),
    *cfg7.validation_outputs,
    Input("btn7", "n_clicks"),
    *cfg7.states,
    prevent_initial_call=True,
)
def apply7(_n, *values):

    kwargs, errors = cfg7.build_kwargs_validated(values)
    if errors:
        return (
            json.dumps({"errors": errors}, indent=2),
            *cfg7.invalid_outputs(errors),
        )
    return _to_json(kwargs), *cfg7.invalid_outputs({})


# ── layout ────────────────────────────────────────────────────────────────────

app.layout = html.Div(
    style={"fontFamily": "sans-serif", "padding": "32px", "maxWidth": "1100px"},
    children=[
        html.H1("dash-fn-interact showcase", style={"marginBottom": "8px"}),
        html.P(
            "FnForm() — typed function → Dash form",
            style={"color": "#666", "marginBottom": "40px"},
        ),
        # ── 1: all field types ──────────────────────────────────────────────
        _section(
            "1 — All field types",
            _row(
                _form_panel(
                    cfg1,
                    _apply_btn("btn1"),
                ),
                _output_panel("out1"),
            ),
        ),
        # ── 2: styling ──────────────────────────────────────────────────────
        _section(
            "2 — Styling  (dark theme · type-level styles · cols=2)",
            _row(
                _form_panel(
                    cfg2,
                    _apply_btn("btn2"),
                    bg="#1e1e2e",
                ),
                _output_panel("out2"),
            ),
        ),
        # ── 3: Field ────────────────────────────────────────────────────
        _section(
            "3 — Field  (label · description · min/max · component override · exclude)",
            _row(
                _form_panel(
                    cfg3,
                    _apply_btn("btn3"),
                ),
                _output_panel("out3"),
            ),
        ),
        # ── 4: runtime hooks ────────────────────────────────────────────────
        _section(
            "4 — Runtime hooks  (FromComponent · register_populate · register_restore)",
            html.P(
                "Edit the source values, then click Populate to copy them into the form.",
                style={"color": "#555", "marginBottom": "16px"},
            ),
            _row(
                _form_panel(
                    html.Div(
                        style={"marginBottom": "16px"},
                        children=[
                            html.P(
                                "Source components",
                                style={
                                    "fontWeight": "600",
                                    "margin": "0 0 8px",
                                    "fontSize": "13px",
                                },
                            ),
                            html.Div(
                                style={
                                    "display": "flex",
                                    "flexDirection": "column",
                                    "gap": "8px",
                                },
                                children=[
                                    html.Label(
                                        "Label",
                                        style={"fontSize": "12px", "color": "#666"},
                                    ),
                                    source_label,
                                    html.Label(
                                        "Color",
                                        style={"fontSize": "12px", "color": "#666"},
                                    ),
                                    source_color,
                                ],
                            ),
                        ],
                    ),
                    html.Hr(style={"borderColor": "#e0e0e0", "margin": "12px 0"}),
                    cfg4,
                    html.Div(
                        style={"display": "flex", "gap": "8px", "marginTop": "12px"},
                        children=[
                            html.Button(
                                "Populate",
                                id="btn4-populate",
                                n_clicks=0,
                                style={
                                    "padding": "8px 16px",
                                    "background": "#43a047",
                                    "color": "white",
                                    "border": "none",
                                    "borderRadius": "4px",
                                    "cursor": "pointer",
                                    "fontWeight": "600",
                                },
                            ),
                            html.Button(
                                "Reset",
                                id="btn4-reset",
                                n_clicks=0,
                                style={
                                    "padding": "8px 16px",
                                    "background": "#e53935",
                                    "color": "white",
                                    "border": "none",
                                    "borderRadius": "4px",
                                    "cursor": "pointer",
                                    "fontWeight": "600",
                                },
                            ),
                            _apply_btn("btn4-apply"),
                        ],
                    ),
                ),
                _output_panel("out4"),
            ),
        ),
        # ── 5: dirty tracking ───────────────────────────────────────────────
        _section(
            "5 — Dirty tracking  (register_dirty_tracking · dirty_states · field_id)",
            html.P(
                "Edit any fields, then click Apply. The right panel shows which"
                " fields were touched and the raw store contents.",
                style={"color": "#555", "marginBottom": "16px"},
            ),
            _row(
                _form_panel(
                    cfg5,
                    _apply_btn("btn5"),
                ),
                html.Div(
                    style={
                        "flex": "1",
                        "display": "flex",
                        "flexDirection": "column",
                        "gap": "16px",
                    },
                    children=[
                        html.Div(
                            children=[
                                html.P(
                                    "kwargs",
                                    style={
                                        "margin": "0 0 8px",
                                        "fontSize": "12px",
                                        "color": "#888",
                                    },
                                ),
                                html.Pre(
                                    id="out5-kwargs",
                                    style={
                                        "background": "#1e1e2e",
                                        "color": "#cdd6f4",
                                        "borderRadius": "6px",
                                        "padding": "16px",
                                        "fontSize": "13px",
                                        "minHeight": "100px",
                                    },
                                ),
                            ]
                        ),
                        html.Div(
                            children=[
                                html.P(
                                    "dirty store",
                                    style={
                                        "margin": "0 0 8px",
                                        "fontSize": "12px",
                                        "color": "#888",
                                    },
                                ),
                                html.Pre(
                                    id="out5-dirty",
                                    style={
                                        "background": "#1e1e2e",
                                        "color": "#a6e3a1",
                                        "borderRadius": "6px",
                                        "padding": "16px",
                                        "fontSize": "13px",
                                        "minHeight": "100px",
                                    },
                                ),
                            ]
                        ),
                    ],
                ),
            ),
        ),
        # ── 7: validation ───────────────────────────────────────────────────
        _section(
            "7 — Validation  (build_kwargs_validated · validation_outputs · invalid_outputs)",
            html.P(
                "username and age are required. Try leaving them empty or entering"
                " text in a number field, then click Apply.",
                style={"color": "#555", "marginBottom": "16px"},
            ),
            _row(
                _form_panel(cfg7, _apply_btn("btn7")),
                _output_panel("out7"),
            ),
        ),
        # ── 6: visibility rules ─────────────────────────────────────────────
        _section(
            "6 — Visibility rules  (Field(visible=...) · register_visibility_callbacks)",
            html.P(
                'Change "Fmt" to see fields appear and disappear instantly'
                " — no server round-trip.",
                style={"color": "#555", "marginBottom": "16px"},
            ),
            _row(
                _form_panel(
                    cfg6,
                    _apply_btn("btn6"),
                ),
                _output_panel("out6"),
            ),
        ),
    ],
)

if __name__ == "__main__":
    app.run(debug=True, port=1236)
