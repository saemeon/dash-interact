# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Output rendering pipeline for interact().

Analogous to matplotlib's unit converter registry: a global type → renderer
mapping is checked before the built-in converter chain.  Register third-party
types once at app startup; all interact() calls pick it up automatically.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from dash import dcc, html

# Global type → renderer registry.
# Keys are types; values are callables (result) -> Dash component.
_RENDERERS: dict[type, Callable] = {}


def register_renderer(type_: type, renderer: Callable[[Any], Any]) -> None:
    """Register a custom renderer for a Python type.

    The renderer is called with the return value of the function whenever
    ``interact()`` produces a result of the registered type (or a subclass).
    This avoids passing ``_render=`` on every ``interact()`` call.

    Analogous to matplotlib's unit converter registry — register once at app
    startup, applies everywhere.

    Later registrations for the same type overwrite earlier ones.  For subclass
    disambiguation, register the more-specific type after the base type; the
    registry is checked in insertion order and the first ``isinstance`` match wins.

    Example::

        import pandas as pd
        from dash import dash_table
        from dash_fn_interact import register_renderer

        register_renderer(
            pd.DataFrame,
            lambda df: dash_table.DataTable(
                data=df.to_dict("records"),
                columns=[{"name": c, "id": c} for c in df.columns],
            ),
        )

        # all interact() calls that return a DataFrame now use this renderer
        panel = interact(get_data)
    """
    _RENDERERS[type_] = renderer


def to_component(result: Any, renderer: Callable[[Any], Any] | None) -> Any:
    """Convert *result* to a Dash-renderable value.

    Resolution order:

    1. Explicit *renderer* callable (highest priority).
    2. Global registry — first ``isinstance`` match wins.
    3. Built-in: ``go.Figure`` → ``dcc.Graph``, Dash component → as-is,
       anything else → ``html.Pre(repr(...))``.
    """
    if result is None:
        return None

    if renderer is not None:
        try:
            return renderer(result)
        except Exception as exc:
            return _error(f"Render error: {exc}")

    # Global registry
    for type_, registered in _RENDERERS.items():
        if isinstance(result, type_):
            try:
                return registered(result)
            except Exception as exc:
                return _error(f"Render error: {exc}")

    # Built-in: Plotly Figure → dcc.Graph
    try:
        import plotly.graph_objects as go  # noqa: PLC0415
        if isinstance(result, go.Figure):
            return dcc.Graph(figure=result)
    except ImportError:
        pass

    # Built-in: Dash component → as-is
    if hasattr(result, "_type"):
        return result

    # Fallback: repr
    return html.Pre(
        repr(result),
        style={"fontFamily": "monospace", "whiteSpace": "pre-wrap"},
    )


def _error(msg: str) -> html.Pre:
    return html.Pre(msg, style={"color": "#d9534f", "fontFamily": "monospace"})
