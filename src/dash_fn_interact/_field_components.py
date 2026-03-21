# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Field component functions for dash-fn-interact.

Pass ``_field_components`` to :func:`~dash_fn_interact.build_config` as a
string shorthand or any callable matching :class:`FieldMaker`.  When omitted,
``"auto"`` is used: :func:`make_dmc_field` if ``dash-mantine-components`` is
installed, otherwise :func:`make_dcc_field` as a fallback.

String shorthands::

    cfg = build_config("id", fn, _field_components="dmc")   # Mantine
    cfg = build_config("id", fn, _field_components="dbc")   # Bootstrap
    cfg = build_config("id", fn, _field_components="dcc")   # plain dcc (explicit fallback)
    cfg = build_config("id", fn, _field_components="auto")  # DMC if available, else dcc

Custom callable (must match :class:`FieldMaker` signature)::

    def my_field(config_id, f, spec, fid):
        ...

    cfg = build_config("id", fn, _field_components=my_field)
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Literal, Protocol, get_args, get_origin

from dash import dcc, html

from dash_fn_interact._spec import Field


def _list_literal_args(f: Any) -> tuple | None:
    """Return the Literal values if *f* is a ``list[Literal[...]]`` field, else ``None``."""
    if f.type == "list" and f.args and get_origin(f.args[0]) is Literal:
        return get_args(f.args[0])
    return None


class FieldMaker(Protocol):
    """Callable protocol for field component factories.

    Any callable with this signature can be passed as ``_field_components``
    to :func:`~dash_fn_interact.build_config`.
    """

    def __call__(self, config_id: str, f: Any, spec: Field, fid: str) -> Any:
        """Return a Dash component for *f* with *fid* as its ``id``.

        Parameters
        ----------
        config_id :
            The config namespace (used for composite types like datetime).
        f :
            The ``_Field`` descriptor (type, default, args, optional, spec).
        spec :
            The resolved ``Field`` for this field.
        fid :
            The Dash component ID to assign.
        """
        ...


def _debounce(spec: Field) -> bool:
    """Resolve effective debounce setting (default: True)."""
    return True if spec.debounce is None else spec.debounce


def _persist(spec: Field) -> dict:
    """Return persistence kwargs when ``spec.persist`` is True, else empty dict."""
    if not spec.persist:
        return {}
    return {"persistence": True, "persistence_type": "session"}


def _resolve_field_maker(value: Any) -> FieldMaker:
    """Resolve a ``_field_components`` argument to a :class:`FieldMaker`.

    * ``None`` / ``"auto"`` → :func:`make_dmc_field` if available, else :func:`make_dcc_field`
    * ``"dcc"`` → :func:`make_dcc_field`
    * ``"dmc"`` → :func:`make_dmc_field`
    * ``"dbc"`` → :func:`make_dbc_field`
    * callable → returned as-is
    """
    if value is None or value == "auto":
        try:
            import dash_mantine_components  # noqa: F401

            return make_dmc_field
        except ImportError:
            return make_dcc_field
    if value == "dcc":
        return make_dcc_field
    if value == "dmc":
        return make_dmc_field
    if value == "dbc":
        return make_dbc_field
    if callable(value):
        return value
    raise ValueError(
        f"Unknown _field_components value {value!r}. "
        "Use 'dcc', 'dmc', 'dbc', 'auto', or a callable matching FieldMaker."
    )


