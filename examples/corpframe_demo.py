"""corpframe Dash demo — run with: uv run python examples/corpframe_demo.py

One-click corporate chart export: capture → strip Plotly decorations →
add corporate header (title, subtitle) and footer (footnotes, sources).
"""

import dash
import plotly.graph_objects as go
from corpframe.dash import corporate_capture_graph
from dash import dcc, html

# --- sample figure ---
fig = go.Figure(
    data=[
        go.Bar(
            x=["Q1", "Q2", "Q3", "Q4"],
            y=[120, 145, 132, 178],
            name="2025",
            marker_color="#1a1a2e",
        ),
        go.Bar(
            x=["Q1", "Q2", "Q3", "Q4"],
            y=[135, 160, 148, 195],
            name="2026",
            marker_color="#e94560",
        ),
    ],
    layout=dict(
        title="Quarterly Revenue (CHF M)",
        xaxis_title="",
        yaxis_title="Revenue (CHF M)",
        barmode="group",
        width=700,
        height=400,
    ),
)

graph = dcc.Graph(id="revenue", figure=fig)

# --- app ---
app = dash.Dash(__name__)

app.layout = html.Div(
    style={
        "maxWidth": "900px",
        "margin": "0 auto",
        "padding": "20px",
        "fontFamily": "system-ui, sans-serif",
    },
    children=[
        html.H2("corpframe — Corporate Chart Export"),
        html.P(
            "Click the button to open a wizard with pre-filled corporate "
            "framing fields (title, subtitle, footnotes, sources). "
            "Generate a preview, then download or copy."
        ),
        html.Hr(),
        graph,
        html.Br(),
        html.H4("Pre-filled corporate export"),
        html.P(
            "Title, subtitle, footnotes, and sources are pre-filled. "
            "Edit them in the wizard before exporting."
        ),
        corporate_capture_graph(
            graph,
            title="Quarterly Revenue",
            subtitle="Comparison 2025 vs 2026, all regions",
            footnotes="Preliminary figures, subject to audit",
            sources="Source: Internal ERP, March 2026",
        ),
        html.Br(),
        html.Hr(),
        html.H4("Minimal — just a title"),
        corporate_capture_graph(
            "revenue",
            title="Revenue Overview",
            trigger="Export (minimal)",
        ),
        html.Br(),
        html.Hr(),
        html.H4("Full strip — no Plotly decorations"),
        corporate_capture_graph(
            "revenue",
            title="Clean Export",
            subtitle="All Plotly decorations removed",
            sources="Internal",
            strip_title=True,
            strip_legend=True,
            strip_margin=True,
            trigger="Export (fully stripped)",
        ),
    ],
)

if __name__ == "__main__":
    app.run(debug=False)
