# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Tests for FnForm: type inference, build_kwargs, Field options, validation."""

from __future__ import annotations

import pathlib
from datetime import date, datetime
from enum import Enum
from typing import Annotated, Literal


class _Mode(Enum):
    fast = "fast"
    slow = "slow"

import pytest
from dash import dcc

from dash_fn_interact import Field, FnForm, fixed


# ── helpers ───────────────────────────────────────────────────────────────────


def _form(fn, **kwargs):
    """Create a FnForm with a unique ID derived from the function name."""
    uid = f"_t_{fn.__name__}_{id(fn)}"
    return FnForm(uid, fn, **kwargs)


def _all_components(component):
    """Recursively yield all Dash components from a component tree."""
    yield component
    children = getattr(component, "children", None)
    if children is None:
        return
    if not isinstance(children, list):
        children = [children]
    for child in children:
        if hasattr(child, "_type"):  # any Dash component, with or without children
            yield from _all_components(child)


def _find(component, cls):
    """Return the first component of type cls in the tree, or None."""
    return next((c for c in _all_components(component) if isinstance(c, cls)), None)


# ── build_kwargs ──────────────────────────────────────────────────────────────


def test_build_kwargs_basic():
    def fn(x: float = 1.0, y: int = 2, name: str = "hi"):
        pass

    form = _form(fn)
    result = form.build_kwargs((3.0, 5, "hello"))
    assert result == {"x": 3.0, "y": 5, "name": "hello"}


def test_build_kwargs_coerces_types():
    def fn(x: float = 1.0, y: int = 2):
        pass

    form = _form(fn)
    # Dash sends numbers as numbers — coercion should handle string-like inputs too
    result = form.build_kwargs(("2.5", "7"))
    assert result == {"x": 2.5, "y": 7}
    assert isinstance(result["x"], float)
    assert isinstance(result["y"], int)


def test_build_kwargs_bool_checked():
    def fn(flag: bool = False):
        pass

    form = _form(fn)
    # dcc.Checklist returns a non-empty list when checked
    result = form.build_kwargs((["flag"],))
    assert result["flag"] is True


def test_build_kwargs_bool_unchecked():
    def fn(flag: bool = True):
        pass

    form = _form(fn)
    result = form.build_kwargs(([],))
    assert result["flag"] is False


def test_build_kwargs_optional_none():
    def fn(x: float | None = None):
        pass

    form = _form(fn)
    assert form.build_kwargs((None,))["x"] is None
    assert form.build_kwargs(("",))["x"] is None


def test_build_kwargs_optional_with_value():
    def fn(x: float | None = None):
        pass

    form = _form(fn)
    assert form.build_kwargs((3.14,))["x"] == pytest.approx(3.14)


def test_build_kwargs_literal():
    def fn(color: Literal["red", "blue"] = "red"):
        pass

    form = _form(fn)
    assert form.build_kwargs(("blue",)) == {"color": "blue"}


def test_build_kwargs_enum():
    def fn(mode: _Mode = _Mode.fast):
        pass

    form = _form(fn)
    assert form.build_kwargs(("slow",)) == {"mode": _Mode.slow}


def test_build_kwargs_list():
    def fn(values: list[float] | None = None):
        pass

    form = _form(fn)
    result = form.build_kwargs(("1.0, 2.5, 3.0",))
    assert result["values"] == pytest.approx([1.0, 2.5, 3.0])


def test_build_kwargs_path():
    def fn(p: pathlib.Path = pathlib.Path("/tmp")):
        pass

    form = _form(fn)
    result = form.build_kwargs(("/tmp/out.png",))
    assert result["p"] == pathlib.Path("/tmp/out.png")


def test_build_kwargs_date():
    def fn(d: date | None = None):
        pass

    form = _form(fn)
    result = form.build_kwargs(("2024-06-15",))
    assert result["d"] == date(2024, 6, 15)


def test_build_kwargs_datetime():
    def fn(ts: datetime | None = None):
        pass

    form = _form(fn)
    # datetime fields consume two values: date + time
    result = form.build_kwargs(("2024-06-15", "09:30"))
    assert result["ts"] == datetime(2024, 6, 15, 9, 30)


# ── Field options ─────────────────────────────────────────────────────────────


def test_exclude_removes_field_from_states():
    def fn(x: float = 1.0, y: int = 2):
        pass

    form = _form(fn, _exclude=["y"])
    assert len(form.states) == 1
    result = form.build_kwargs((5.0,))
    # excluded fields are not present in build_kwargs output
    assert result == {"x": 5.0}


def test_fixed_value_bypasses_widget():
    def fn(x: float = 1.0, y: int = 2):
        pass

    form = _form(fn, y=fixed(99))
    # y is not in states — only x
    assert len(form.states) == 1
    result = form.build_kwargs((3.0,))
    assert result == {"x": 3.0, "y": 99}


def test_tuple_shorthand_creates_bounded_input():
    def fn(n: int = 10):
        pass

    form = _form(fn, n=(1, 100, 5))
    inp = _find(form, dcc.Input)
    assert inp is not None
    assert inp.min == 1
    assert inp.max == 100
    assert inp.step == 5


def test_field_widget_slider_creates_slider():
    def fn(x: float = 1.0):
        pass

    form = _form(fn, x=Field(ge=0.0, le=10.0, step=0.5, widget="slider"))
    slider = _find(form, dcc.Slider)
    assert slider is not None
    assert slider.min == 0.0
    assert slider.max == 10.0
    assert slider.step == 0.5


def test_field_persist_adds_store():
    from dash import dcc as _dcc

    def fn(x: float = 1.0):
        pass

    form = _form(fn, x=Field(ge=0.0, le=5.0, step=0.1, persist=True))
    store = _find(form, _dcc.Store)
    assert store is not None


def test_literal_produces_dropdown():
    def fn(color: Literal["red", "blue", "green"] = "red"):
        pass

    form = _form(fn)
    dropdown = _find(form, dcc.Dropdown)
    assert dropdown is not None
    assert set(dropdown.options) == {"red", "blue", "green"}


def test_annotated_field_label():
    def fn(
        x: Annotated[float, Field(label="My Label")] = 1.0,
    ):
        pass

    form = _form(fn)
    # The label text appears somewhere in the form's children
    form_json = str(form.to_plotly_json())
    assert "My Label" in form_json


# ── validation ────────────────────────────────────────────────────────────────


def test_build_kwargs_validated_passes():
    def fn(x: float, y: int = 2):
        pass

    form = _form(fn)
    kwargs, errors = form.build_kwargs_validated((3.0, 5))
    assert errors == {}
    assert kwargs == {"x": 3.0, "y": 5}


def test_build_kwargs_validated_required_missing():
    def fn(x: float):
        pass

    form = _form(fn)
    kwargs, errors = form.build_kwargs_validated((None,))
    assert "x" in errors


def test_build_kwargs_validated_custom_validator():
    def fn(
        username: Annotated[str, lambda v: None if len(v) >= 3 else "Min 3 chars"],
    ):
        pass

    form = _form(fn)
    _, errors = form.build_kwargs_validated(("ab",))
    assert "username" in errors

    _, errors = form.build_kwargs_validated(("alice",))
    assert errors == {}
