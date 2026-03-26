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
from dash_fn_form.fn_interact import FnPanel, build_fn_panel
from dash_fn_form.utils import _caller_name, _in_jupyter

import dash_interact.html as _html_factories
from dash_interact._page_manager import _PageManager
from dash_interact.html import *  # noqa: F401, F403 — exposes page.H1, page.P, etc.
from dash_interact.interact import interact as interact  # noqa: F401

_THIS_MODULES = {"dash_interact.page"}


# ── Layout context managers ──────────────────────────────────────────────────


class _Slot:
    """Redirect page.add() into a temporary list."""

    def __init__(self, target: list[Any], page: Page) -> None:
        self._target = target
        self._page = page
        self._prev: list[Any] | None = None

    def __enter__(self) -> _Slot:
        self._prev = self._page._add_target
        self._page._add_target = self._target
        return self

    def __exit__(self, *exc: object) -> None:
        self._page._add_target = self._prev  # type: ignore[assignment]


class _ColumnContext:
    """Context manager for page.columns(n)."""

    def __init__(self, n_cols: int, page: Page, gap: str = "24px") -> None:
        self._columns: list[list[Any]] = [[] for _ in range(n_cols)]
        self._page = page
        self._gap = gap

    def __getitem__(self, idx: int) -> _Slot:
        return _Slot(self._columns[idx], self._page)

    def __enter__(self) -> _ColumnContext:
        return self

    def __exit__(self, *exc: object) -> None:
        col_children = [html.Div(col, style={"flex": "1"}) for col in self._columns]
        row = html.Div(col_children, style={"display": "flex", "gap": self._gap})
        self._page.add(row)


class _SidebarContext:
    """Context manager for page.sidebar()."""

    def __init__(self, page: Page, width: int = 300) -> None:
        self._page = page
        self._width = width
        self._side: list[Any] = []
        self._main: list[Any] = []

    def __enter__(self) -> tuple[_Slot, _Slot]:
        return _Slot(self._side, self._page), _Slot(self._main, self._page)

    def __exit__(self, *exc: object) -> None:
        sidebar_div = html.Div(
            self._side,
            style={
                "width": f"{self._width}px",
                "flexShrink": "0",
            },
        )
        main_div = html.Div(self._main, style={"flex": "1"})
        row = html.Div(
            [sidebar_div, main_div],
            style={
                "display": "flex",
                "gap": "24px",
            },
        )
        self._page.add(row)


class _TabContext:
    """A single tab slot within _TabsContext."""

    def __init__(self, name: str, tabs_ctx: _TabsContext) -> None:
        self._name = name
        self._children: list[Any] = []
        self._tabs_ctx = tabs_ctx

    def __enter__(self) -> _TabContext:
        self._tabs_ctx._page._add_target = self._children
        return self

    def __exit__(self, *exc: object) -> None:
        self._tabs_ctx._tabs.append((self._name, self._children))
        self._tabs_ctx._page._add_target = self._tabs_ctx._prev_target


class _TabsContext:
    """Context manager for page.tabs()."""

    def __init__(self, page: Page) -> None:
        self._page = page
        self._tabs: list[tuple[str, list[Any]]] = []
        self._prev_target = page._add_target

    def tab(self, name: str) -> _TabContext:
        return _TabContext(name, self)

    def __enter__(self) -> _TabsContext:
        return self

    def __exit__(self, *exc: object) -> None:
        from dash import dcc

        tab_children = [
            dcc.Tab(label=name, children=list(children))
            for name, children in self._tabs
        ]
        self._page._add_target = self._prev_target
        self._page.add(dcc.Tabs(tab_children))


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
        auto_slider: bool = False,
        children: list[Any] | None = None,
    ) -> None:
        self._max_width = max_width
        self._manual = manual
        self._auto_slider = auto_slider
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
        self._add_target = self.children
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
        _auto_slider: bool | None = None,
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
                    _auto_slider=_auto_slider,
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
            _auto_slider=self._auto_slider if _auto_slider is None else _auto_slider,
            **kwargs,
        )
        cast("list[Any]", self._add_target).append(panel)
        return panel

    def add(self, *components: Any) -> None:
        """Append arbitrary Dash components to this page."""
        _PageManager.activate(self)
        cast("list[Any]", self._add_target).extend(components)

    def columns(self, *args: Any, **kwargs: Any) -> _ColumnContext | None:
        """Create a multi-column layout.

        Context manager usage::

            with page.columns(2) as cols:
                with cols[0]:
                    page.H1("Left")
                with cols[1]:
                    page.H1("Right")

        Shorthand usage::

            page.columns([left_panel], [right_panel])
        """
        if len(args) == 1 and isinstance(args[0], int):
            return _ColumnContext(args[0], self, **kwargs)
        # Shorthand: pass lists of components directly
        gap = kwargs.get("gap", "24px")
        col_children = [html.Div(list(col), style={"flex": "1"}) for col in args]
        row = html.Div(col_children, style={"display": "flex", "gap": gap})
        self.add(row)
        return None

    def sidebar(self, *, width: int = 300, **kwargs: Any) -> _SidebarContext:
        """Create a sidebar + main layout.

        Context manager usage::

            with page.sidebar(width=300) as (side, main):
                with side:
                    page.add(form)
                with main:
                    page.add(output)
        """
        return _SidebarContext(self, width=width)

    def tabs(self, *args: Any) -> _TabsContext | None:
        """Create a tabbed layout.

        Context manager usage::

            with page.tabs() as t:
                with t.tab("Analysis"):
                    page.interact(analysis_fn)
                with t.tab("Settings"):
                    page.interact(settings_fn)

        Shorthand usage::

            page.tabs(("Tab1", [panel1]), ("Tab2", [panel2]))
        """
        if not args:
            return _TabsContext(self)
        # Shorthand
        from dash import dcc

        tab_children = [
            dcc.Tab(label=name, children=list(children)) for name, children in args
        ]
        self.add(dcc.Tabs(tab_children))
        return None

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


def columns(*args: Any, **kwargs: Any) -> _ColumnContext | None:
    """Create a multi-column layout on the current page."""
    return _PageManager.current().columns(*args, **kwargs)


def sidebar(**kwargs: Any) -> _SidebarContext:
    """Create a sidebar + main layout on the current page."""
    return _PageManager.current().sidebar(**kwargs)


def tabs(*args: Any) -> _TabsContext | None:
    """Create a tabbed layout on the current page."""
    return _PageManager.current().tabs(*args)
