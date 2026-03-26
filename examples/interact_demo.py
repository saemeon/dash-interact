"""interact() demo — dash-fn-form equivalent of ipywidgets.interact().

Nine panels on one page:

  1. Sine wave        — live update, returns plotly Figure → dcc.Graph
                        Field(persist=True) remembers slider positions on reload
  2. Text stats       — live update, returns str → dcc.Markdown
  3. Number table     — manual Apply, returns html.Table (Dash component → as-is)
  4. BMI calculator   — @interact no-arg decorator
  5. Colour mixer     — @interact(...) decorator with shorthands
  6. Sine (matplotlib)— live update, returns matplotlib Figure → html.Img
  7. Data table       — manual Apply, returns pd.DataFrame → DataTable
                        (requires: pip install pandas)
  8. Dict return      — function returns dict → labelled card grid
  9. Caching          — _cache=True skips re-calling fn on repeated identical inputs

Run:
    uv run python examples/interact_demo.py
then open http://localhost:1237
"""

from __future__ import annotations

from typing import Literal

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import plotly.graph_objects as go
from dash import Dash, html
from dash_interact import Field, interact

matplotlib.use("Agg")  # non-interactive backend — must be set before pyplot use

app = Dash(__name__)


# ── 1. Sine wave — returns a plotly Figure ──────────────────────────────────


def sine_wave(
    amplitude: float = 1.0,
    frequency: float = 2.0,
    phase: float = 0.0,
    color: Literal["royalblue", "tomato", "seagreen"] = "royalblue",
) -> go.Figure:
    """Adjust the sliders to reshape the wave in real time."""
    t = np.linspace(0, 2 * np.pi, 500)
    y = amplitude * np.sin(frequency * t + phase)
    fig = go.Figure(go.Scatter(x=t, y=y, line={"color": color}))
    fig.update_layout(
        margin={"t": 20, "b": 20, "l": 40, "r": 20},
        yaxis_range=[-2.5, 2.5],
        height=280,
    )
    return fig


# persist=True — slider positions survive a full page refresh (session storage)
panel1 = interact(
    sine_wave,
    amplitude=Field(ge=0.0, le=2.5, step=0.05, persist=True),
    frequency=Field(ge=0.1, le=10.0, step=0.1, persist=True),
    phase=Field(ge=0.0, le=6.28, step=0.05, persist=True),
)


# ── 2. Text stats — returns str → dcc.Markdown ───────────────────────────────


def text_stats(
    text: str = "Hello, Dash!",
    case: Literal["original", "upper", "lower", "title"] = "original",
    reverse: bool = False,
) -> str:
    """Type anything to see live statistics."""
    transformed = {
        "original": text,
        "upper": text.upper(),
        "lower": text.lower(),
        "title": text.title(),
    }[case]
    if reverse:
        transformed = transformed[::-1]
    words = len(text.split())
    chars = len(text)
    return f"**{transformed}**\n\nwords: {words}  ·  chars: {chars}"


panel2 = interact(
    text_stats,
    text=Field(min_length=0, max_length=200),
)


# ── 3. Number table — manual Apply, returns html.Table ──────────────────────


def number_table(
    start: int = 1,
    count: int = 5,
    step: int = 1,
    show_squares: bool = True,
) -> html.Table:
    """Generate a table of numbers. Click Apply to update."""
    nums = list(range(start, start + count * step, step))
    header = ["n", "n²"] if show_squares else ["n"]
    rows = (
        [[str(n), str(n * n)] for n in nums]
        if show_squares
        else [[str(n)] for n in nums]
    )
    return html.Table(
        [html.Thead(html.Tr([html.Th(h) for h in header]))]
        + [html.Tbody([html.Tr([html.Td(c) for c in row]) for row in rows])],
        style={"borderCollapse": "collapse", "fontFamily": "monospace"},
    )


