# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Tests for Page and the page module singleton."""

from __future__ import annotations

from dash import Dash, html
from dash_interact import Page, page
from dash_interact._page_manager import _PageManager


def _fresh_page(**kwargs) -> Page:
    _PageManager._page = None
    return Page(**kwargs)


# ── Page construction ─────────────────────────────────────────────────────────


def test_page_is_html_div_subclass():
    p = _fresh_page()
    assert isinstance(p, html.Div)


def test_page_starts_empty():
    p = _fresh_page()
    assert p.children == []


def test_page_activates_page_manager():
    p = _fresh_page()
    assert _PageManager.current() is p


# ── Page.add and HTML shorthands ──────────────────────────────────────────────


def test_page_add_appends_component():
    p = _fresh_page()
    comp = html.P("hello")
    p.add(comp)
    assert comp in p.children


def test_page_html_shorthand_appends():
    p = _fresh_page()
    comp = p.H1("My Title")
    assert comp in p.children
    assert isinstance(comp, html.H1)


def test_page_html_shorthand_returns_component():
    p = _fresh_page()
    result = p.P("text")
    assert isinstance(result, html.P)
    assert result.children == "text"


def test_page_unknown_attr_raises():
    import pytest

    p = _fresh_page()
    with pytest.raises(AttributeError):
        p.NotARealHtmlElement()


# ── Page.interact ─────────────────────────────────────────────────────────────


def test_page_interact_appends_panel():
    p = _fresh_page()

    def fn(x: float = 1.0):
        pass

    p.interact(fn, _id="_t_page_interact")
    assert len(p.children) == 1


def test_page_interact_decorator():
    p = _fresh_page()

    @p.interact(_id="_t_page_interact_deco")
    def fn(x: float = 1.0):
        pass

    assert len(p.children) == 1


# ── Page.build_app ────────────────────────────────────────────────────────────


def test_build_app_returns_dash():
    p = _fresh_page()
    app = p.build_app()
    assert isinstance(app, Dash)


def test_build_app_sets_layout():
    p = _fresh_page()
    app = p.build_app()
    assert app.layout is p


# ── module-level page API ─────────────────────────────────────────────────────


def test_page_module_current_creates_page():
    _PageManager._page = None
    p = page.current()
    assert isinstance(p, Page)


def test_page_module_add_appends():
    _PageManager._page = None
    comp = html.Hr()
    page.add(comp)
    assert comp in page.current().children


def test_page_module_h1_shorthand():
    _PageManager._page = None
    comp = page.H1("title")
    assert isinstance(comp, html.H1)
    assert comp in page.current().children