def make_dcc_field(config_id: str, f: Any, spec: Field, fid: str) -> Any:
    """Build a field component using plain ``dcc``/``html`` (no extra dependencies).

    Used automatically when ``dash-mantine-components`` is not installed.

    | Python type | Component |
    |---|---|
    | `str` / `path` | `dcc.Input(type="text")` |
    | `int` / `float` | `dcc.Input(type="number")` |
    | `bool` | `dcc.Checklist` |
    | `Literal` / `Enum` | `dcc.Dropdown` |
    | `list` / `tuple` | `dcc.Input(type="text")` — comma-separated |
    | `dict` | `dcc.Textarea` — JSON |
    | `date` | `dcc.DatePickerSingle` |
    | `datetime` | `dcc.DatePickerSingle` + `dcc.Input` (HH:MM) |
    """
    if f.type == "bool":
        return dcc.Checklist(
            id=fid,
            options=[{"label": "", "value": f.name}],
            value=[f.name] if f.default else [],
            style=spec.style,
            className=spec.class_name,
            **_persist(spec),
        )
    if f.type == "date":
        return dcc.DatePickerSingle(
            id=fid,
            date=f.default.isoformat() if isinstance(f.default, date) else None,
            style=spec.style,
            className=spec.class_name,
            **_persist(spec),
        )
    if f.type == "datetime":
        default_date = (
            f.default.date().isoformat()
            if isinstance(f.default, datetime)
            else None
        )
        default_time = (
            f.default.strftime("%H:%M") if isinstance(f.default, datetime) else None
        )
        time_fid = f"_dft_field_{config_id}_{f.name}_time"
        return html.Div(
            style={"display": "flex", "gap": "8px", "alignItems": "center"},
            children=[
                dcc.DatePickerSingle(
                    id=fid,
                    date=default_date,
                    style=spec.style,
                    className=spec.class_name,
                ),
                dcc.Input(
                    id=time_fid,
                    type="text",
                    placeholder="HH:MM",
                    value=default_time,
                    debounce=_debounce(spec),
                    style={"width": "70px", **(spec.style or {})},
                    className=spec.class_name,
                ),
            ],
        )
    if f.type in ("int", "float"):
        step: Any = spec.step
        if step is None:
            step = 1 if f.type == "int" else "any"
        if spec.widget == "slider" and spec.min is not None and spec.max is not None:
            slider_step = spec.step if spec.step not in (None, "any") else (1 if f.type == "int" else 0.1)
            slider = dcc.Slider(
                id=fid,
                min=spec.min,
                max=spec.max,
                step=slider_step,
                value=f.default if f.default is not None else spec.min,
                tooltip={"placement": "bottom", "always_visible": False},
                className=spec.class_name,
                **_persist(spec),
            )
            return html.Div(slider, style=spec.style) if spec.style else slider
        zero: int | float = 0 if f.type == "int" else 0.0
        bounds: dict = {}
        if spec.min is not None:
            bounds["min"] = spec.min
        if spec.max is not None:
            bounds["max"] = spec.max
        return dcc.Input(
            id=fid,
            type="number",
            step=step,
            value=f.default if f.default is not None else zero,
            debounce=_debounce(spec),
            style=spec.style,
            className=spec.class_name,
            **bounds,
            **_persist(spec),
        )
    if f.type in ("list", "tuple"):
        lit_args = _list_literal_args(f)
        if lit_args is not None:
            default = f.default if isinstance(f.default, list) else []
            return dcc.Dropdown(
                id=fid,
                options=list(lit_args),
                value=default,
                multi=True,
                style=spec.style,
                className=spec.class_name,
                **_persist(spec),
            )
        if f.type == "tuple":
            placeholder = ", ".join(t.__name__ for t in f.args)
        else:
            elem = f.args[0].__name__ if f.args else "value"
            placeholder = f"{elem}, ..."
        return dcc.Input(
            id=fid,
            type="text",
            value=", ".join(str(v) for v in f.default) if f.default else "",
            placeholder=placeholder,
            debounce=_debounce(spec),
            style=spec.style,
            className=spec.class_name,
            **_persist(spec),
        )
    if f.type == "literal":
        return dcc.Dropdown(
            id=fid,
            options=list(f.args),
            value=f.default if f.default in f.args else f.args[0],
            style=spec.style,
            className=spec.class_name,
            **_persist(spec),
        )
    if f.type == "enum":
        enum_cls = f.args[0]
        members = list(enum_cls)
        default_name = (
            f.default.name if isinstance(f.default, enum_cls) else members[0].name
        )
        return dcc.Dropdown(
            id=fid,
            options=[{"label": m.name, "value": m.name} for m in members],
            value=default_name,
            style=spec.style,
            className=spec.class_name,
            **_persist(spec),
        )
    if f.type == "dict":
        default_str = json.dumps(f.default, indent=2) if f.default else ""
        return dcc.Textarea(
            id=fid,
            value=default_str,
            placeholder='{"key": "value"}',
            style={
                "fontFamily": "monospace",
                "width": "100%",
                **(spec.style or {}),
            },
            className=spec.class_name,
            **_persist(spec),
        )
    if f.type == "path":
        return dcc.Input(
            id=fid,
            type="text",
            value=str(f.default) if f.default is not None else "",
            placeholder="/path/to/file",
            debounce=_debounce(spec),
            minLength=spec.min_length,
            maxLength=spec.max_length,
            style=spec.style,
            className=spec.class_name,
            **_persist(spec),
        )
    # str (fallback)
    return dcc.Input(
        id=fid,
        type="text",
        value=str(f.default) if f.default is not None else "",
        placeholder="",
        debounce=_debounce(spec),
        minLength=spec.min_length,
        maxLength=spec.max_length,
        style=spec.style,
        className=spec.class_name,
        **_persist(spec),
    )