panel3 = interact(
    number_table,
    _manual=True,
    start=Field(ge=1, le=1000),
    count=Field(ge=1, le=50),
    step=Field(ge=1, le=100),
)


# ── 4. BMI calculator — @interact decorator (no-arg form) ───────────────────


@interact
def bmi_calculator(
    weight_kg: float = 70.0,
    height_cm: float = 175.0,
) -> str:
    """interact can also be used as a decorator."""
    if height_cm <= 0:
        return "Height must be > 0"
    bmi = weight_kg / (height_cm / 100) ** 2
    category = (
        "Underweight"
        if bmi < 18.5
        else "Normal"
        if bmi < 25
        else "Overweight"
        if bmi < 30
        else "Obese"
    )
    return f"**BMI: {bmi:.1f}** — {category}"


# ── 5. Colour mixer — @interact(...) decorator with shorthands ───────────────


@interact(
    red=Field(ge=0, le=255, step=1),
    green=Field(ge=0, le=255, step=1),
    blue=Field(ge=0, le=255, step=1),
)
def colour_mixer(
    red: int = 100,
    green: int = 149,
    blue: int = 237,
) -> html.Div:
    """@interact(...) — decorator with per-field shorthands."""
    hex_color = f"#{red:02x}{green:02x}{blue:02x}"
    return html.Div(
        style={
            "background": hex_color,
            "height": "80px",
            "borderRadius": "6px",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "fontWeight": "bold",
            "color": "white"
            if (red * 299 + green * 587 + blue * 114) / 1000 < 128
            else "#333",
            "textShadow": "0 1px 2px rgba(0,0,0,0.3)",
        },
        children=hex_color,
    )


# ── 6. Matplotlib figure — auto-rendered as html.Img ────────────────────────


def sine_matplotlib(
    amplitude: float = 1.0,
    frequency: float = 2.0,
    color: Literal["royalblue", "tomato", "seagreen", "darkorange"] = "royalblue",
) -> plt.Figure:
    """Returns a matplotlib Figure — auto-converted to a PNG image."""
    t = np.linspace(0, 2 * np.pi, 500)
    y = amplitude * np.sin(frequency * t)
    fig, ax = plt.subplots(figsize=(7, 2.5))
    ax.plot(t, y, color=color)
    ax.set_ylim(-2.5, 2.5)
    ax.set_xlabel("t")
    fig.tight_layout()
    return fig


panel6 = interact(
    sine_matplotlib,
    amplitude=Field(ge=0.0, le=2.5, step=0.05),
    frequency=Field(ge=0.1, le=10.0, step=0.1),
)


# ── 7. pandas DataFrame — auto-rendered as DataTable ────────────────────────
# Requires: pip install pandas


try:
    import pandas as pd

    def data_table(
        n_rows: int = 10,
        scale: float = 1.0,
        noise: bool = False,
    ) -> pd.DataFrame:
        """Returns a pd.DataFrame — auto-rendered as a DataTable."""
        rng = np.random.default_rng(42)
        x = np.arange(n_rows, dtype=float)
        y = x * scale
        if noise:
            y += rng.normal(0, scale * 0.1, size=n_rows)
        return pd.DataFrame({"x": x, "y": y.round(3), "y²": (y**2).round(3)})

    panel7 = interact(data_table, _manual=True, n_rows=Field(ge=1, le=100))

except ImportError:
    panel7 = html.P(
        "pandas not installed — run: pip install pandas",
        style={"color": "#888", "fontStyle": "italic"},
    )


# ── 8. Dict return — each value rendered as a labelled card ─────────────────


