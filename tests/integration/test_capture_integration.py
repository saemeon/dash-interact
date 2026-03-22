# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Integration tests for dash-capture — live Dash app with Chrome.

These tests verify the full capture pipeline:
  JS capture (Plotly.toImage) → dcc.Store → Python callback → renderer

Run locally with:
  PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/integration/test_capture_integration.py -v
"""

from __future__ import annotations

import base64
import time

import dash
import plotly.graph_objects as go
from dash import dcc, html
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from dash_capture import capture_graph, plotly_strategy


def _make_figure():
    """Create a simple Plotly figure for testing."""
    return go.Figure(
        data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6], mode="markers"),
        layout=dict(title="Test Chart", width=400, height=300),
    )


def _find_button(dash_duo, label):
    """Find a button by visible text, regardless of display state."""
    for b in dash_duo.driver.find_elements(By.TAG_NAME, "button"):
        # Use textContent via JS to get text even for hidden elements
        text = dash_duo.driver.execute_script("return arguments[0].textContent", b)
        if text.strip() == label:
            return b
    return None


def _wait_for_png(dash_duo, timeout=45):
    """Wait for an <img> with a data:image/png src and return raw bytes."""
    WebDriverWait(dash_duo.driver, timeout).until(
        lambda d: any(
            (img.get_attribute("src") or "").startswith("data:image/png")
            for img in d.find_elements(By.TAG_NAME, "img")
        )
    )
    for img in dash_duo.driver.find_elements(By.TAG_NAME, "img"):
        src = img.get_attribute("src") or ""
        if src.startswith("data:image/png"):
            return base64.b64decode(src.split(",", 1)[1])
    raise AssertionError("PNG image disappeared")


# ── tests ────────────────────────────────────────────────────────────────


def test_capture_graph_renders_export_button(dash_duo):
    """capture_graph produces a visible Export button."""
    graph = dcc.Graph(id="t1-graph", figure=_make_figure())
    app = dash.Dash(__name__)
    exporter = capture_graph(graph, trigger="Export")
    app.layout = html.Div([graph, exporter])

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#t1-graph", timeout=10)

    btn = _find_button(dash_duo, "Export")
    assert btn is not None, "Export button not found"


def test_full_capture_pipeline(dash_duo):
    """Export → open wizard → auto-capture (no fields) → verify PNG in preview."""
    graph = dcc.Graph(id="t2-graph", figure=_make_figure())

    def passthrough(_target, _snapshot_img):
        _target.write(_snapshot_img())

    app = dash.Dash(__name__)
    exporter = capture_graph(graph, renderer=passthrough, trigger="Export")
    app.layout = html.Div([graph, exporter])

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#t2-graph", timeout=10)
    time.sleep(1)  # ensure Plotly.js is loaded

    # Click Export to open wizard — no fields so capture fires automatically
    export_btn = _find_button(dash_duo, "Export")
    export_btn.click()

    raw = _wait_for_png(dash_duo, timeout=45)
    assert raw[:4] == b"\x89PNG", f"Expected PNG header, got {raw[:4]!r}"


def test_capture_with_strip_patches(dash_duo):
    """Capture with strip_title=True produces valid PNG."""
    fig = _make_figure()
    fig.update_layout(title="BIG TITLE")
    graph = dcc.Graph(id="t3-graph", figure=fig)

    def passthrough(_target, _snapshot_img):
        _target.write(_snapshot_img())

    app = dash.Dash(__name__)
    exporter = capture_graph(
        graph, renderer=passthrough, trigger="Export",
        strip_title=True,
    )
    app.layout = html.Div([graph, exporter])

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#t3-graph", timeout=10)
    time.sleep(1)

    _find_button(dash_duo, "Export").click()

    raw = _wait_for_png(dash_duo, timeout=45)
    assert raw[:4] == b"\x89PNG"


def test_capture_with_explicit_strategy(dash_duo):
    """capture_graph with explicit plotly_strategy works."""
    graph = dcc.Graph(id="t4-graph", figure=_make_figure())

    def passthrough(_target, _snapshot_img):
        _target.write(_snapshot_img())

    app = dash.Dash(__name__)
    exporter = capture_graph(
        graph, renderer=passthrough, trigger="Export",
        strategy=plotly_strategy(strip_legend=True),
    )
    app.layout = html.Div([graph, exporter])

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#t4-graph", timeout=10)
    time.sleep(1)

    _find_button(dash_duo, "Export").click()

    raw = _wait_for_png(dash_duo, timeout=45)
    assert raw[:4] == b"\x89PNG"
