"""dash-capture demo — run with: uv run python examples/capture_demo.py

Showcases the full range of auto-generated form field types:
  str, int, float, bool, Literal (dropdown), date, datetime, list
"""

import io
from datetime import date
from typing import Literal

import dash
import pandas as pd
import plotly.graph_objects as go
from dash import dash_table, dcc, html
from dash_capture import capture_element, capture_graph, plotly_strategy

# --- sample figure ---
fig = go.Figure(
    data=[
        go.Scatter(
            x=[1, 2, 3, 4, 5], y=[2, 5, 3, 8, 4], mode="lines+markers", name="Series A"
        ),
        go.Scatter(
            x=[1, 2, 3, 4, 5], y=[1, 3, 6, 4, 7], mode="lines+markers", name="Series B"
        ),
    ],
    layout=dict(
        title="Sample Chart",
        xaxis_title="X",
        yaxis_title="Y",
        width=700,
        height=400,
        showlegend=True,
    ),
)
graph = dcc.Graph(id="demo-graph", figure=fig)


# ---------------------------------------------------------------------------
# Renderers — each showcases different parameter types → form field types
# ---------------------------------------------------------------------------


def passthrough(_target, _snapshot_img):
    """No user parameters → empty wizard (just Generate + Download)."""
    _target.write(_snapshot_img())


def str_and_int_renderer(
    _target,
    _snapshot_img,
    title: str = "My Report",
    dpi: int = 150,
):
    """str → text input, int → number input.

    Overlays a matplotlib title at the given DPI.
    """
    import matplotlib.pyplot as plt

    plt.switch_backend("agg")
    raw = plt.imread(io.BytesIO(_snapshot_img()))
    h, w = raw.shape[:2]
    fig_mpl, ax = plt.subplots(figsize=(w / dpi, h / dpi), dpi=dpi)
    try:
        ax.imshow(raw)
        ax.axis("off")
        if title:
            ax.set_title(title, fontsize=10)
        fig_mpl.savefig(_target, format="png", bbox_inches="tight", pad_inches=0)
    finally:
        plt.close(fig_mpl)


def literal_and_bool_renderer(
    _target,
    _snapshot_img,
    border_color: Literal["white", "black", "gray", "navy"] = "white",
    border_width: int = 20,
    add_shadow: bool = False,
):
    """Literal → dropdown, int → number input, bool → checkbox.

    Adds a colored border (and optional shadow) using PIL.
    """
    from PIL import Image, ImageFilter

    img = Image.open(io.BytesIO(_snapshot_img()))
    bw = border_width
    new = Image.new("RGB", (img.width + 2 * bw, img.height + 2 * bw), border_color)
    new.paste(img, (bw, bw))
    if add_shadow:
        new = new.filter(ImageFilter.GaussianBlur(radius=3))
        new.paste(img, (bw, bw))
    buf = io.BytesIO()
    new.save(buf, format="PNG")
    _target.write(buf.getvalue())


def float_renderer(
    _target,
    _snapshot_img,
    brightness: float = 1.0,
    contrast: float = 1.0,
):
    """float → number input (with decimal step).

    Adjusts brightness and contrast using PIL.
    """
    from PIL import Image, ImageEnhance

    img = Image.open(io.BytesIO(_snapshot_img()))
    img = ImageEnhance.Brightness(img).enhance(brightness)
    img = ImageEnhance.Contrast(img).enhance(contrast)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    _target.write(buf.getvalue())


def date_renderer(
    _target,
    _snapshot_img,
    report_date: date = date(2026, 3, 22),
    author: str = "Data Team",
):
    """date → date picker, str → text input.

    Stamps a date and author line below the image.
    """
    from PIL import Image, ImageDraw

    img = Image.open(io.BytesIO(_snapshot_img()))
    new = Image.new("RGB", (img.width, img.height + 30), "white")
    new.paste(img, (0, 0))
    draw = ImageDraw.Draw(new)
    draw.text((10, img.height + 5), f"{report_date} — {author}", fill="gray")
    buf = io.BytesIO()
    new.save(buf, format="PNG")
    _target.write(buf.getvalue())


