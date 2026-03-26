"""Page (explicit) example.

Demonstrates the :class:`~dash_interact.Page` object: build a multi-panel
app by calling ``page.interact()`` and ``page.add()`` in order, then launch
with ``page.run()`` — no manual ``app.layout`` wiring needed.

Call styles demonstrated:
  - direct call:          page.interact(fn, ...)
  - decorator:            @page.interact  /  @page.interact(...)
  - _loading=False:       disable spinner for fast functions
  - _loading=True:        spinner shown for slow functions (default)
  - _manual=True:         Apply button instead of live update
  - Field(persist=True):  slider positions remembered across page reloads

Run:
    uv run python examples/page_explicit.py
then open http://localhost:8060
"""

import time
from typing import Literal

import numpy as np
import plotly.graph_objects as go

from dash_interact import Field, Page

page = Page()

# ── header ────────────────────────────────────────────────────────────────────

page.H1("Page — explicit", style={"marginBottom": "4px"})
page.P(
    "Three panels showing live update, disabled spinner, and a slow function "
    "where the loading indicator is most visible.",
    style={"color": "#666", "marginBottom": "32px"},
)

# ── panel 1: sine wave — fast, spinner disabled ───────────────────────────────
# For very fast functions the spinner flash can be distracting — turn it off.

page.H2("Sine wave", style={"marginBottom": "4px"})
page.P(
    "_loading=False — renders instantly, no spinner flash. "
    "Field(persist=True) — amplitude and frequency sliders are remembered on reload.",
    style={"color": "#888", "fontSize": "13px", "marginBottom": "12px"},
)


# persist=True on the custom Field specs — amplitude and frequency are remembered on reload
@page.interact(
    amplitude=Field(min=0.1, max=3.0, step=0.1, persist=True),
    frequency=Field(min=0.5, max=8.0, step=0.5, persist=True),
    _loading=False,
)
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


# ── panel 2: histogram — fast, default spinner ────────────────────────────────

page.Hr(style={"margin": "32px 0", "borderColor": "#e0e0e0"})
page.H2("Histogram", style={"marginBottom": "4px"})
page.P(
    "_loading=True (default) — spinner shown while callback runs.",
    style={"color": "#888", "fontSize": "13px", "marginBottom": "12px"},
)


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


page.interact(random_histogram, n_samples=(50, 2000, 50), bins=(5, 100, 5))

# ── panel 3: slow function — manual mode + spinner ────────────────────────────
# _manual=True adds an Apply button so the expensive call only fires on click.
# The spinner is most visible here — it shows for the full duration of the sleep.

page.Hr(style={"margin": "32px 0", "borderColor": "#e0e0e0"})
page.H2("Slow computation", style={"marginBottom": "4px"})
page.P(
    "_manual=True + _loading=True — click Apply and watch the spinner.",
    style={"color": "#888", "fontSize": "13px", "marginBottom": "12px"},
)


@page.interact(_manual=True, n_points=(100, 5000, 100))
def slow_scatter(
    n_points: int = 1000,
    delay: float = 1.0,
    color: Literal["royalblue", "crimson", "seagreen"] = "royalblue",
):
    """Simulates a slow computation — sleep before returning the figure."""
    time.sleep(delay)
    rng = np.random.default_rng(seed=0)
    x, y = rng.standard_normal(n_points), rng.standard_normal(n_points)
    return go.Figure(
        go.Scatter(
            x=x, y=y, mode="markers", marker={"color": color, "opacity": 0.5, "size": 4}
        ),
        layout={"margin": {"t": 20, "b": 40}},
    )


# ── launch ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    page.run(debug=True, port=8060)
