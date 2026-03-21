# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Build self-contained interactive panels from typed callables."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from dash import Input, Output, State, callback, dcc, html

from dash_fn_interact._forms import FnForm
from dash_fn_interact._renderers import to_component


def build_fn_panel(
    fn: Callable,
    *,
    _id: str | None = None,
    _manual: bool = False,
    _loading: bool = True,
    _render: Callable[[Any], Any] | None = None,
    **kwargs: Any,
) -> html.Div:
    """Build and return a self-contained interactive panel.

    Registers Dash callbacks and returns an ``html.Div``.  Has no knowledge
    of pages; the caller is responsible for placing the panel in a layout.

    Parameters
    ----------
    fn :
        Callable whose parameters define the form fields.
    _id :
        Explicit component-ID namespace.  Defaults to ``fn.__name__``.
        Pass a unique string when two panels wrap functions with the same name
        to prevent Dash component-ID collisions.
    _manual :
        ``False`` — live update on every field change.
        ``True`` — *Apply* button; callback fires on click only.
    _loading :
        Wrap the output area in ``dcc.Loading`` (default ``True``).
    _render :
        Optional converter applied to *fn*'s return value before display.
    **kwargs :
        Per-field shorthands forwarded to :class:`FnForm`.
    """
    config_id = _id or fn.__name__
    output_id = f"_dft_interact_out_{config_id}"

    cfg: FnForm = FnForm(config_id, fn, **kwargs)

    _inner = html.Div(id=output_id, style={"marginTop": "16px"})
    output_div = dcc.Loading(_inner, type="circle") if _loading else _inner

    if _manual:
        btn_id = f"_dft_interact_btn_{config_id}"
        panel = html.Div(
            [
                cfg,
                html.Button(
                    "Apply",
                    id=btn_id,
                    n_clicks=0,
                    style={"marginTop": "8px", "padding": "6px 16px", "cursor": "pointer"},
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
            try:
                result = fn(**cfg.build_kwargs(values))
            except Exception as exc:
                return html.Pre(f"Error: {exc}", style={"color": "#d9534f", "fontFamily": "monospace"})
            return to_component(result, _render)

    else:
        cfg_states: list[State] = object.__getattribute__(cfg, "states")
        inputs = [Input(s.component_id, s.component_property) for s in cfg_states]
        panel = html.Div([cfg, output_div])

        @callback(Output(output_id, "children"), *inputs)
        def _on_change(*values: Any) -> Any:
            try:
                result = fn(**cfg.build_kwargs(values))
            except Exception as exc:
                return html.Pre(f"Error: {exc}", style={"color": "#d9534f", "fontFamily": "monospace"})
            return to_component(result, _render)

    return panel