def make_dmc_field(config_id: str, f: Any, spec: Field, fid: str) -> Any:
    """Build a field component using `dash-mantine-components <https://www.dash-mantine.com/>`_.

    Requires ``pip install dash-mantine-components``.

    | Python type | Component |
    |---|---|
    | `str` / `path` / `list` / `tuple` | `dmc.TextInput` |
    | `int` / `float` | `dmc.NumberInput` |
    | `bool` | `dcc.Checklist` *(fallback — preserves `value` prop)* |
    | `Literal` / `Enum` | `dmc.Select` |
    | `dict` | `dmc.Textarea` — JSON |
    | `date` / `datetime` | `dcc.DatePickerSingle` *(fallback — DMC date API differs)* |
    """
    try:
        import dash_mantine_components as dmc
    except ImportError as exc:
        raise ImportError(
            "dash-mantine-components is required for make_dmc_field. "
            "Install it with: pip install dash-mantine-components"
        ) from exc

    # date / datetime / bool — fall back to make_dcc_field for prop compatibility
    if f.type in ("date", "datetime", "bool"):
        return make_dcc_field(config_id, f, spec, fid)

    if f.type in ("int", "float"):
        step = spec.step
        if step is None:
            step = 1 if f.type == "int" else 0.01
        if spec.widget == "slider" and spec.min is not None and spec.max is not None:
            slider_step = spec.step if spec.step not in (None, "any") else (1 if f.type == "int" else 0.1)
            return dmc.Slider(
                id=fid,
                min=spec.min,
                max=spec.max,
                step=slider_step,
                value=f.default if f.default is not None else spec.min,
                style=spec.style,
                className=spec.class_name,
            )
        zero_dmc: int | float = 0 if f.type == "int" else 0.0
        bounds_dmc: dict = {}
        if spec.min is not None:
            bounds_dmc["min"] = spec.min
        if spec.max is not None:
            bounds_dmc["max"] = spec.max
        return dmc.NumberInput(
            id=fid,
            value=f.default if f.default is not None else zero_dmc,
            step=step,
            style=spec.style,
            className=spec.class_name,
            **bounds_dmc,
        )

    if f.type == "literal":
        # dmc.Select requires string values; fall back for non-string literals
        if all(isinstance(v, str) for v in f.args):
            return dmc.Select(
                id=fid,
                data=list(f.args),
                value=f.default if f.default in f.args else f.args[0],
                style=spec.style,
                className=spec.class_name,
            )
        return make_dcc_field(config_id, f, spec, fid)

    if f.type == "enum":
        enum_cls = f.args[0]
        members = list(enum_cls)
        default_name = (
            f.default.name if isinstance(f.default, enum_cls) else members[0].name
        )
        return dmc.Select(
            id=fid,
            data=[{"label": m.name, "value": m.name} for m in members],
            value=default_name,
            style=spec.style,
            className=spec.class_name,
        )

    if f.type == "list":
        lit_args = _list_literal_args(f)
        if lit_args is not None and all(isinstance(v, str) for v in lit_args):
            default = f.default if isinstance(f.default, list) else []
            return dmc.MultiSelect(
                id=fid,
                data=list(lit_args),
                value=default,
                style=spec.style,
                className=spec.class_name,
            )
        # non-literal list or non-string literals — fall through to TextInput

    if f.type == "dict":
        default_str = json.dumps(f.default, indent=2) if f.default else ""
        return dmc.Textarea(
            id=fid,
            value=default_str,
            placeholder='{"key": "value"}',
            style={
                "fontFamily": "monospace",
                "width": "100%",
                **(spec.style or {}),
            },
            className=spec.class_name,
        )

    # str, path, list, tuple
    # dmc.TextInput does not expose Dash's persistence prop — no _persist() here
    return dmc.TextInput(
        id=fid,
        value=str(f.default) if f.default is not None else "",
        style=spec.style,
        className=spec.class_name,
    )


