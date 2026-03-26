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


# ── Page serialization ────────────────────────────────────────────────────────


def test_page_to_plotly_json_returns_dict():
    p = _fresh_page()
    p.H1("Test")
    result = p.to_plotly_json()
    assert isinstance(result, dict)


def test_page_to_plotly_json_no_field_ref_leakage():
    """FieldRef objects must not appear in serialized layout."""
    from dash_fn_form import FnForm

    p = _fresh_page()

    def fn(x: float = 1.0):
        pass

    form = FnForm("_t_serial", fn)
    p.add(form)
    result = str(p.to_plotly_json())
    assert "FieldRef" not in result


def test_page_unknown_attr_during_serialization_raises():
    """__getattr__ with _in_serialization=True must raise AttributeError."""
    import pytest

    p = _fresh_page()
    object.__setattr__(p, "_in_serialization", True)
    with pytest.raises(AttributeError):
        _ = p.SomeAttr
    object.__setattr__(p, "_in_serialization", False)


# ── Page options ──────────────────────────────────────────────────────────────


def test_page_max_width_in_style():
    p = _fresh_page(max_width=1200)
    assert "1200px" in str(p.style)


def test_page_manual_default_false():
    p = _fresh_page()
    assert p._manual is False


def test_page_manual_true_propagates_to_interact():
    """Page(manual=True) makes interact panels use manual mode by default."""
    from dash_fn_form.fn_interact import FnPanel

    p = _fresh_page(manual=True)

    def fn(x: float = 1.0):
        pass

    panel = p.interact(fn, _id="_t_manual_prop")
    assert isinstance(panel, FnPanel)
    # The panel should contain a button (manual mode)
    json_str = str(panel.to_plotly_json())
    assert "Button" in json_str


def test_page_interact_explicit_manual_overrides_page_default():
    """_manual kwarg overrides Page.manual."""

    p = _fresh_page(manual=True)

    def fn(x: float = 1.0):
        pass

    panel = p.interact(fn, _id="_t_manual_override", _manual=False)
    json_str = str(panel.to_plotly_json())
    assert "Button" not in json_str


def test_page_build_app_with_name():
    p = _fresh_page()
    app = p.build_app(name="MyTestApp")
    assert isinstance(app, Dash)


# ── _PageManager ─────────────────────────────────────────────────────────────


def test_page_manager_is_active_false_initially():
    _PageManager._page = None
    assert not _PageManager.is_active()


def test_page_manager_is_active_after_page_creation():
    _fresh_page()
    assert _PageManager.is_active()


def test_page_manager_activate_switches_page():
    p1 = _fresh_page()
    p2 = Page()
    _PageManager.activate(p1)
    assert _PageManager.current() is p1
    _PageManager.activate(p2)
    assert _PageManager.current() is p2
