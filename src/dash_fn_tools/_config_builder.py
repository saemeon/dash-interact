# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

from __future__ import annotations

import copy
import inspect
import json
import pathlib
import types
import warnings
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import (
    Annotated,
    Any,
    Literal,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

import dash
from dash import Input, Output, State, dcc, html

from dash_fn_tools._spec import FieldHook, FieldSpec

_registered_config_ids: set[str] = set()

# --- field descriptor ---


@dataclass
class _Field:
    name: str
    type: str  # "str"|"bool"|"date"|"datetime"|"int"|"float"|"list"|"tuple"|"literal"
    default: Any
    args: tuple = ()
    optional: bool = False
    spec: FieldSpec | None = field(default=None, repr=False)
    # spec is None until _resolve_spec is called in build_config


# --- Config ---


class Config:
    def __init__(
        self,
        div: html.Div,
        states: list[State],
        fields: list[_Field],
        config_id: str,
    ):
        self.div = div
        self.states = states
        self._fields = fields
        self._config_id = config_id

    @property
    def dirty_states(self) -> list[State]:
        """A single ``State`` for the dirty-tracking store.

        Pass to a callback alongside :attr:`states` to know which fields the
        user has touched.  The store value is a dict keyed by component ID
        (use :func:`field_id` to look up a specific field).
        Requires :meth:`register_dirty_tracking` to have been called.
        """
        return [State(f"_dft_dirty_{self._config_id}", "data")]

    def register_visibility_callbacks(self) -> None:
        """Register a clientside callback that shows/hides conditional fields.

        Fields with ``FieldSpec(visible=("other_field", op, value))`` are
        wrapped in a div whose ``display`` style is toggled whenever the
        controlling field changes.  Supported operators: ``==``, ``!=``,
        ``"in"``, ``"not in"``.

        No arguments needed — call once after ``build_config``.
        """
        visible_fields = [f for f in self._fields if f.spec and f.spec.visible]
        if not visible_fields:
            return

        # Map each field name to its index in self.states (datetime uses two)
        field_to_idx: dict[str, int] = {}
        idx = 0
        for f in self._fields:
            field_to_idx[f.name] = idx
            idx += 2 if f.type == "datetime" else 1

        inputs = [Input(s.component_id, s.component_property) for s in self.states]
        outputs = [
            Output(f"_dft_vis_{self._config_id}_{f.name}", "style")
            for f in visible_fields
        ]
        conditions = [
            {
                "idx": field_to_idx.get(f.spec.visible[0], 0),  # type: ignore[index]
                "op": f.spec.visible[1],  # type: ignore[index]
                "val": f.spec.visible[2],  # type: ignore[index]
            }
            for f in visible_fields
        ]
        conditions_js = json.dumps(conditions)

        dash.clientside_callback(
            f"""
            function() {{
                var args = Array.from(arguments);
                var conditions = {conditions_js};
                return conditions.map(function(cond) {{
                    var raw = args[cond.idx];
                    var value = Array.isArray(raw) ? raw.length > 0 : raw;
                    var show;
                    if (cond.op === '==') show = value == cond.val;
                    else if (cond.op === '!=') show = value != cond.val;
                    else if (cond.op === 'in') show = Array.isArray(cond.val) && cond.val.includes(value);
                    else if (cond.op === 'not in') show = !Array.isArray(cond.val) || !cond.val.includes(value);
                    else show = true;
                    return show ? {{}} : {{"display": "none"}};
                }});
            }}
            """,
            outputs,
            inputs,
        )

    def register_dirty_tracking(self) -> None:
        """Register a clientside callback that records touched fields.

        Writes ``{component_id: 1}`` into a ``dcc.Store`` on every field
        change.  Already-dirty fields are preserved — the store accumulates.
        Read it via :attr:`dirty_states`.
        """
        store_id = f"_dft_dirty_{self._config_id}"
        inputs = [Input(s.component_id, s.component_property) for s in self.states]
        dash.clientside_callback(
            """
            function() {
                var triggered = dash_clientside.callback_context.triggered;
                if (!triggered || triggered.length === 0) {
                    return dash_clientside.no_update;
                }
                var current = arguments[arguments.length - 1] || {};
                var dirty = Object.assign({}, current);
                triggered.forEach(function(t) {
                    dirty[t.prop_id.split('.')[0]] = 1;
                });
                return dirty;
            }
            """,
            Output(store_id, "data", allow_duplicate=True),
            inputs,
            State(store_id, "data"),
            prevent_initial_call=True,
        )

    def build_kwargs(self, values: tuple) -> dict:
        return _build_kwargs(self._fields, values)

    def build_kwargs_validated(
        self, values: tuple
    ) -> tuple[dict, dict[str, str]]:
        """Like :meth:`build_kwargs` but also validates each field.

        Returns ``(kwargs, errors)`` where ``errors`` maps field names to
        human-readable error messages.  Pass ``errors`` to
        :meth:`invalid_outputs` to surface them back to the form.

        Example::

            @app.callback(
                Output("result", "children"),
                *cfg.validation_outputs,
                Input("apply", "n_clicks"),
                *cfg.states,
            )
            def on_apply(_n, *values):
                kwargs, errors = cfg.build_kwargs_validated(values)
                if errors:
                    return dash.no_update, *cfg.invalid_outputs(errors)
                return do_work(**kwargs), *cfg.invalid_outputs({})
        """
        it = iter(values)
        kwargs: dict = {}
        errors: dict[str, str] = {}
        for f in self._fields:
            if f.type == "datetime":
                date_val = next(it)
                time_val = next(it)
                if date_val is None:
                    if not f.optional and f.default is None:
                        errors[f.name] = "Required"
                    kwargs[f.name] = None if f.optional else f.default
                else:
                    time_str = time_val or "00:00"
                    if len(time_str) == 4:
                        time_str = "0" + time_str
                    try:
                        kwargs[f.name] = datetime.fromisoformat(
                            f"{date_val}T{time_str}"
                        )
                    except ValueError:
                        errors[f.name] = "Invalid time (use HH:MM)"
                        kwargs[f.name] = None if f.optional else f.default
            else:
                raw = next(it)
                err = _validate(f, raw)
                if err:
                    errors[f.name] = err
                kwargs[f.name] = _coerce(f, raw)
        return kwargs, errors

    @property
    def validation_outputs(self) -> list[Output]:
        """``Output`` objects for the error spans of each validatable field.

        Each validatable field produces two outputs: the error message text
        and its visibility style.  Pass to a callback decorator alongside
        your normal outputs.  Pair with :meth:`invalid_outputs` to compute
        the return values.

        Only covers fields whose component is ``dcc.Input`` (types: ``str``,
        ``int``, ``float``, ``list``, ``tuple``, ``path``).
        """
        result = []
        for f in self._fields:
            if not (f.spec and f.spec.component) and f.type in _VALIDATABLE:
                err_id = f"_dft_err_{self._config_id}_{f.name}"
                result.append(Output(err_id, "children", allow_duplicate=True))
                result.append(Output(err_id, "style", allow_duplicate=True))
        return result

    def invalid_outputs(self, errors: dict[str, str]) -> list:
        """Convert an errors dict to a flat list of values for :attr:`validation_outputs`.

        Each validatable field contributes two values: the error message
        (or ``""`` when valid) and its CSS style dict.
        Pass ``{}`` (empty dict) to clear all error states.
        """
        result = []
        for f in self._fields:
            if not (f.spec and f.spec.component) and f.type in _VALIDATABLE:
                msg = errors.get(f.name, "")
                result.append(msg)
                result.append(
                    {
                        "color": "#d9534f",
                        "fontSize": "0.8em",
                        "display": "block" if msg else "none",
                    }
                )
        return result

    def register_populate_callback(self, open_input: Input) -> None:
        """Register a single callback that populates all hooked fields on open.

        Existing values are preserved — fields are only populated when empty.
        """
        hooked = [f for f in self._fields if f.spec and f.spec.hook is not None]
        if not hooked:
            return

        seen: set[tuple] = set()
        hook_states: list[State] = []
        for f in hooked:
            for s in f.spec.hook.required_states():  # type: ignore[union-attr]
                key = (s.component_id, s.component_property)
                if key not in seen:
                    seen.add(key)
                    hook_states.append(s)

        outputs: list[Output] = []
        current_states: list[State] = []
        for f in hooked:
            fid = _field_id(self._config_id, f)
            if f.type == "datetime":
                tid = _time_field_id(self._config_id, f)
                outputs.append(Output(fid, "date", allow_duplicate=True))
                outputs.append(Output(tid, "value", allow_duplicate=True))
                current_states.append(State(fid, "date"))
                current_states.append(State(tid, "value"))
            elif f.type == "date":
                outputs.append(Output(fid, "date", allow_duplicate=True))
                current_states.append(State(fid, "date"))
            else:
                prop = f.spec.component_prop if f.spec and f.spec.component else "value"
                outputs.append(Output(fid, prop, allow_duplicate=True))
                current_states.append(State(fid, prop))

        fields = hooked

        @dash.callback(
            *outputs,
            open_input,
            *current_states,
            *hook_states,
            prevent_initial_call=True,
        )
        def populate(is_open, *all_state_values):
            if not is_open:
                return [dash.no_update] * len(outputs)

            n_current = len(current_states)
            current_values = list(all_state_values[:n_current])
            hook_state_values = all_state_values[n_current:]

            state_map = {
                (s.component_id, s.component_property): v
                for s, v in zip(hook_states, hook_state_values, strict=False)
            }

            results: list[Any] = []
            cur = iter(current_values)
            for f in fields:
                assert f.spec is not None and f.spec.hook is not None
                hook: FieldHook = f.spec.hook
                resolved = [
                    state_map[(s.component_id, s.component_property)]
                    for s in hook.required_states()
                ]
                if f.type == "datetime":
                    cur_date, cur_time = next(cur), next(cur)
                    if cur_date not in (None, "") or cur_time not in (None, ""):
                        results += [dash.no_update, dash.no_update]
                        continue
                    val = hook.get_default(*resolved)
                    if isinstance(val, datetime):
                        results += [val.date().isoformat(), val.strftime("%H:%M")]
                    else:
                        results += [dash.no_update, dash.no_update]
                elif f.type == "date":
                    if next(cur) not in (None, ""):
                        results.append(dash.no_update)
                        continue
                    val = hook.get_default(*resolved)
                    results.append(
                        val.isoformat() if isinstance(val, date) else dash.no_update
                    )
                else:
                    if next(cur) not in (None, ""):
                        results.append(dash.no_update)
                        continue
                    val = hook.get_default(*resolved)
                    if isinstance(val, Enum):
                        results.append(val.name)
                    elif isinstance(val, dict):
                        results.append(json.dumps(val, indent=2))
                    elif isinstance(val, pathlib.Path):
                        results.append(str(val))
                    else:
                        results.append(val)
            return results

    def register_restore_callback(self, restore_input: Input) -> None:
        """Register a callback that resets all fields to their defaults.

        Hooked fields call ``hook.get_default()``;
        non-hooked fields revert to the static default from the signature.
        """
        seen: set[tuple] = set()
        hook_states: list[State] = []
        for f in self._fields:
            hook = f.spec.hook if f.spec else None
            if hook:
                for s in hook.required_states():
                    key = (s.component_id, s.component_property)
                    if key not in seen:
                        seen.add(key)
                        hook_states.append(s)

        outputs: list[Output] = []
        for f in self._fields:
            fid = _field_id(self._config_id, f)
            if f.type == "datetime":
                outputs.append(Output(fid, "date", allow_duplicate=True))
                outputs.append(
                    Output(
                        _time_field_id(self._config_id, f),
                        "value",
                        allow_duplicate=True,
                    )
                )
            elif f.type == "date":
                outputs.append(Output(fid, "date", allow_duplicate=True))
            else:
                prop = f.spec.component_prop if f.spec and f.spec.component else "value"
                outputs.append(Output(fid, prop, allow_duplicate=True))

        fields = self._fields

        @dash.callback(*outputs, restore_input, *hook_states, prevent_initial_call=True)
        def restore_all(n_clicks, *hook_state_values):
            state_map = {
                (s.component_id, s.component_property): v
                for s, v in zip(hook_states, hook_state_values, strict=False)
            }
            results: list[Any] = []
            for f in fields:
                hook = f.spec.hook if f.spec else None
                if hook:
                    resolved = [
                        state_map[(s.component_id, s.component_property)]
                        for s in hook.required_states()
                    ]
                    val = hook.get_default(*resolved)
                else:
                    val = f.default

                if f.type == "datetime":
                    if isinstance(val, datetime):
                        results.append(val.date().isoformat())
                        results.append(val.strftime("%H:%M"))
                    else:
                        results.append(None)
                        results.append(None)
                elif f.type == "date":
                    results.append(val.isoformat() if isinstance(val, date) else None)
                elif f.type == "bool":
                    results.append([f.name] if val else [])
                elif f.type in ("list", "tuple"):
                    results.append(", ".join(str(v) for v in val) if val else "")
                elif f.type == "enum":
                    results.append(val.name if isinstance(val, Enum) else val)
                elif f.type == "dict":
                    results.append(json.dumps(val, indent=2) if val is not None else "")
                elif f.type == "path":
                    results.append(str(val) if val is not None else "")
                else:
                    results.append(val if val is not None else "")
            return results


# --- public ---


def build_config(
    config_id: str,
    fn: Callable,
    *,
    _field_specs: dict[str, FieldSpec | FieldHook] | None = None,
    _styles: dict[str, dict] | None = None,
    _class_names: dict[str, str] | None = None,
    _cols: int = 1,
    _show_docstring: bool = True,
    _exclude: list[str] | None = None,
    _include: list[str] | None = None,
    **kwargs: FieldSpec | FieldHook | tuple,
) -> Config:
    """Introspect *fn*'s signature and return a :class:`Config`.

    Parameters
    ----------
    config_id :
        Unique namespace for component IDs.
    fn :
        Callable whose parameters define the fields.
        Parameters whose names start with ``_`` are skipped.
    **kwargs :
        Per-field customisation passed as keyword arguments named after the
        function parameter.  Values may be a :class:`FieldSpec`, a bare
        :class:`FieldHook` (treated as ``FieldSpec(hook=hook)``), or a tuple
        shorthand:

        * ``(min, max)`` → ``FieldSpec(min=min, max=max)``
        * ``(min, max, step)`` → ``FieldSpec(min=min, max=max, step=step)``

        Example::

            cfg = build_config("render", fn, dpi=(10, 300, 10), show_grid=FieldSpec(label="Grid"))

        Overridden by ``Annotated[T, FieldSpec(...)]`` in the signature.
        Use ``_field_specs`` when you need to build the dict programmatically.
    _field_specs :
        Dict-based alternative to ``**kwargs``.  Takes precedence over
        ``**kwargs`` for the same field name.
    _styles :
        Type-level CSS dicts, keyed by slot name.  Applied to every field
        of that type unless the field has its own ``FieldSpec.style``.

        * ``"str"`` → ``dcc.Input(type="text")``
        * ``"int"`` → ``dcc.Input(type="number", step=1)``
        * ``"float"`` → ``dcc.Input(type="number", step="any")``
        * ``"bool"`` → ``dcc.Checklist``
        * ``"date"`` → ``dcc.DatePickerSingle``
        * ``"datetime"`` → ``dcc.DatePickerSingle`` + ``dcc.Input(type="text")``
        * ``"literal"`` → ``dcc.Dropdown``
        * ``"enum"`` → ``dcc.Dropdown`` (from ``Enum`` subclass)
        * ``"dict"`` → ``dcc.Textarea`` (JSON, coerced via ``json.loads``)
        * ``"path"`` → ``dcc.Input(type="text")`` (coerced via ``pathlib.Path``)
        * ``"list"`` / ``"tuple"`` → ``dcc.Input(type="text")``
        * ``"label"`` → ``html.Label`` on every field label
    _class_names :
        Same as *_styles* but for CSS class names.
    _cols :
        Number of columns in the form grid. Default ``1`` (vertical stack).
        Use ``FieldSpec.col_span`` on individual fields to span columns.
    _show_docstring :
        Prepend the function's docstring as a paragraph above the fields.
        Default ``True``.
    _exclude :
        Parameter names to skip entirely.
    _include :
        If given, only these parameters are shown, in the order listed.

    Returns
    -------
    Config
        ``.div`` — ``html.Div`` with labeled inputs ready to embed anywhere.
        ``.states`` — ``list[State]`` matching the fields (pass to a callback).
        ``.build_kwargs(values)`` — reconstruct a ``dict`` from callback values.
        ``.register_populate_callback(open_input)`` — wire hook defaults on open.
        ``.register_restore_callback(restore_input)`` — reset all fields.
    """
    if config_id in _registered_config_ids:
        warnings.warn(
            f"dash-fn-tools: config_id {config_id!r} is already in use. "
            "Duplicate IDs will cause Dash callback errors.",
            UserWarning,
            stacklevel=2,
        )
    _registered_config_ids.add(config_id)

    styles = _styles or {}
    class_names = _class_names or {}

    # Normalize **kwargs tuple shorthands and merge with _field_specs.
    # _field_specs wins over **kwargs for the same field name.
    normalized: dict[str, FieldSpec | FieldHook] = {}
    for name, val in kwargs.items():
        if isinstance(val, tuple):
            if len(val) == 2:
                normalized[name] = FieldSpec(min=val[0], max=val[1])
            elif len(val) == 3:
                normalized[name] = FieldSpec(min=val[0], max=val[1], step=val[2])
            else:
                raise ValueError(
                    f"build_config kwarg {name!r}: tuple must be (min, max) or "
                    f"(min, max, step), got {val!r}"
                )
        else:
            normalized[name] = val
    external_specs = {**normalized, **(_field_specs or {})}

    fields = _get_fields(fn, exclude=_exclude, include=_include)

    for f in fields:
        f.spec = _resolve_spec(f, external_specs, styles, class_names)

    states = _build_states(config_id, fields)

    label_style = styles.get("label")
    label_class_name = class_names.get("label", "")

    children: list = []
    if _show_docstring:
        doc = inspect.getdoc(fn)
        if doc:
            children.append(
                html.P(
                    doc,
                    style={
                        "margin": "0 0 8px 0",
                        "fontSize": "0.875em",
                        "color": "#555",
                    },
                )
            )

    field_defaults = {f.name: f.default for f in fields}
    for f in fields:
        child = _build_field(config_id, f, label_style, label_class_name)
        if f.spec and f.spec.visible:
            other, op, val = f.spec.visible
            show = _check_visible(field_defaults.get(other), op, val)
            grid: dict = (
                {"gridColumn": f"span {f.spec.col_span}"} if f.spec.col_span > 1 else {}
            )
            vis_style = {**grid, **({} if show else {"display": "none"})}
            child = html.Div(
                child,
                id=f"_dft_vis_{config_id}_{f.name}",
                style=vis_style or None,
            )
        children.append(child)

    if _cols > 1:
        outer_style: dict = {
            "display": "grid",
            "gridTemplateColumns": f"repeat({_cols}, 1fr)",
            "gap": "8px",
        }
    else:
        outer_style = {"display": "flex", "flexDirection": "column", "gap": "8px"}

    div = html.Div(
        children=[
            dcc.Store(id=f"_dft_dirty_{config_id}", data={}),
            html.Div(style=outer_style, children=children),
        ]
    )
    return Config(div, states, fields, config_id)


# --- internals ---


def field_id(config_id: str, name: str) -> str:
    """Return the Dash component ID for a field by name."""
    return f"_dft_field_{config_id}_{name}"


def _field_id(config_id: str, f: _Field) -> str:
    return field_id(config_id, f.name)


def _time_field_id(config_id: str, f: _Field) -> str:
    return f"_dft_field_{config_id}_{f.name}_time"


def _resolve_spec(
    f: _Field,
    external_specs: dict[str, FieldSpec | FieldHook],
    styles: dict[str, dict],
    class_names: dict[str, str],
) -> FieldSpec:
    """Merge tiers: Annotated (tier 3) > field_specs (tier 2) > type-level (tier 1)."""
    if f.spec is not None:
        # Annotated spec wins entirely over external
        spec = copy.copy(f.spec)
    else:
        ext = external_specs.get(f.name)
        if isinstance(ext, FieldHook):
            spec = FieldSpec(hook=ext)
        elif isinstance(ext, FieldSpec):
            spec = copy.copy(ext)
        else:
            spec = FieldSpec()

    # Fill visual properties from type-level dicts where spec didn't set them
    if spec.style is None and f.type in styles:
        spec.style = styles[f.type]
    if not spec.class_name and f.type in class_names:
        spec.class_name = class_names[f.type]

    return spec


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
    if annotation is int or (
        isinstance(default, int) and not isinstance(default, bool)
    ):
        return "int", (), False
    if annotation is float or isinstance(default, float):
        return "float", (), False
    if origin is list:
        return "list", args, False
    if origin is tuple:
        return "tuple", args, False
    if origin is Literal:
        return "literal", args, False
    if inspect.isclass(annotation) and issubclass(annotation, Enum):
        return "enum", (annotation,), False
    if annotation is dict or origin is dict:
        return "dict", (), False
    if annotation is pathlib.Path:
        return "path", (), False
    return "str", (), False


def _get_fields(
    fn: Callable,
    exclude: list[str] | None = None,
    include: list[str] | None = None,
) -> list[_Field]:
    """Introspect fn's signature into a list of _Field descriptors."""
    try:
        hints = get_type_hints(fn, include_extras=True)
    except Exception:
        hints = {}

    exclude_set = set(exclude or [])
    include_set = set(include) if include else None

    fields = []
    for param in inspect.signature(fn).parameters.values():
        if param.name.startswith("_"):
            continue
        if param.name in exclude_set:
            continue
        if include_set is not None and param.name not in include_set:
            continue

        raw_default = (
            param.default if param.default is not inspect.Parameter.empty else None
        )

        # Legacy: FieldHook as default — kept for renderer functions (e.g. FromPlotly).
        # For user functions, prefer FieldSpec(hook=...) via field_specs or Annotated.
        hook_from_default: FieldHook | None = None
        if isinstance(raw_default, FieldHook):
            hook_from_default = raw_default
            raw_default = None

        annotation = hints.get(param.name, param.annotation)

        # Extract FieldSpec from Annotated[T, FieldSpec(...)]
        annotated_spec: FieldSpec | None = None
        if get_origin(annotation) is Annotated:
            inner_args = get_args(annotation)
            annotation = inner_args[0]
            annotated_spec = next(
                (m for m in inner_args[1:] if isinstance(m, FieldSpec)), None
            )

        # Legacy hook-as-default: fold into annotated_spec so _resolve_spec sees it
        if hook_from_default is not None and annotated_spec is None:
            annotated_spec = FieldSpec(hook=hook_from_default)

        field_type, args, optional = _infer_type(annotation, raw_default)
        fields.append(
            _Field(
                name=param.name,
                type=field_type,
                default=raw_default,
                args=args,
                optional=optional,
                spec=annotated_spec,  # None → resolved later in build_config
            )
        )

    if include:
        order = {name: i for i, name in enumerate(include)}
        fields.sort(key=lambda f: order.get(f.name, len(include)))

    return fields


# Field types whose primary component is dcc.Input and supports the `invalid` prop.
_VALIDATABLE = frozenset({"str", "int", "float", "list", "tuple", "path"})


def _validate(f: _Field, value: Any) -> str | None:
    """Return an error message if value fails validation for field f, else None."""
    if f.type not in _VALIDATABLE:
        return None
    empty = value is None or value == ""
    if empty:
        return "Required" if (not f.optional and f.default is None) else None
    try:
        if f.type == "int":
            int(value)
        elif f.type == "float":
            float(value)
        elif f.type == "list":
            elem_type = f.args[0] if f.args else str
            [elem_type(x.strip()) for x in str(value).split(",")]
        elif f.type == "tuple":
            parts = [x.strip() for x in str(value).split(",")]
            if f.args:
                tuple(t(v) for t, v in zip(f.args, parts, strict=False))
    except (ValueError, TypeError):
        return "Invalid value"
    return None


def _check_visible(value: Any, op: str, expected: Any) -> bool:
    """Evaluate a single visibility condition at render time (Python side)."""
    if op == "==":
        return value == expected
    if op == "!=":
        return value != expected
    if op == "in":
        return value in expected
    if op == "not in":
        return value not in expected
    return True


def _build_states(config_id: str, fields: list[_Field]) -> list[State]:
    """Build the State list. datetime emits two States (date + time)."""
    states = []
    for f in fields:
        fid = _field_id(config_id, f)
        spec = f.spec
        if spec and spec.component is not None:
            states.append(State(fid, spec.component_prop))
        elif f.type == "datetime":
            states.append(State(fid, "date"))
            states.append(State(_time_field_id(config_id, f), "value"))
        elif f.type == "date":
            states.append(State(fid, "date"))
        else:
            states.append(State(fid, "value"))
    return states


def _build_field(
    config_id: str,
    f: _Field,
    label_style: dict | None,
    label_class_name: str,
) -> html.Div:
    """Build a labeled input component for a single field."""
    spec = f.spec or FieldSpec()
    fid = _field_id(config_id, f)

    label_text = spec.label or f.name.replace("_", " ").title()
    label = html.Label(label_text, style=label_style, className=label_class_name)

    wrapper_style: dict = {}
    if spec.col_span > 1:
        wrapper_style["gridColumn"] = f"span {spec.col_span}"

    if spec.component is not None:
        comp = copy.copy(spec.component)
        comp.id = fid
        children: list = [label, comp]
        if spec.description:
            children.append(
                html.Small(
                    spec.description, style={"color": "#666", "display": "block"}
                )
            )
        return html.Div(children, style=wrapper_style or None)

    component = _make_component(config_id, f, spec, fid)
    children = [label, component]
    if spec.description:
        children.append(
            html.Small(spec.description, style={"color": "#666", "display": "block"})
        )
    if f.type in _VALIDATABLE:
        children.append(
            html.Small(
                "",
                id=f"_dft_err_{config_id}_{f.name}",
                style={"color": "#d9534f", "fontSize": "0.8em", "display": "none"},
            )
        )
    return html.Div(children, style=wrapper_style or None)


def _make_component(config_id: str, f: _Field, spec: FieldSpec, fid: str) -> Any:
    """Build the Dash input component for a field based on its type."""
    if f.type == "bool":
        return dcc.Checklist(
            id=fid,
            options=[{"label": "", "value": f.name}],
            value=[f.name] if f.default else [],
            style=spec.style,
            className=spec.class_name,
        )
    if f.type == "date":
        return dcc.DatePickerSingle(
            id=fid,
            date=f.default.isoformat() if isinstance(f.default, date) else None,
            style=spec.style,
            className=spec.class_name,
        )
    if f.type == "datetime":
        default_date = (
            f.default.date().isoformat() if isinstance(f.default, datetime) else None
        )
        default_time = (
            f.default.strftime("%H:%M") if isinstance(f.default, datetime) else None
        )
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
                    id=_time_field_id(config_id, f),
                    type="text",
                    placeholder="HH:MM",
                    value=default_time,
                    debounce=True,
                    style={"width": "70px", **(spec.style or {})},
                    className=spec.class_name,
                ),
            ],
        )
    if f.type in ("int", "float"):
        step: Any = spec.step
        if step is None:
            step = 1 if f.type == "int" else "any"
        return dcc.Input(
            id=fid,
            type="number",
            step=step,
            value=f.default,
            min=spec.min,
            max=spec.max,
            debounce=True,
            style=spec.style,
            className=spec.class_name,
        )
    if f.type in ("list", "tuple"):
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
            debounce=True,
            style=spec.style,
            className=spec.class_name,
        )
    if f.type == "literal":
        return dcc.Dropdown(
            id=fid,
            options=list(f.args),
            value=f.default if f.default in f.args else f.args[0],
            style=spec.style,
            className=spec.class_name,
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
        )
    if f.type == "dict":
        default_str = json.dumps(f.default, indent=2) if f.default else ""
        return dcc.Textarea(
            id=fid,
            value=default_str,
            placeholder='{"key": "value"}',
            style={"fontFamily": "monospace", "width": "100%", **(spec.style or {})},
            className=spec.class_name,
        )
    if f.type == "path":
        return dcc.Input(
            id=fid,
            type="text",
            value=str(f.default) if f.default is not None else "",
            placeholder="/path/to/file",
            debounce=True,
            style=spec.style,
            className=spec.class_name,
        )
    return dcc.Input(
        id=fid,
        type="text",
        value=str(f.default) if f.default is not None else "",
        placeholder="",
        debounce=True,
        style=spec.style,
        className=spec.class_name,
    )