def make_dbc_field(config_id: str, f: Any, spec: Field, fid: str) -> Any:
    """Build a field component using `dash-bootstrap-components <https://dash-bootstrap-components.opensource.faculty.ai/>`_.

    Requires ``pip install dash-bootstrap-components``.

    | Python type | Component |
    |---|---|
    | `str` / `path` | `dbc.Input(type="text")` |
    | `int` / `float` | `dbc.Input(type="number")` |
    | `bool` | `dbc.Checklist` |
    | `Literal` / `Enum` | `dbc.Select` |
    | `list` / `tuple` | `dbc.Input(type="text")` — comma-separated |
    | `dict` | `dbc.Textarea` — JSON |
    | `date` / `datetime` | `dcc.DatePickerSingle` *(fallback — DBC has no date picker)* |
    """
    try:
        import dash_bootstrap_components as dbc
    except ImportError as exc:
        raise ImportError(
            "dash-bootstrap-components is required for make_dbc_field. "
            "Install it with: pip install dash-bootstrap-components"
        ) from exc

    # date / datetime — fall back to make_dcc_field (DBC has no date picker)
    if f.type in ("date", "datetime"):
        return make_dcc_field(config_id, f, spec, fid)

    if f.type == "bool":
        return dbc.Checklist(
            id=fid,
            options=[{"label": "", "value": f.name}],
            value=[f.name] if f.default else [],
            style=spec.style,
            className=spec.class_name,
            **_persist(spec),
        )

    if f.type in ("int", "float"):
        step = spec.step
        if step is None:
            step = 1 if f.type == "int" else None
        if spec.widget == "slider" and spec.min is not None and spec.max is not None:
            slider_step = spec.step if spec.step not in (None, "any") else (1 if f.type == "int" else 0.1)
            slider = dcc.Slider(
                id=fid,
                min=spec.min,
                max=spec.max,
                step=slider_step,
                value=f.default if f.default is not None else spec.min,
                tooltip={"placement": "bottom", "always_visible": False},
                className=spec.class_name,
                **_persist(spec),
            )
            return html.Div(slider, style=spec.style) if spec.style else slider
        zero_dbc: int | float = 0 if f.type == "int" else 0.0
        bounds_dbc: dict = {}
        if spec.min is not None:
            bounds_dbc["min"] = spec.min
        if spec.max is not None:
            bounds_dbc["max"] = spec.max
        return dbc.Input(
            id=fid,
            type="number",
            value=f.default if f.default is not None else zero_dbc,
            step=step,
            debounce=_debounce(spec),
            style=spec.style,
            className=spec.class_name,
            **bounds_dbc,
            **_persist(spec),
        )

    if f.type == "literal":
        options = [{"label": str(v), "value": v} for v in f.args]
        return dbc.Select(
            id=fid,
            options=options,
            value=f.default if f.default in f.args else f.args[0],
            style=spec.style,
            className=spec.class_name,
            **_persist(spec),
        )

    if f.type == "enum":
        enum_cls = f.args[0]
        members = list(enum_cls)
        default_name = (
            f.default.name if isinstance(f.default, enum_cls) else members[0].name
        )
        return dbc.Select(
            id=fid,
            options=[{"label": m.name, "value": m.name} for m in members],
            value=default_name,
            style=spec.style,
            className=spec.class_name,
            **_persist(spec),
        )

    if f.type == "dict":
        default_str = json.dumps(f.default, indent=2) if f.default else ""
        return dbc.Textarea(
            id=fid,
            value=default_str,
            placeholder='{"key": "value"}',
            style={
                "fontFamily": "monospace",
                "width": "100%",
                **(spec.style or {}),
            },
            className=spec.class_name,
            **_persist(spec),
        )

    if f.type in ("list", "tuple"):
        lit_args = _list_literal_args(f)
        if lit_args is not None:
            # DBC has no multi-select; fall back to dcc.Dropdown(multi=True)
            default = f.default if isinstance(f.default, list) else []
            return dcc.Dropdown(
                id=fid,
                options=list(lit_args),
                value=default,
                multi=True,
                style=spec.style,
                className=spec.class_name,
                **_persist(spec),
            )
        if f.type == "tuple":
            placeholder = ", ".join(t.__name__ for t in f.args)
        else:
            elem = f.args[0].__name__ if f.args else "value"
            placeholder = f"{elem}, ..."
        return dbc.Input(
            id=fid,
            type="text",
            value=", ".join(str(v) for v in f.default) if f.default else "",
            placeholder=placeholder,
            debounce=_debounce(spec),
            style=spec.style,
            className=spec.class_name,
            **_persist(spec),
        )

    # str, path
    return dbc.Input(
        id=fid,
        type="text",
        value=str(f.default) if f.default is not None else "",
        placeholder="",
        debounce=_debounce(spec),
        style=spec.style,
        className=spec.class_name,
        **_persist(spec),
    )
