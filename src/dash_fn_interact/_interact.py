# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""interact() — ipywidgets-style one-liner for Plotly Dash."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from dash import Input, Output, State, callback, dcc, html

from dash_fn_interact._forms import FnForm


def interact(
    fn: Callable | None = None,
    *,
    _manual: bool = False,
    **kwargs: Any,
) -> html.Div | Callable:
    """Build a self-contained interactive panel from a typed callable.

    The Dash equivalent of ``ipywidgets.interact()``.  Introspects *fn*'s
    signature, renders a form, and registers a callback that calls *fn* with
    the current field values whenever they change.

    ``interact`` can be used as a plain function call **or** as a decorator.
    This allows you to define a function and interact with it in a single shot.
    As the examples below show, ``interact`` also works with functions that
    have multiple arguments.

    Parameters
    ----------
    fn :
        Callable whose parameters define the form fields.  It is also called
        with the resolved ``**kwargs`` to produce the output shown below the
        form.  Return a Dash component, a ``plotly.graph_objects.Figure``, or
        any value (rendered via ``repr``).

        When omitted, ``interact`` returns a decorator — useful for the
        ``@interact(...)`` form with per-field shorthands.
    _manual :
        ``False`` (default) — callback fires on every field change (live
        update).  ``True`` — an *Apply* button is added; callback fires on
        click only.
    **kwargs :
        Per-field shorthands passed directly to :func:`FnForm` — same
        syntax as ``FnForm`` keyword arguments (``Field``, tuples,
        ``range``, lists, etc.).

    Returns
    -------
    html.Div
        Panel containing the form, an optional *Apply* button, and an output
        area.  Embed directly in ``app.layout``.
    Callable
        When *fn* is omitted, returns a decorator that accepts the function.

    Notes
    -----
    ``config_id`` is derived from ``fn.__name__``.  Calling ``interact()``
    twice with the same function will trigger a duplicate-ID warning — use
    :func:`FnForm` directly if you need two panels for the same function.

    Examples
    --------
    Plain function call::

        panel = interact(make_wave, amplitude=(0, 2, 0.01))
        app.layout = html.Div([panel])

    No-argument decorator — interact is applied when the function is defined::

        @interact
        def make_wave(amplitude: float = 1.0, freq: float = 1.0):
            ...

        app.layout = html.Div([make_wave])   # make_wave is now the panel

    Decorator with per-field shorthands::

        @interact(amplitude=(0, 2, 0.01), freq=(0.5, 10, 0.5))
        def make_wave(amplitude: float = 1.0, freq: float = 1.0):
            ...

        app.layout = html.Div([make_wave])
    """
    if fn is None:
        # Called as @interact(...) with kwargs — return a decorator
        def decorator(f: Callable) -> html.Div:
            return interact(f, _manual=_manual, **kwargs)
        return decorator

    config_id = fn.__name__
    output_id = f"_dft_interact_out_{config_id}"

    cfg: FnForm = FnForm(config_id, fn, **kwargs)

    output_div = html.Div(id=output_id, style={"marginTop": "16px"})

    if _manual:
        btn_id = f"_dft_interact_btn_{config_id}"
        panel = html.Div(
            [
                cfg,
                html.Button(
                    "Apply",
                    id=btn_id,
                    n_clicks=0,
                    style={
                        "marginTop": "8px",
                        "padding": "6px 16px",
                        "cursor": "pointer",
                    },
                ),
                output_div,
            ]
        )

        @callback(
            Output(output_id, "children"),
            Input(btn_id, "n_clicks"),
            *cfg.states,
            prevent_initial_call=True,
        )
        def _on_apply(_n: int, *values: Any) -> Any:
            return _render(fn, cfg.build_kwargs(values))

    else:
        cfg_states: list[State] = object.__getattribute__(cfg, "states")
        inputs = [Input(s.component_id, s.component_property) for s in cfg_states]
        panel = html.Div([cfg, output_div])

        @callback(Output(output_id, "children"), *inputs)
        def _on_change(*values: Any) -> Any:
            return _render(fn, cfg.build_kwargs(values))

    return panel


def _render(fn: Callable, kwargs: dict) -> Any:
    """Call fn(**kwargs) and convert the result to Dash-renderable children."""
    try:
        result = fn(**kwargs)
    except Exception as exc:
        return html.Pre(
            f"Error: {exc}",
            style={"color": "#d9534f", "fontFamily": "monospace"},
        )

    if result is None:
        return None

    # Plotly Figure → dcc.Graph
    try:
        import plotly.graph_objects as go  # noqa: PLC0415

        if isinstance(result, go.Figure):
            return dcc.Graph(figure=result)
    except ImportError:
        pass

    # Dash component → as-is
    if hasattr(result, "_type"):
        return result

    # Anything else → repr
    return html.Pre(
        repr(result),
        style={"fontFamily": "monospace", "whiteSpace": "pre-wrap"},
    )
