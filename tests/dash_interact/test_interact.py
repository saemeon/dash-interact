# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Tests for interact, interactive, interactive_output."""

from __future__ import annotations

from dash import html
from dash_fn_form import FnForm
from dash_fn_form.fn_interact import FnPanel

from dash_interact import interact, interactive, interactive_output
from dash_interact._page_manager import _PageManager


def _reset_page():
    _PageManager._page = None


# ── interact ──────────────────────────────────────────────────────────────────


def test_interact_returns_fn_panel():
    _reset_page()

    def fn(x: float = 1.0):
        pass

    panel = interact(fn, _id="_t_interact_basic")
    assert isinstance(panel, FnPanel)


def test_interact_adds_to_page():
    _reset_page()

    def fn(x: float = 1.0):
        pass

    page = _PageManager.current()
    before = len(page.children)
    interact(fn, _id="_t_interact_adds")
    assert len(page.children) == before + 1


def test_interact_decorator_no_args():
    _reset_page()

    @interact
    def fn_deco(x: float = 1.0):
        pass

    # decorator replaces fn with the panel
    assert isinstance(fn_deco, FnPanel)


def test_interact_decorator_with_kwargs():
    _reset_page()

    @interact(x=(0.0, 5.0, 0.5), _id="_t_interact_deco_kwargs")
    def fn_kwargs(x: float = 1.0):
        pass

    assert isinstance(fn_kwargs, FnPanel)


# ── interactive ───────────────────────────────────────────────────────────────


def test_interactive_returns_fn_panel():
    panel = interactive(lambda x=1.0: None, _id="_t_interactive_basic")
    assert isinstance(panel, FnPanel)


def test_interactive_does_not_add_to_page():
    _reset_page()
    page = _PageManager.current()
    before = len(page.children)

    def fn(x: float = 1.0):
        pass

    interactive(fn, _id="_t_interactive_no_page")
    assert len(page.children) == before


def test_interactive_has_form_and_output():
    def fn(x: float = 1.0, y: int = 2):
        pass

    panel = interactive(fn, _id="_t_interactive_props")
    assert isinstance(panel.form, FnForm)
    assert isinstance(panel.output, html.Div)


# ── interactive_output ────────────────────────────────────────────────────────


def test_interactive_output_returns_div():
    def fn(x: float = 1.0):
        pass

    form = FnForm("_t_io_form", fn)
    out = interactive_output(fn, form, _loading=False)
    assert isinstance(out, html.Div)


def test_interactive_output_with_loading_returns_loading():
    from dash import dcc

    def fn(x: float = 1.0):
        pass

    form = FnForm("_t_io_loading", fn)
    out = interactive_output(fn, form, _loading=True)
    assert isinstance(out, dcc.Loading)


# ── caching params ────────────────────────────────────────────────────────────


def test_interactive_cache_true_builds():
    def fn(x: float = 1.0):
        pass

    panel = interactive(fn, _id="_t_interactive_cache", _cache=True)
    assert isinstance(panel, FnPanel)


def test_interactive_cache_maxsize_builds():
    def fn(x: float = 1.0):
        pass

    panel = interactive(fn, _id="_t_interactive_maxsize", _cache=True, _cache_maxsize=32)
    assert isinstance(panel, FnPanel)


def test_interactive_output_cache_true_builds():
    def fn(x: float = 1.0):
        pass

    form = FnForm("_t_io_cache", fn)
    out = interactive_output(fn, form, _loading=False, _cache=True)
    assert isinstance(out, html.Div)
