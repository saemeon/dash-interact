from datetime import date, datetime
from typing import Literal

import matplotlib.pyplot as plt
import plotly.graph_objects as go
from dash import Dash, dcc, html

from s5ndt.mpl_export import mpl_export_button

app = Dash(__name__)

# --- figure ---

fig = go.Figure(go.Scatter(x=[1, 2, 3, 4, 5], y=[4, 2, 5, 1, 3], mode="markers"))
fig.update_layout(title="All-types example")


# --- renderer covering all supported field types ---

def full_renderer(
    _fig_data,
    # str
    title: str = "My Plot",
    # int / float
    dpi: int = 100,
    alpha: float = 0.8,
    # bool
    show_grid: bool = True,
    # date only
    report_date: date | None = None,
    # date + time
    as_of: datetime | None = None,
    # Literal (dropdown)
    marker_style: Literal["o", "s", "^", "x"] = "o",
    # list[T]
    y_ticks: list[float] | None = None,
    # tuple[T, ...]
    xlim: tuple[float, float] | None = None,
):
    x = _fig_data["data"][0]["x"]
    y = _fig_data["data"][0]["y"]

    fig, ax = plt.subplots(dpi=dpi)
    ax.scatter(x, y, alpha=alpha, marker=marker_style)
    ax.set_title(title)
    ax.grid(show_grid)

    if xlim:
        ax.set_xlim(*xlim)
    if y_ticks:
        ax.set_yticks(y_ticks)
    if report_date:
        fig.text(0, 0, str(report_date), fontsize=7)
    if as_of:
        ax.set_xlabel(f"as of {as_of.strftime('%Y-%m-%d %H:%M')}")

    return fig


# --- layout ---

export_btn = mpl_export_button(graph_id="main-graph", renderer=full_renderer)

app.layout = html.Div([
    dcc.Graph(id="main-graph", figure=fig),
    export_btn,
])

if __name__ == "__main__":
    app.run(debug=True)
