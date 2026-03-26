"""dash-fn-form — FnForm example (manual-callback form).

Shows the manual workflow:
  1. Define a typed function.
  2. Wrap it in FnForm to get form controls.
  3. Wire a custom Dash callback using cfg.states / cfg.build_kwargs.

This is the lower-level alternative to interact() — use it when you need
full control over the callback (custom outputs, state sharing, etc.).

Run:
    uv run python examples/interact.py
then open http://localhost:1235
"""

from typing import Literal

import numpy as np
import plotly.graph_objects as go
from dash import Dash, Input, Output, callback, dcc, html

from dash_interact import Field, FnForm

app = Dash(__name__)


# --- the function whose signature drives the UI ---


def make_wave(
    amplitude: float = 1.0,
    frequency: float = 1.0,
    phase: float = 0.0,
    n_cycles: int = 3,
    color: Literal["blue", "red", "green", "orange"] = "blue",
    show_envelope: bool = False,
):
    """A simple sine wave with configurable parameters."""
    x = np.linspace(0, n_cycles * 2 * np.pi, 500)
    y = amplitude * np.sin(frequency * x + phase)

    traces = [go.Scatter(x=x, y=y, mode="lines", line={"color": color}, name="wave")]
    if show_envelope:
        traces += [
            go.Scatter(
                x=x,
                y=[amplitude] * len(x),
                mode="lines",
                line={"color": color, "dash": "dot", "width": 1},
                showlegend=False,
            ),
            go.Scatter(
                x=x,
                y=[-amplitude] * len(x),
                mode="lines",
                line={"color": color, "dash": "dot", "width": 1},
                showlegend=False,
            ),
        ]

    return go.Figure(
        traces,
        layout={"margin": {"t": 20, "b": 20}, "yaxis": {"range": [-2.5, 2.5]}},
    )


# --- build form controls from the function signature ---

cfg = FnForm(
    "wave",
    make_wave,
    amplitude=Field(ge=0.0, le=2.5, step=0.05),
    frequency=Field(ge=0.1, le=10.0, step=0.1),
    phase=Field(ge=0.0, le=6.28, step=0.05),
)

# --- layout ---

app.layout = html.Div(
    style={
        "display": "flex",
        "gap": "32px",
        "padding": "24px",
        "fontFamily": "sans-serif",
    },
    children=[
        html.Div(
            style={"width": "240px", "flexShrink": "0"},
            children=[
                html.H3("Parameters", style={"marginTop": 0}),
                cfg,
                html.Button(
                    "Apply",
                    id="apply",
                    n_clicks=0,
                    style={"marginTop": "16px", "width": "100%", "padding": "8px"},
                ),
            ],
        ),
        dcc.Graph(id="graph", style={"flex": "1"}),
    ],
)


# --- callback: read form → call function → update graph ---


@callback(Output("graph", "figure"), Input("apply", "n_clicks"), *cfg.states)
def update(_n_clicks, *values):
    return make_wave(**cfg.build_kwargs(values))


if __name__ == "__main__":
    app.run(debug=True, port=1235)
