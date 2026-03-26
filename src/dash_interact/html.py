# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Page-appending wrappers for all ``dash.html`` elements.

Each name here is a factory that creates the corresponding Dash component
and appends it to the current page::

    from dash_interact import html

    html.H1("My App")   # creates html.H1 and adds it to the current page
    html.Hr()
    html.P("Some text")

Also accessible directly from ``dash_interact``::

    import dash_interact as di

    di.H1("My App")
    di.html.H1("My App")   # same thing
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from dash import html as _dash_html

from dash_interact._page_manager import _PageManager

# Explicit imports for static analysis (Pylance / mypy).
# At runtime these are overwritten by the factory loop below.
if TYPE_CHECKING:
    from dash.html import (  # noqa: F401
        H1,
        H2,
        H3,
        H4,
        H5,
        H6,
        A,
        Abbr,
        Acronym,
        Address,
        Area,
        Article,
        Aside,
        Audio,
        B,
        Base,
        Basefont,
        Bdi,
        Bdo,
        Big,
        Blink,
        Blockquote,
        Br,
        Button,
        Canvas,
        Caption,
        Center,
        Cite,
        Code,
        Col,
        Colgroup,
        Content,
        Data,
        Datalist,
        Dd,
        Del,
        Details,
        Dfn,
        Dialog,
        Div,
        Dl,
        Dt,
        Em,
        Embed,
        Fieldset,
        Figcaption,
        Figure,
        Font,
        Footer,
        Form,
        Frame,
        Frameset,
        Header,
        Hgroup,
        Hr,
        I,
        Iframe,
        Img,
        Ins,
        Kbd,
        Keygen,
        Label,
        Legend,
        Li,
        Link,
        Main,
        MapEl,
        Mark,
        Marquee,
        Meta,
        Meter,
        Nav,
        Nobr,
        Noscript,
        ObjectEl,
        Ol,
        Optgroup,
        Option,
        Output,
        P,
        Param,
        Picture,
        Plaintext,
        Pre,
        Progress,
        Q,
        Rb,
        Rp,
        Rt,
        Rtc,
        Ruby,
        S,
        Samp,
        Script,
        Section,
        Select,
        Shadow,
        Slot,
        Small,
        Source,
        Spacer,
        Span,
        Strike,
        Strong,
        Sub,
        Summary,
        Sup,
        Table,
        Tbody,
        Td,
        Template,
        Textarea,
        Tfoot,
        Th,
        Thead,
        Time,
        Title,
        Tr,
        Track,
        U,
        Ul,
        Var,
        Video,
        Wbr,
        Xmp,
    )


def _make(cls: type) -> Callable:
    def _factory(*args: Any, **kwargs: Any) -> Any:
        comp = cls(*args, **kwargs)
        _PageManager.current().add(comp)
        return comp

    _factory.__name__ = cls.__name__
    _factory.__qualname__ = cls.__qualname__
    _factory.__doc__ = (
        f"Create ``html.{cls.__name__}`` and append it to the current page."
    )
    return _factory


for _name, _cls in vars(_dash_html).items():
    if isinstance(_cls, type) and not _name.startswith("_"):
        globals()[_name] = _make(_cls)

del _name, _cls
