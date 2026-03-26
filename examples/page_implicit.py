"""Page (implicit) example.

Demonstrates the implicit convenience layer — import ``page`` and call
everything through it, just like ``matplotlib.pyplot``.

    from dash_interact import page

    page.H1("My App")

    @page.interact
    def sine_wave(amplitude: float = 1.0): ...

    page.run()

No Page object, no app.layout, no Dash() instantiation.

Run:
    uv run python examples/page_implicit.py
then open http://localhost:8061
"""

from typing import Literal

import numpy as np
import plotly.graph_objects as go

from dash_interact import page

# ── header ────────────────────────────────────────────────────────────────────

page.H1("Page — implicit", style={"marginBottom": "4px"})
page.P(
    "Same two panels as page_explicit.py — written top-to-bottom with no "
    "Page object and no app.layout.",
    style={"color": "#666", "marginBottom": "32px"},
)

# ── panel 1: sine wave ────────────────────────────────────────────────────────

page.H2("Sine wave", style={"marginBottom": "16px"})


@page.interact(amplitude=(0.1, 3.0, 0.1), frequency=(0.5, 8.0, 0.5))
def sine_wave(
    amplitude: float = 1.0,
    frequency: float = 2.0,
    n_cycles: int = 3,
    color: Literal["royalblue", "crimson", "seagreen", "darkorange"] = "royalblue",
    show_envelope: bool = False,
):
    """Sine wave with configurable amplitude, frequency, and color."""
    x = np.linspace(0, n_cycles * 2 * np.pi, 600)
    y = amplitude * np.sin(frequency * x)

    traces = [go.Scatter(x=x, y=y, mode="lines", line={"color": color, "width": 2})]
    if show_envelope:
        traces.extend(
            go.Scatter(
                x=x,
                y=[sign * amplitude] * len(x),
                mode="lines",
                line={"color": color, "dash": "dot", "width": 1},
                showlegend=False,
            )
            for sign in (1, -1)
        )

    return go.Figure(
        traces,
        layout={
            "margin": {"t": 20, "b": 40},
            "yaxis": {"range": [-3.5, 3.5]},
            "xaxis": {"title": "x"},
        },
    )


# ── divider ───────────────────────────────────────────────────────────────────

page.Hr(style={"margin": "32px 0", "borderColor": "#e0e0e0"})
page.H2("Histogram", style={"marginBottom": "16px"})

# ── panel 2: histogram ────────────────────────────────────────────────────────


@page.interact(n_samples=(50, 2000, 50), bins=(5, 100, 5))
def random_histogram(
    n_samples: int = 500,
    mean: float = 0.0,
    std: float = 1.0,
    bins: int = 40,
    color: Literal["royalblue", "crimson", "seagreen", "darkorange"] = "seagreen",
):
    """Normal-distribution histogram with configurable parameters."""
    rng = np.random.default_rng(seed=42)
    data = rng.normal(mean, max(std, 0.01), n_samples)
    return go.Figure(
        go.Histogram(x=data, nbinsx=bins, marker_color=color, opacity=0.8),
        layout={
            "margin": {"t": 20, "b": 40},
            "xaxis": {"title": "value"},
            "yaxis": {"title": "count"},
            "bargap": 0.05,
        },
    )


# ── launch ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    page.run(debug=True, port=8061)
