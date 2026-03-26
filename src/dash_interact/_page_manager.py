# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Internal singleton tracker for the active Page.

Mirrors matplotlib's ``Gcf``.  Kept in its own module so both ``page.py``
and ``html.py`` can import it without circular dependencies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dash_interact.page import Page


class _PageManager:
    """Tracks the active :class:`~dash_interact.Page` instance."""

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
            from dash_interact.page import Page  # noqa: PLC0415

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
                        from dash_interact.page import Page  # noqa: PLC0415

                        Page(
                            max_width=cls._page._max_width,
                            manual=cls._page._manual,
                        )

                ip.events.register("post_execute", _auto_display)
        except (ImportError, AttributeError):
            pass