def wave_stats(
    amplitude: float = 1.0,
    frequency: float = 2.0,
    n_points: int = 500,
) -> dict:
    """Returns a dict — each entry is rendered as a labelled card."""
    t = np.linspace(0, 2 * np.pi, n_points)
    y = amplitude * np.sin(frequency * t)
    return {
        "min": f"{y.min():.4f}",
        "max": f"{y.max():.4f}",
        "mean": f"{y.mean():.4f}",
        "std": f"{y.std():.4f}",
        "rms": f"{np.sqrt(np.mean(y**2)):.4f}",
        "plot": go.Figure(
            go.Scatter(x=t, y=y, line={"color": "royalblue"}),
            layout={"margin": {"t": 10, "b": 30, "l": 40, "r": 10}, "height": 200},
        ),
    }


panel8 = interact(
    wave_stats,
    amplitude=Field(ge=0.0, le=2.5, step=0.05),
    frequency=Field(ge=0.1, le=10.0, step=0.1),
    n_points=Field(ge=10, le=2000, step=10),
)


# ── 9. Caching — _cache=True avoids redundant function calls ─────────────────


_cache_call_count = [0]


def cached_wave(
    amplitude: float = 1.0,
    frequency: float = 2.0,
) -> dict:
    """Expensive function — _cache=True skips re-calling on repeated inputs.

    The call counter increments only on a genuine call.  Submit the same
    values twice and the counter stays the same.
    """
    _cache_call_count[0] += 1
    t = np.linspace(0, 2 * np.pi, 500)
    y = amplitude * np.sin(frequency * t)
    fig = go.Figure(
        go.Scatter(x=t, y=y, line={"color": "seagreen"}),
        layout={"margin": {"t": 10, "b": 30, "l": 40, "r": 10}, "height": 200},
    )
    return {
        "calls so far": str(_cache_call_count[0]),
        "plot": fig,
    }


panel9 = interact(
    cached_wave,
    _cache=True,
    _id="cached_wave",
    amplitude=Field(ge=0.0, le=2.5, step=0.05),
    frequency=Field(ge=0.1, le=10.0, step=0.1),
)


# ── layout ───────────────────────────────────────────────────────────────────

_section_style = {
    "background": "#f9f9f9",
    "border": "1px solid #e0e0e0",
    "borderRadius": "8px",
    "padding": "20px 24px",
    "maxWidth": "700px",
}


def _section(title: str, panel) -> html.Div:
    return html.Div(
        style={**_section_style, "marginBottom": "32px"},
        children=[
            html.H3(
                title,
                style={"margin": "0 0 16px 0", "fontSize": "1rem", "color": "#333"},
            ),
            panel,
        ],
    )


app.layout = html.Div(
    style={"fontFamily": "sans-serif", "padding": "32px", "maxWidth": "780px"},
    children=[
        html.H1("interact() demo", style={"marginBottom": "8px"}),
        html.P(
            "dash-fn-form equivalent of ipywidgets.interact(). "
            "Panels 1–5: various return types. Panels 6–7: auto-rendered objects.",
            style={"color": "#666", "marginBottom": "32px"},
        ),
        _section(
            "1 — Sine wave  (live · go.Figure → dcc.Graph · persist=True)", panel1
        ),
        _section("2 — Text stats  (live · str → dcc.Markdown)", panel2),
        _section("3 — Number table  (manual Apply · html.Table → as-is)", panel3),
        _section(
            "4 — BMI calculator  (@interact · no-arg decorator · str → Markdown)",
            bmi_calculator,
        ),
        _section(
            "5 — Colour mixer  (@interact(...) · decorator with shorthands · html.Div → as-is)",
            colour_mixer,
        ),
        _section(
            "6 — Sine (matplotlib)  (live · Figure → html.Img via base64 PNG)", panel6
        ),
        _section("7 — Data table  (manual Apply · pd.DataFrame → DataTable)", panel7),
        _section(
            "8 — Dict return  (dict → labelled card grid · nested renderer pipeline)",
            panel8,
        ),
        _section(
            "9 — Caching  (_cache=True · LRU · call counter stays on repeated inputs)",
            panel9,
        ),
    ],
)

if __name__ == "__main__":
    app.run(debug=True, port=1237)