def figdata_renderer(
    _target,
    _fig_data,
    output_format: Literal["summary", "json"] = "summary",
):
    """_fig_data → receives the Plotly figure dict (no browser capture needed).

    Demonstrates server-side figure access without _snapshot_img.
    Writes a text summary or JSON dump of the figure data.
    """
    import json

    if output_format == "json":
        text = json.dumps(_fig_data, indent=2, default=str)
    else:
        n_traces = len(_fig_data.get("data", []))
        title = _fig_data.get("layout", {}).get("title", {}) or {}
        title_text = (
            title.get("text", "(no title)") if isinstance(title, dict) else title
        )
        text = f"Figure: {title_text}\nTraces: {n_traces}"

    _target.write(text.encode())


def error_renderer(
    _target,
    _snapshot_img,
    max_size_kb: int = 50,
):
    """Demonstrates error display — fails if image exceeds max_size_kb."""
    data = _snapshot_img()
    size_kb = len(data) / 1024
    if size_kb > max_size_kb:
        raise ValueError(
            f"Image too large: {size_kb:.0f} KB (max {max_size_kb} KB). "
            f"Try a smaller chart or lower resolution."
        )
    _target.write(data)


# ---------------------------------------------------------------------------
# App layout
# ---------------------------------------------------------------------------

# --- sample table ---
df = pd.DataFrame(
    {
        "Country": ["Switzerland", "Germany", "France", "Italy", "Austria"],
        "Population (M)": [8.7, 83.2, 67.4, 59.6, 9.0],
        "GDP per capita ($)": [93_720, 51_380, 44_850, 35_550, 53_640],
        "Life expectancy": [83.4, 80.9, 82.5, 82.9, 81.6],
    }
)