def _coerce(f: _Field, value: Any) -> Any:
    """Coerce a raw widget value to the field's Python type."""
    if f.type == "bool":
        return bool(value)

    empty = value is None or value == "" or value == []
    if empty:
        return None if f.optional else f.default

    try:
        if f.type == "date":
            return date.fromisoformat(value)
        if f.type == "int":
            return int(value)
        if f.type == "float":
            return float(value)
        if f.type == "list":
            elem_type = f.args[0] if f.args else str
            return [elem_type(x.strip()) for x in value.split(",")]
        if f.type == "tuple":
            parts = [x.strip() for x in value.split(",")]
            if f.args:
                return tuple(t(v) for t, v in zip(f.args, parts, strict=False))
            return tuple(parts)
    except (ValueError, TypeError):
        return f.default
    if f.type == "literal":
        return value
    if f.type == "enum":
        enum_cls = f.args[0]
        try:
            return enum_cls[value]
        except KeyError:
            return f.default
    if f.type == "dict":
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError, TypeError):
            return f.default
    if f.type == "path":
        return pathlib.Path(value)
    return value or ""


def _build_kwargs(fields: list[_Field], values: tuple) -> dict:
    """Consume values with an iterator — datetime fields consume two (date + time)."""
    it = iter(values)
    kwargs = {}
    for f in fields:
        if f.type == "datetime":
            date_val = next(it)
            time_val = next(it)
            if date_val is None:
                kwargs[f.name] = None if f.optional else f.default
            else:
                time_str = time_val or "00:00"
                if len(time_str) == 4:
                    time_str = "0" + time_str
                try:
                    kwargs[f.name] = datetime.fromisoformat(f"{date_val}T{time_str}")
                except ValueError:
                    kwargs[f.name] = None if f.optional else f.default
        else:
            kwargs[f.name] = _coerce(f, next(it))
    return kwargs
