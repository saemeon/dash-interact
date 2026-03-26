# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""dash-interact — pyplot-style convenience layer for Dash.

Re-exports the full dash-fn-forms engine plus the page/singleton API::

    from dash_interact import page, interact, Page

    page.H1("My App")

    @page.interact
    def sine_wave(amplitude: float = 1.0, frequency: float = 2.0):
        ...

    page.run(debug=True)
"""

# Re-export dash-fn-forms engine for users who install only dash-interact
from dash_fn_forms import (
    Field,
    FieldHook,
    FieldMaker,
    FieldRef,
    FnForm,
    FnPanel,
    Form,
    FromComponent,
    build_fn_panel,
    field_id,
    fixed,
    make_dbc_field,
    make_dcc_field,
    make_dmc_field,
    register_renderer,
)

from dash_interact import html, page
from dash_interact.html import *  # noqa: F401, F403 — exposes di.H1, di.P, etc.
from dash_interact.interact import interact, interactive, interactive_output
from dash_interact.page import Page, add, current, run

__all__ = [
    # page API
    "Page",
    "add",
    "current",
    "html",
    "interact",
    "interactive",
    "interactive_output",
    "page",
    "run",
    # engine re-exports
    "Field",
    "FieldHook",
    "FieldMaker",
    "FieldRef",
    "FnPanel",
    "FnForm",
    "Form",
    "FromComponent",
    "build_fn_panel",
    "field_id",
    "fixed",
    "make_dbc_field",
    "make_dcc_field",
    "make_dmc_field",
    "register_renderer",
]
