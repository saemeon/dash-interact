# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Tests for build_fn_panel and FnPanel."""

from __future__ import annotations

from dash import dcc, html

from dash_fn_interact import FnForm
from dash_fn_interact.fn_interact import FnPanel, build_fn_panel


def _panel(fn, **kwargs):
    uid = f"_t_{fn.__name__}_{id(fn)}"
    return build_fn_panel(fn, _id=uid, **kwargs)


# ── FnPanel structure ─────────────────────────────────────────────────────────


def test_build_fn_panel_returns_fn_panel():
    def fn(x: float = 1.0):
        pass

    panel = _panel(fn)
    assert isinstance(panel, FnPanel)


def test_fn_panel_form_is_fn_form():
    def fn(x: float = 1.0):
        pass

    panel = _panel(fn)
    assert isinstance(panel.form, FnForm)


def test_fn_panel_output_is_div():
    def fn(x: float = 1.0):
        pass

    panel = _panel(fn)
    assert isinstance(panel.output, html.Div)


def test_fn_panel_output_has_id():
    def fn(x: float = 1.0):
        pass

    panel = _panel(fn)
    assert panel.output.id is not None


def test_fn_panel_form_and_output_are_distinct():
    def fn(x: float = 1.0):
        pass

    panel = _panel(fn)
    assert panel.form is not panel.output
    assert type(panel.form).__name__ == "FnForm"
    assert panel.output.id is not None


# ── loading wrapper ───────────────────────────────────────────────────────────


def test_loading_true_wraps_output():
    def fn(x: float = 1.0):
        pass

    panel = _panel(fn, _loading=True)

    def _has_loading(comp):
        if isinstance(comp, dcc.Loading):
            return True
        for child in (getattr(comp, "children", None) or []):
            if isinstance(child, list):
                if any(_has_loading(c) for c in child):
                    return True
            elif hasattr(child, "_type") and _has_loading(child):
                return True
        return False

    assert _has_loading(panel)


def test_loading_false_no_loading_wrapper():
    def fn(x: float = 1.0):
        pass

    panel = _panel(fn, _loading=False)

    def _has_loading(comp):
        if isinstance(comp, dcc.Loading):
            return True
        for child in (getattr(comp, "children", None) or []):
            if isinstance(child, list):
                if any(_has_loading(c) for c in child):
                    return True
            elif hasattr(child, "_type") and _has_loading(child):
                return True
        return False

    assert not _has_loading(panel)


# ── manual mode ───────────────────────────────────────────────────────────────


def test_manual_mode_has_apply_button():
    def fn(x: float = 1.0):
        pass

    panel = _panel(fn, _manual=True)

    def _has_button(comp):
        if isinstance(comp, html.Button):
            return True
        for child in (getattr(comp, "children", None) or []):
            if isinstance(child, list):
                if any(_has_button(c) for c in child):
                    return True
            elif hasattr(child, "_type") and _has_button(child):
                return True
        return False

    assert _has_button(panel)


def test_auto_mode_has_no_apply_button():
    def fn(x: float = 1.0):
        pass

    panel = _panel(fn, _manual=False)

    def _has_button(comp):
        if isinstance(comp, html.Button):
            return True
        for child in (getattr(comp, "children", None) or []):
            if isinstance(child, list):
                if any(_has_button(c) for c in child):
                    return True
            elif hasattr(child, "_type") and _has_button(child):
                return True
        return False

    assert not _has_button(panel)
