# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Page — ordered collection of interact panels assembled into a Dash app.

Import as a module for a pyplot-style authoring experience::

    from dash_fn_interact import page

    page.H1("My App")

    @page.interact
    def sine_wave(amplitude: float = 1.0, frequency: float = 2.0):
        ...

    page.run(debug=True)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from dash import Dash, html

from dash_fn_interact.fn_interact import build_fn_panel
from dash_fn_interact.utils import _caller_name, _in_jupyter

_THIS_MODULES = {"dash_fn_interact.page"}


class _PageManager:
    """Mirrors matplotlib's ``Gcf`` — tracks the active :class:`Page`."""

    _page: Page | None = None
    _hook_registered: bool = False

    @classmethod
    def activate(cls, p: Page) -> None:
        cls._page = p
        cls._register_jupyter_hook()

    @classmethod
    def is_active(cls) -> bool:
        return cls._page is not None

    @classmethod
    def current(cls) -> Page:
        """Return the active page, creating one if needed (like ``plt.gcf()``)."""
        if cls._page is None:
            Page()  # __init__ calls activate
        return cls._page  # type: ignore[return-value]

    @classmethod
    def _register_jupyter_hook(cls) -> None:
        if cls._hook_registered:
            return
        cls._hook_registered = True
        try:
            from IPython import get_ipython  # noqa: PLC0415

            ip = get_ipython()
            if ip is not None and ip.__class__.__name__ == "ZMQInteractiveShell":

                def _auto_display() -> None:
                    if cls._page is not None and cls._page.children:
                        cls._page.run()
                        Page(max_width=cls._page._max_width, manual=cls._page._manual)

                ip.events.register("post_execute", _auto_display)
        except (ImportError, AttributeError):
            pass


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

        from dash_fn_interact import Page

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
        **kwargs: Any,
    ) -> html.Div | Callable:
        """Add an interact panel to this page."""
        _PageManager.activate(self)
        if fn is None:

            def decorator(f: Callable) -> html.Div:
                return self.interact(
                    f,
                    _id=_id,
                    _manual=_manual,
                    _loading=_loading,
                    _render=_render,
                    **kwargs,
                )

            return decorator
        panel = build_fn_panel(
            fn,
            _id=_id,
            _manual=self._manual if _manual is None else _manual,
            _loading=_loading,
            _render=_render,
            **kwargs,
        )
        self.children.append(panel)
        return panel

    def add(self, *components: Any) -> None:
        """Append arbitrary Dash components to this page."""
        _PageManager.activate(self)
        self.children.extend(components)

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
        html_cls = getattr(html, name, None)
        if html_cls is not None:

            def _factory(*args: Any, **kwargs: Any) -> Any:
                _PageManager.activate(self)
                comp = html_cls(*args, **kwargs)
                self.children.append(comp)
                return comp

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

        from dash_fn_interact import page, interact

        @interact
        def controls(): ...

        app.layout = html.Div([navbar, page.current(), footer])
    """
    return _PageManager.current()


def interact(
    fn: Callable | None = None,
    *,
    _id: str | None = None,
    _manual: bool | None = None,
    _loading: bool = True,
    _render: Callable[[Any], Any] | None = None,
    **kwargs: Any,
) -> html.Div | Callable:
    """Add an interact panel to the current page."""
    return _PageManager.current().interact(
        fn, _id=_id, _manual=_manual, _loading=_loading, _render=_render, **kwargs
    )


def add(*components: Any) -> None:
    """Append arbitrary Dash components to the current page."""
    _PageManager.current().add(*components)


def run(**kwargs: Any) -> None:
    """Build and run the current page as a Dash app."""
    _PageManager.current().run(**kwargs)


def __getattr__(name: str) -> Any:
    """Proxy ``html.*`` element constructors onto the current page.

    ``page.H1("title")`` is shorthand for ``page.add(html.H1("title"))``.
    """
    html_cls = getattr(html, name, None)
    if html_cls is not None:

        def _factory(*args: Any, **kwargs: Any) -> Any:
            comp = html_cls(*args, **kwargs)
            _PageManager.current().add(comp)
            return comp

        return _factory
    raise AttributeError(f"module 'dash_fn_interact.page' has no attribute {name!r}")
