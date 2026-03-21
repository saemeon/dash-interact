# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Tests for the to_component rendering pipeline."""

from __future__ import annotations

import pytest
from dash import dcc, html

from dash_fn_interact._renderers import to_component, register_renderer


# ── built-ins ─────────────────────────────────────────────────────────────────


def test_none_returns_none():
    assert to_component(None, None) is None


def test_str_returns_markdown():
    result = to_component("hello **world**", None)
    assert isinstance(result, dcc.Markdown)


def test_int_returns_p():
    result = to_component(42, None)
    assert isinstance(result, html.P)


def test_float_returns_p():
    result = to_component(3.14, None)
    assert isinstance(result, html.P)


def test_bool_returns_p():
    result = to_component(True, None)
    assert isinstance(result, html.P)


def test_dash_component_returned_as_is():
    comp = html.Div("content")
    result = to_component(comp, None)
    assert result is comp


def test_plotly_figure_returns_graph():
    import plotly.graph_objects as go

    fig = go.Figure()
    result = to_component(fig, None)
    assert isinstance(result, dcc.Graph)


def test_matplotlib_figure_returns_img():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    ax.plot([1, 2], [3, 4])
    result = to_component(fig, None)
    plt.close(fig)
    assert isinstance(result, html.Img)
    assert result.src.startswith("data:image/png;base64,")


def test_pandas_dataframe_returns_table():
    import pandas as pd
    from dash import dash_table

    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    result = to_component(df, None)
    assert isinstance(result, dash_table.DataTable)


def test_unknown_type_returns_pre():
    class Weird:
        def __repr__(self):
            return "weird!"

    result = to_component(Weird(), None)
    assert isinstance(result, html.Pre)


# ── explicit renderer ─────────────────────────────────────────────────────────


def test_explicit_renderer_takes_priority():
    custom = html.Span("custom")
    result = to_component("any string", lambda _: custom)
    assert result is custom


def test_explicit_renderer_error_shows_error_component():
    def bad_renderer(_):
        raise ValueError("oops")

    result = to_component("x", bad_renderer)
    # Should return some error component, not raise
    assert result is not None


# ── global registry ───────────────────────────────────────────────────────────


def test_register_renderer_used_for_type():
    class MyType:
        pass

    register_renderer(MyType, lambda _: html.Span("registered"))
    result = to_component(MyType(), None)
    assert isinstance(result, html.Span)
    assert result.children == "registered"


def test_explicit_renderer_overrides_registry():
    class MyType:
        pass

    register_renderer(MyType, lambda _: html.Span("from registry"))
    override = html.B("override")
    result = to_component(MyType(), lambda _: override)
    assert result is override


def test_registry_checked_before_builtins():
    # Register a renderer for str — should beat the built-in str → Markdown
    register_renderer(str, lambda s: html.H1(s))
    result = to_component("hi", None)
    assert isinstance(result, html.H1)