table = dash_table.DataTable(
    id="demo-table",
    columns=[{"name": c, "id": c} for c in df.columns],
    data=df.to_dict("records"),
    style_table={"width": "600px"},
    style_header={"backgroundColor": "#2c3e50", "color": "white", "fontWeight": "bold"},
    style_cell={"padding": "8px", "fontFamily": "system-ui, sans-serif"},
    style_data_conditional=[
        {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
    ],
)

app = dash.Dash(
    __name__,
    external_scripts=[
        # html2canvas — needed for capture_element (table capture)
        "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.0/html2canvas.min.js",
    ],
)

SECTION = {"marginBottom": "30px"}

app.layout = html.Div(
    style={
        "maxWidth": "900px",
        "margin": "0 auto",
        "padding": "20px",
        "fontFamily": "system-ui, sans-serif",
    },
    children=[
        html.H2("dash-capture — field type showcase"),
        html.P(
            "Each button opens a wizard. The form fields are auto-generated "
            "from the renderer function's type hints. Try them all!"
        ),
        html.Hr(),
        graph,
        html.Br(),
        # 1. No fields
        html.Div(
            style=SECTION,
            children=[
                html.H4("1. No parameters → empty wizard"),
                html.Code("def passthrough(_target, _snapshot_img)"),
                html.Br(),
                html.Br(),
                capture_graph(graph, renderer=passthrough, trigger="Capture (simple)"),
            ],
        ),
        # 2. str + int
        html.Div(
            style=SECTION,
            children=[
                html.H4("2. str + int → text input + number input"),
                html.Code("def renderer(_target, _snapshot_img, title: str, dpi: int)"),
                html.Br(),
                html.Br(),
                capture_graph(
                    "demo-graph",
                    renderer=str_and_int_renderer,
                    trigger="Capture (matplotlib)",
                ),
            ],
        ),
        # 3. Literal + bool
        html.Div(
            style=SECTION,
            children=[
                html.H4("3. Literal + int + bool → dropdown + number + checkbox"),
                html.Code(
                    "def renderer(..., border_color: Literal[...], add_shadow: bool)"
                ),
                html.Br(),
                html.Br(),
                capture_graph(
                    "demo-graph",
                    renderer=literal_and_bool_renderer,
                    trigger="Capture (PIL border)",
                ),
            ],
        ),
        # 4. float
        html.Div(
            style=SECTION,
            children=[
                html.H4("4. float → number input with decimal step"),
                html.Code("def renderer(..., brightness: float, contrast: float)"),
                html.Br(),
                html.Br(),
                capture_graph(
                    "demo-graph",
                    renderer=float_renderer,
                    trigger="Capture (brightness/contrast)",
                ),
            ],
        ),
        # 5. date
        html.Div(
            style=SECTION,
            children=[
                html.H4("5. date → date picker"),
                html.Code("def renderer(..., report_date: date, author: str)"),
                html.Br(),
                html.Br(),
                capture_graph(
                    "demo-graph", renderer=date_renderer, trigger="Capture (date stamp)"
                ),
            ],
        ),
        # 6. strip patches
        html.Div(
            style=SECTION,
            children=[
                html.H4("6. Strip patches — preprocess before capture"),
                html.P(
                    "Same passthrough renderer, but Plotly title + legend are "
                    "removed before the browser captures the image."
                ),
                capture_graph(
                    "demo-graph",
                    renderer=passthrough,
                    trigger="Capture (stripped)",
                    strip_title=True,
                    strip_legend=True,
                ),
            ],
        ),
        # 7. _fig_data (no snapshot)
        html.Div(
            style=SECTION,
            children=[
                html.H4("7. _fig_data — server-side figure access (no screenshot)"),
                html.P(
                    "Renderer receives the Plotly figure dict directly. "
                    "No browser capture — useful for data extraction."
                ),
                html.Code(
                    "def renderer(_target, _fig_data, output_format: Literal[...])"
                ),
                html.Br(),
                html.Br(),
                capture_graph(
                    "demo-graph",
                    renderer=figdata_renderer,
                    trigger="Capture (fig data)",
                ),
            ],
        ),
        # 8. explicit strategy
        html.Div(
            style=SECTION,
            children=[
                html.H4("8. Explicit strategy object"),
                html.P(
                    "Pass a plotly_strategy() directly instead of using strip_* flags."
                ),
                capture_graph(
                    "demo-graph",
                    renderer=passthrough,
                    trigger="Capture (strategy)",
                    strategy=plotly_strategy(
                        strip_margin=True,
                        strip_title=True,
                        strip_colorbar=True,
                    ),
                ),
            ],
        ),
        # 9. Table capture (html2canvas)
        html.Hr(),
        html.H3("Table capture — capture_element + html2canvas"),
        html.P(
            "capture_element() uses html2canvas to capture any DOM element, "
            "not just Plotly graphs. The table below is a plain dash_table.DataTable."
        ),
        html.Br(),
        table,
        html.Br(),
        html.Div(
            style=SECTION,
            children=[
                html.H4("9. Table → simple capture"),
                html.Code("capture_element('demo-table', renderer=passthrough)"),
                html.Br(),
                html.Br(),
                capture_element(
                    "demo-table", renderer=passthrough, trigger="Capture table"
                ),
            ],
        ),
        html.Div(
            style=SECTION,
            children=[
                html.H4("10. Table → PIL border + title"),
                html.P("Same border renderer from example 3, but applied to a table."),
                capture_element(
                    "demo-table",
                    renderer=literal_and_bool_renderer,
                    trigger="Capture table (styled)",
                ),
            ],
        ),
        # 11. Format selection
        html.Hr(),
        html.H3("Format selection"),
        html.Div(
            style=SECTION,
            children=[
                html.H4("11. Capture as JPEG"),
                html.P("plotly_strategy(format='jpeg') — smaller file size, lossy."),
                capture_graph(
                    "demo-graph",
                    renderer=passthrough,
                    trigger="Capture (JPEG)",
                    strategy=plotly_strategy(format="jpeg"),
                ),
            ],
        ),
        html.Div(
            style=SECTION,
            children=[
                html.H4("12. Capture as SVG"),
                html.P("plotly_strategy(format='svg') — vector format, infinite zoom."),
                capture_graph(
                    "demo-graph",
                    renderer=passthrough,
                    trigger="Capture (SVG)",
                    strategy=plotly_strategy(format="svg"),
                ),
            ],
        ),
        # 13. Error display
        html.Hr(),
        html.H3("Error handling"),
        html.Div(
            style=SECTION,
            children=[
                html.H4("13. Renderer that raises an error"),
                html.P("The error message is shown in red below the preview."),
                capture_graph(
                    "demo-graph",
                    renderer=error_renderer,
                    trigger="Capture (error demo)",
                ),
            ],
        ),
    ],
)

if __name__ == "__main__":
    app.run(debug=False)
