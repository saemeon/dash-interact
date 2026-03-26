"""Tests for auto-slider feature."""
from dash_fn_form.fn_interact import FnPanel, _auto_slider_range, build_fn_panel


def test_auto_slider_range_positive_float():
    mn, mx, step = _auto_slider_range(1.0, "float")
    assert mn == 0.0
    assert mx == 3.0
    assert step == 0.1


def test_auto_slider_range_negative_float():
    mn, mx, step = _auto_slider_range(-2.0, "float")
    assert mn == -6.0
    assert mx == 0.0


def test_auto_slider_range_zero_float():
    mn, mx, step = _auto_slider_range(0.0, "float")
    assert mn == -1.0
    assert mx == 1.0


def test_auto_slider_range_positive_int():
    mn, mx, step = _auto_slider_range(5, "int")
    assert mn == 0
    assert mx == 15
    assert step == 1


def test_auto_slider_range_zero_int():
    mn, mx, step = _auto_slider_range(0, "int")
    assert mn == -10
    assert mx == 10


def test_build_fn_panel_auto_slider():
    def fn(x: float = 1.0, y: int = 5):
        pass
    panel = build_fn_panel(fn, _id="_t_auto_slider", _auto_slider=True)
    assert isinstance(panel, FnPanel)


def test_build_fn_panel_auto_slider_respects_explicit():
    """User-provided shorthand takes precedence over auto-slider."""
    def fn(x: float = 1.0):
        pass
    panel = build_fn_panel(fn, _id="_t_auto_explicit", _auto_slider=True, x=(0, 10, 0.5))
    assert isinstance(panel, FnPanel)


def test_build_fn_panel_auto_slider_false_no_slider():
    """With auto_slider=False, numeric defaults stay as number inputs."""
    def fn(x: float = 1.0):
        pass
    panel = build_fn_panel(fn, _id="_t_no_auto", _auto_slider=False)
    assert isinstance(panel, FnPanel)
