# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Page — ordered collection of interact panels assembled into a Dash app.

Import as a module for a pyplot-style authoring experience::

    from dash_interact import page

    page.H1("My App")

    @page.interact
    def sine_wave(amplitude: float = 1.0, frequency: float = 2.0):
        ...

    page.run(debug=True)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from dash import Dash, html
from dash_fn_forms.fn_interact import FnPanel, build_fn_panel
from dash_fn_forms.utils import _caller_name, _in_jupyter

import dash_interact.html as _html_factories
from dash_interact._page_manager import _PageManager
from dash_interact.html import *  # noqa: F401, F403 — exposes page.H1, page.P, etc.
from dash_interact.interact import interact as interact  # noqa: F401

_THIS_MODULES = {"dash_interact.page"}


class Page(html.Div):
    """Ordered collection of interact panels — itself a Dash ``html.Div``.

    Being a ``Div`` subclass means a ``Page`` can be used directly as
    ``app.layout`` or nested inside any other Dash component.

    Parameters
    ----------
    max_width :
        CSS ``max-width`` in pixels.  Defaults to 960.
    manual :
        Default ``_manual`` value for every :meth:`interact` call on this page.
    children :
        Initial child components.

    Examples
    --------
    ::

        from dash_interact import Page

        p = Page(manual=True)
        p.H1("My App")

        @p.interact
        def sine_wave(amplitude: float = 1.0, frequency: float = 2.0):
            ...

        p.run(debug=True)
    """

    def __init__(
        self,
        *,
        max_width: int = 960,
        manual: bool = False,
        children: list[Any] | None = None,
    ) -> None:
        self._max_width = max_width
        self._manual = manual
        super().__init__(
            children=list(children) if children is not None else [],
            style={
                "fontFamily": "sans-serif",
                "padding": "32px",
                "maxWidth": f"{max_width}px",
                "backgroundColor": "#ffffff",
                "color": "#1a1a1a",
            },
        )
        _PageManager.activate(self)

    def interact(  # noqa: F811
        self,
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
        """Add an interact panel to this page."""
        _PageManager.activate(self)
        if fn is None:

            def decorator(f: Callable) -> FnPanel:
                return self.interact(  # type: ignore[return-value]
                    f,
                    _id=_id,
                    _manual=_manual,
                    _loading=_loading,
                    _render=_render,
                    _cache=_cache,
                    _cache_maxsize=_cache_maxsize,
                    **kwargs,
                )

            return decorator
        panel = build_fn_panel(
            fn,
            _id=_id,
            _manual=self._manual if _manual is None else _manual,
            _loading=_loading,
            _render=_render,
            _cache=_cache,
            _cache_maxsize=_cache_maxsize,
            **kwargs,
        )
        cast("list[Any]", self.children).append(panel)
        return panel

    def add(self, *components: Any) -> None:
        """Append arbitrary Dash components to this page."""
        _PageManager.activate(self)
        cast("list[Any]", self.children).extend(components)

    def build_app(self, *, name: str | None = None) -> Dash:
        """Assemble and return a configured :class:`~dash.Dash` app."""
        app = Dash(name or _caller_name(_THIS_MODULES))
        app.layout = self
        return app

    def _ipython_display_(self, **_: Any) -> None:
        """Auto-display when this page is the last expression in a cell."""
        self.run()

    def run(self, *, name: str | None = None, **kwargs: Any) -> None:
        """Build the app and start the Dash development server."""
        if _in_jupyter():
            kwargs.setdefault("jupyter_mode", "inline")
        self.build_app(name=name or _caller_name(_THIS_MODULES)).run(**kwargs)

    def __getattr__(self, name: str) -> Any:
        """Proxy ``html.*`` element constructors as page-appending factories.

        ``p.H1("title")`` is shorthand for ``p.add(html.H1("title"))``.
        """
        d = object.__getattribute__(self, "__dict__")
        if d.get("_in_serialization"):
            raise AttributeError(name)
        factory = getattr(_html_factories, name, None)
        if factory is not None:

            def _factory(*args: Any, **kwargs: Any) -> Any:
                _PageManager.activate(self)
                return factory(*args, **kwargs)

            return _factory
        raise AttributeError(f"Page has no attribute {name!r}")

    def to_plotly_json(self) -> dict:
        object.__setattr__(self, "_in_serialization", True)
        try:
            return super().to_plotly_json()
        finally:
            object.__setattr__(self, "_in_serialization", False)


def current() -> Page:
    """Return the active :class:`Page`, creating one if needed.

    Use this to retrieve the current page when embedding it into a larger
    Dash layout after building panels with the module-level API::

        from dash_interact import page, interact

        @interact
        def controls(): ...

        app.layout = html.Div([navbar, page.current(), footer])
    """
    return _PageManager.current()


def add(*components: Any) -> None:
    """Append arbitrary Dash components to the current page."""
    _PageManager.current().add(*components)


def run(**kwargs: Any) -> None:
    """Build and run the current page as a Dash app."""
    _PageManager.current().run(**kwargs)
