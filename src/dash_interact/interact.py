# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""The interact family — three levels mirroring ipywidgets.

``interact``
    Fire and forget. Adds a panel to the current page.

``interactive``
    Returns an embeddable :class:`~dash_fn_forms.FnPanel` you place
    yourself.  Access ``.form`` and ``.output`` to split controls and output
    into separate layout regions.

``interactive_output``
    Fully decoupled. You supply a pre-built :class:`~dash_fn_forms.FnForm`;
    get back just the output ``html.Div``.  Use when controls live in a
    sidebar or modal and the output area is elsewhere in the layout::

        form = FnForm("plot", sine_wave)
        output = interactive_output(sine_wave, form)

        app.layout = html.Div([
            html.Div([form], className="sidebar"),
            html.Div([output], className="main"),
        ])
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from dash import Input, Output, callback, dcc, html
from dash_fn_forms._forms import FnForm
from dash_fn_forms._renderers import to_component
from dash_fn_forms.fn_interact import FnPanel, _cached_caller, build_fn_panel

from dash_interact._page_manager import _PageManager


def interact(
    fn: Callable | None = None,
    *,
    _id: str | None = None,
    _manual: bool | None = None,
    _loading: bool = True,
    _render: Callable[[Any], Any] | None = None,
    _cache: bool = False,
    _cache_maxsize: int = 128,
    **kwargs: Any,
) -> FnPanel | Callable:
    """Add an interact panel to the current page.

    Mirrors ipywidgets ``interact()`` — fire and forget.  The panel is
    appended to the active :class:`~dash_interact.Page` and the page is
    returned.

    Can be used as a plain call, a no-arg decorator, or a decorator with
    field shorthands::

        # plain call
        interact(sine_wave, amplitude=(0, 2, 0.1))

        # no-arg decorator
        @interact
        def sine_wave(amplitude: float = 1.0): ...

        # decorator with shorthands
        @interact(amplitude=(0, 2, 0.1))
        def sine_wave(amplitude: float = 1.0): ...
    """
    return _PageManager.current().interact(
        fn,
        _id=_id,
        _manual=_manual,
        _loading=_loading,
        _render=_render,
        _cache=_cache,
        _cache_maxsize=_cache_maxsize,
        **kwargs,
    )


def interactive(
    fn: Callable,
    *,
    _id: str | None = None,
    _manual: bool = False,
    _loading: bool = True,
    _render: Callable[[Any], Any] | None = None,
    _cache: bool = False,
    _cache_maxsize: int = 128,
    **kwargs: Any,
) -> FnPanel:
    """Build an embeddable interactive panel.

    Mirrors ipywidgets ``interactive()`` — returns a
    :class:`~dash_fn_forms.FnPanel` you place anywhere in the layout.
    Access ``.form`` and ``.output`` to put controls and output in different
    parts of the layout::

        panel = interactive(sine_wave, amplitude=(0, 2, 0.1))

        # as a unit
        app.layout = html.Div([panel])

        # split form and output
        app.layout = html.Div([
            html.Div([panel.form], className="sidebar"),
            html.Div([panel.output], className="main"),
        ])
    """
    return build_fn_panel(
        fn,
        _id=_id,
        _manual=_manual,
        _loading=_loading,
        _render=_render,
        _cache=_cache,
        _cache_maxsize=_cache_maxsize,
        **kwargs,
    )


def interactive_output(
    fn: Callable,
    form: FnForm,
    *,
    _loading: bool = True,
    _render: Callable[[Any], Any] | None = None,
    _cache: bool = False,
    _cache_maxsize: int = 128,
) -> dcc.Loading | html.Div:
    """Build a decoupled output area wired to an existing :class:`~dash_fn_forms.FnForm`.

    Mirrors ipywidgets ``interactive_output()`` — you supply the form (already
    placed in the layout), and get back just the output ``html.Div``.  The
    callback is registered internally; no additional wiring is needed::

        form = FnForm("plot", sine_wave, amplitude=(0, 2, 0.1))
        output = interactive_output(sine_wave, form)

        app.layout = html.Div([
            html.Div([form], className="sidebar"),
            html.Div([output], className="main"),
        ])

    Parameters
    ----------
    fn :
        The same callable used to build *form*.
    form :
        A pre-built :class:`~dash_fn_forms.FnForm` already present in the
        layout.
    _loading :
        Wrap the output area in ``dcc.Loading`` (default ``True``).
    _render :
        Optional converter applied to *fn*'s return value before display.
    """
    config_id = object.__getattribute__(form, "_config_id")
    output_id = f"_di_interactive_output_{config_id}"

    cfg_states = object.__getattribute__(form, "states")
    inputs = [Input(s.component_id, s.component_property) for s in cfg_states]

    _inner = html.Div(id=output_id, style={"marginTop": "16px"})
    output_div = dcc.Loading(_inner, type="circle") if _loading else _inner

    _call = _cached_caller(fn, form, _cache_maxsize) if _cache else None

    @callback(Output(output_id, "children"), *inputs)
    def _on_change(*values: Any) -> Any:
        try:
            result = _call(*values) if _call is not None else fn(**form.build_kwargs(values))
        except Exception as exc:
            return html.Pre(
                f"Error: {exc}",
                style={"color": "#d9534f", "fontFamily": "monospace"},
            )
        return to_component(result, _render)

    return output_div
