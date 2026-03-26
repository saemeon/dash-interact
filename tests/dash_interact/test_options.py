"""Tests for interact.options() factory."""

from dash_fn_form.fn_interact import FnPanel

from dash_interact.interact import interact


def test_options_returns_callable():
    factory = interact.options(_manual=True)
    assert callable(factory)


def test_options_as_decorator():
    from dash_interact._page_manager import _PageManager

    _PageManager._page = None

    @interact.options(_id="_t_opts_deco", _manual=True)
    def fn(x: float = 1.0):
        pass

    assert isinstance(fn, FnPanel)


def test_options_with_auto_slider():
    from dash_interact._page_manager import _PageManager

    _PageManager._page = None

    @interact.options(_id="_t_opts_auto", _auto_slider=True)
    def fn(x: float = 2.0):
        pass

    assert isinstance(fn, FnPanel)
