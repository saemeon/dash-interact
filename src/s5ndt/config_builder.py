# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

from __future__ import annotations

import inspect
import types
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Literal, Union, get_args, get_origin, get_type_hints

from dash import State, dcc, html


@dataclass
class _Field:
    name: str
    type: str  # "str"|"bool"|"date"|"datetime"|"int"|"float"|"list"|"tuple"|"literal"
    default: Any
    args: tuple = ()
    optional: bool = False  # True when annotation is Optional[T] / T | None


class Config:
    def __init__(self, div: html.Div, states: list[State], fields: list[_Field]):
        self.div = div
        self.states = states
        self._fields = fields

    def build_kwargs(self, values: tuple) -> dict:
        return _build_kwargs(self._fields, values)


def build_config(config_id: str, fn: Callable) -> Config:
    """Introspect *fn*'s signature and return a :class:`Config`.

    Parameters
    ----------
    config_id :
        Unique namespace for component IDs.
    fn :
        Callable whose parameters (after the first) define the fields.

    Returns
    -------
    Config
        ``.div`` — ``html.Div`` with stacked labeled inputs ready to embed anywhere.
        ``.states`` — ``list[State]`` matching the fields (pass to a callback).
        ``.build_kwargs(values)`` — reconstruct a ``dict`` from callback values.
    """
    fields = _get_fields(fn)
    states = _build_states(config_id, fields)
    div = html.Div(
        style={"display": "flex", "flexDirection": "column", "gap": "8px"},
        children=[_build_field(config_id, f) for f in fields],
    )
    return Config(div, states, fields)


# --- internals ---


def _field_id(config_id: str, field: _Field) -> str:
    return f"_s5ndt_field_{config_id}_{field.name}"


def _time_field_id(config_id: str, field: _Field) -> str:
    return f"_s5ndt_field_{config_id}_{field.name}_time"


def _infer_type(annotation: Any, default: Any) -> tuple[str, tuple, bool]:
    """Return (field_type, args, optional) from a parameter annotation + default."""
    origin = get_origin(annotation)
    args = get_args(annotation)

    # Optional[T] == Union[T, None]  |  T | None (Python 3.10+)
    if origin is Union or isinstance(annotation, types.UnionType):
        all_args = args if origin is Union else get_args(annotation)
        non_none = [a for a in all_args if a is not type(None)]
        if len(non_none) == 1:
            field_type, inner_args, _ = _infer_type(non_none[0], default)
            return field_type, inner_args, True
        return "str", (), False

    if annotation is bool or isinstance(default, bool):
        return "bool", (), False
    # datetime must be checked before date (datetime is a subclass of date)
    if annotation is datetime or isinstance(default, datetime):
        return "datetime", (), False
    if annotation is date or isinstance(default, date):
        return "date", (), False
    if annotation is int or (isinstance(default, int) and not isinstance(default, bool)):
        return "int", (), False
    if annotation is float or isinstance(default, float):
        return "float", (), False
    if origin is list:
        return "list", args, False
    if origin is tuple:
        return "tuple", args, False
    if origin is Literal:
        return "literal", args, False
    return "str", (), False


def _get_fields(fn: Callable) -> list[_Field]:
    """Introspect fn's signature, skipping parameters whose names start with ``_``."""
    try:
        hints = get_type_hints(fn)
    except Exception:
        hints = {}

    fields = []
    params = inspect.signature(fn).parameters.values()
    for param in params:
        if param.name.startswith("_"):
            continue
        annotation = hints.get(param.name, param.annotation)
        default = param.default if param.default is not inspect.Parameter.empty else None
        field_type, args, optional = _infer_type(annotation, default)
        fields.append(_Field(
            name=param.name,
            type=field_type,
            default=default,
            args=args,
            optional=optional,
        ))

    return fields


def _build_states(config_id: str, fields: list[_Field]) -> list[State]:
    """Build the State list. datetime emits two States (date + time)."""
    states = []
    for f in fields:
        if f.type == "datetime":
            states.append(State(_field_id(config_id, f), "date"))
            states.append(State(_time_field_id(config_id, f), "value"))
        elif f.type == "date":
            states.append(State(_field_id(config_id, f), "date"))
        else:
            states.append(State(_field_id(config_id, f), "value"))
    return states


def _build_field(config_id: str, field: _Field) -> html.Div:
    """Build a labeled input component for a single field."""
    fid = _field_id(config_id, field)
    label = html.Label(field.name.replace("_", " ").title())

    if field.type == "bool":
        component = dcc.Checklist(
            id=fid,
            options=[{"label": "", "value": field.name}],
            value=[field.name] if field.default else [],
        )
    elif field.type == "date":
        component = dcc.DatePickerSingle(
            id=fid,
            date=field.default.isoformat() if isinstance(field.default, date) else None,
        )
    elif field.type == "datetime":
        default_date = field.default.date().isoformat() if isinstance(field.default, datetime) else None
        default_time = field.default.strftime("%H:%M") if isinstance(field.default, datetime) else None
        component = html.Div(
            style={"display": "flex", "gap": "8px", "alignItems": "center"},
            children=[
                dcc.DatePickerSingle(id=fid, date=default_date),
                dcc.Input(
                    id=_time_field_id(config_id, field),
                    type="text",
                    placeholder="HH:MM",
                    value=default_time,
                    debounce=True,
                    style={"width": "70px"},
                ),
            ],
        )
    elif field.type in ("int", "float"):
        component = dcc.Input(
            id=fid,
            type="number",
            step=1 if field.type == "int" else "any",
            value=field.default,
        )
    elif field.type in ("list", "tuple"):
        if field.type == "tuple":
            placeholder = ", ".join(t.__name__ for t in field.args)
        else:
            elem = field.args[0].__name__ if field.args else "value"
            placeholder = f"{elem}, ..."
        component = dcc.Input(
            id=fid,
            type="text",
            value=", ".join(str(v) for v in field.default) if field.default else "",
            placeholder=placeholder,
        )
    elif field.type == "literal":
        component = dcc.Dropdown(
            id=fid,
            options=list(field.args),
            value=field.default if field.default in field.args else field.args[0],
        )
    else:
        component = dcc.Input(
            id=fid,
            type="text",
            value=str(field.default) if field.default is not None else "",
            placeholder="",
        )

    return html.Div([label, component])


def _coerce(field: _Field, value: Any) -> Any:
    """Coerce a raw widget value to the field's Python type."""
    if field.type == "bool":
        return bool(value)

    empty = value is None or value == "" or value == []
    if empty:
        return None if field.optional else field.default

    if field.type == "date":
        return date.fromisoformat(value)
    if field.type == "int":
        return int(value)
    if field.type == "float":
        return float(value)
    if field.type == "list":
        elem_type = field.args[0] if field.args else str
        return [elem_type(x.strip()) for x in value.split(",")]
    if field.type == "tuple":
        parts = [x.strip() for x in value.split(",")]
        if field.args:
            return tuple(t(v) for t, v in zip(field.args, parts))
        return tuple(parts)
    if field.type == "literal":
        return value
    return value or ""


def _build_kwargs(fields: list[_Field], values: tuple) -> dict:
    """Consume values with an iterator — datetime fields consume two (date + time)."""
    it = iter(values)
    kwargs = {}
    for field in fields:
        if field.type == "datetime":
            date_val = next(it)
            time_val = next(it)
            if date_val is None:
                kwargs[field.name] = None if field.optional else field.default
            else:
                kwargs[field.name] = datetime.fromisoformat(
                    f"{date_val}T{time_val or '00:00'}"
                )
        else:
            kwargs[field.name] = _coerce(field, next(it))
    return kwargs
