# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

from __future__ import annotations

import copy
import inspect
import json
import pathlib
import re
import types
import warnings
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import (
    TYPE_CHECKING,
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

from dash_fn_interact._spec import Field, FieldHook, _FieldFixed

_registered_config_ids: set[str] = set()




class FieldRef:
    """A reference to a single field in a :class:`Config`.

    Behaves as a string equal to the field's component ID, so it can be used
    directly as a dict key or passed anywhere a component ID string is expected.
    Also exposes :attr:`id`, :attr:`state`, and :attr:`output` for explicit use.

    Access via attribute on :class:`Config`::

        cfg.title           # FieldRef for the "title" field
        cfg.title.id        # "_dft_field_render_title"
        cfg.title.state     # State("_dft_field_render_title", "value")
        cfg.title.output    # Output("_dft_field_render_title", "value")
        dirty.get(cfg.title)  # works — FieldRef hashes and compares as its ID
    """

    def __init__(self, component_id: str, prop: str) -> None:
        self._component_id = component_id
        self._prop = prop

    @property
    def id(self) -> str:
        """The Dash component ID string."""
        return self._component_id

    @property
    def state(self) -> State:
        """``State(id, prop)`` ready to pass to a callback."""
        return State(self._component_id, self._prop)

    @property
    def output(self) -> Output:
        """``Output(id, prop)`` ready to pass to a callback."""
        return Output(self._component_id, self._prop)

    # --- string-like behaviour ---

    def __str__(self) -> str:
        return self._component_id

    def __repr__(self) -> str:
        return f"FieldRef({self._component_id!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, FieldRef):
            return self._component_id == other._component_id
        return self._component_id == other

    def __hash__(self) -> int:
        return hash(self._component_id)




@dataclass
class _Field:
    name: str
    type: str  # "str"|"bool"|"date"|"datetime"|"int"|"float"|"list"|"tuple"|"literal"
    default: Any
    args: tuple = ()
    optional: bool = False
    spec: Field | None = field(default=None, repr=False)
    # spec is None until _resolve_spec is called in Config.__init__




class Form(html.Div):
    """Base class for declarative Dash forms.

    Subclass and annotate fields directly::

        class RenderForm(Form):
            dpi: int = Field(min=72, max=300)
            method: Literal["newton", "euler"] = "newton"
            title: str = ""

        cfg = RenderForm("render")

    Use :class:`FnForm` to build a form from an existing typed callable instead.
    """

    if TYPE_CHECKING:
        states: list[State]
        _fields: list[_Field]
        _config_id: str
        _fixed_values: dict[str, Any]
        _form_validator: Callable[[dict], str | None] | None

    def __init__(
        self,
        config_id: str,
        *,
        _fields: list[_Field] | None = None,
        _fixed_values: dict[str, Any] | None = None,
        _cols: int = 1,
        _styles: dict[str, dict] | None = None,
        _class_names: dict[str, str] | None = None,
        _validator: Callable[[dict], str | None] | None = None,
        _field_components: Any = None,
        _description: str | None = None,
    ):
        if config_id in _registered_config_ids:
            warnings.warn(
                f"dash-fn-interact: config_id {config_id!r} is already in use. "
                "Duplicate IDs will cause Dash callback errors.",
                UserWarning,
                stacklevel=2,
            )
        _registered_config_ids.add(config_id)

        styles = _styles or {}
        class_names = _class_names or {}

        if _fields is None:
            _fields = type(self)._collect_fields(styles, class_names)

        fixed_values = _fixed_values or {}
        states = _build_states(config_id, _fields)

        from dash_fn_interact._field_components import _resolve_field_maker

        field_maker = _resolve_field_maker(_field_components)

        label_style = styles.get("label")
        label_class_name = class_names.get("label", "")

        children: list = []
        if _description:
            children.append(
                html.P(
                    _description,
                    style={
                        "margin": "0 0 8px 0",
                        "fontSize": "0.875em",
                        "color": "#555",
                    },
                )
            )

        field_defaults = {f.name: f.default for f in _fields}
        for f in _fields:
            child = _build_field(config_id, f, label_style, label_class_name, field_maker)
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

        form_children: list = [
            dcc.Store(id=f"_dft_dirty_{config_id}", data={}),
            html.Div(style=outer_style, children=children),
        ]
        if _validator is not None:
            form_children.append(
                html.Small(
                    id=f"_dft_form_err_{config_id}",
                    children="",
                    style={"color": "#d9534f", "fontSize": "0.8em", "display": "none"},
                )
            )

        super().__init__(children=form_children)
        object.__setattr__(self, "states", states)
        object.__setattr__(self, "_fields", _fields)
        object.__setattr__(self, "_config_id", config_id)
        object.__setattr__(self, "_fixed_values", fixed_values)
        object.__setattr__(self, "_form_validator", _validator)

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

        Fields with ``Field(visible=("other_field", op, value))`` are
        wrapped in a div whose ``display`` style is toggled whenever the
        controlling field changes.  Supported operators: ``==``, ``!=``,
        ``"in"``, ``"not in"``.

        No arguments needed — call once after constructing the :class:`Config`.
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

    def __getattr__(self, name: str) -> FieldRef:
        # Only called when normal attribute lookup fails.
        # Use object.__getattribute__ to avoid infinite recursion.
        try:
            fields = object.__getattribute__(self, "_fields")
            config_id = object.__getattribute__(self, "_config_id")
        except AttributeError as exc:
            raise AttributeError(f"Config has no field {name!r}") from exc
        for f in fields:
            if f.name == name:
                prop = (
                    f.spec.component_prop
                    if f.spec and f.spec.component
                    else "date"
                    if f.type in ("date", "datetime")
                    else "value"
                )
                return FieldRef(field_id(config_id, name), prop)
        raise AttributeError(f"Config has no field {name!r}")

    def build_kwargs(self, values: tuple) -> dict:
        result = _build_kwargs(self._fields, values)
        result.update(self._fixed_values)
        return result

    def build_kwargs_validated(self, values: tuple) -> tuple[dict, dict[str, str]]:
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
                coerced = _coerce(f, raw)
                if err:
                    errors[f.name] = err
                elif f.spec and f.spec.validator is not None:
                    try:
                        custom_err = f.spec.validator(coerced)
                    except Exception as exc:
                        custom_err = str(exc)
                    if custom_err:
                        errors[f.name] = custom_err
                kwargs[f.name] = coerced
        kwargs.update(self._fixed_values)
        form_validator = object.__getattribute__(self, "_form_validator")
        if not errors and form_validator is not None:
            try:
                form_err = form_validator(kwargs)
            except Exception as exc:
                form_err = str(exc)
            if form_err:
                errors["_form"] = form_err
        return kwargs, errors

    @property
    def validation_outputs(self) -> list[Output]:
        """``Output`` objects for the error spans of each validatable field.

        Each validatable field produces two outputs: the error message text
        and its visibility style.  Pass to a callback decorator alongside
        your normal outputs.  Pair with :meth:`invalid_outputs` to compute
        the return values.

        Covers fields with built-in type validation (``str``, ``int``, ``float``,
        ``list``, ``tuple``, ``path``) and any field with a custom
        ``Field(validator=...)``.
        """
        result = []
        for f in self._fields:
            if _has_error_span(f):
                err_id = f"_dft_err_{self._config_id}_{f.name}"
                result.append(Output(err_id, "children", allow_duplicate=True))
                result.append(Output(err_id, "style", allow_duplicate=True))
        return result

    def invalid_outputs(self, errors: dict[str, str]) -> list:
        """Convert an errors dict to a flat list of values for
        :attr:`validation_outputs`.

        Each validatable field contributes two values: the error message
        (or ``""`` when valid) and its CSS style dict.
        Pass ``{}`` (empty dict) to clear all error states.
        """
        result = []
        for f in self._fields:
            if _has_error_span(f):
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

    @property
    def form_validation_output(self) -> list[Output]:
        """``Output`` objects for the form-level error span.

        Returns two outputs: the error message text and its visibility style.
        Pass to a callback decorator alongside :attr:`validation_outputs`.
        Pair with :meth:`form_invalid_output` to compute the return values.

        Only meaningful when ``_validator`` was passed to :class:`Config`.
        """
        err_id = f"_dft_form_err_{self._config_id}"
        return [
            Output(err_id, "children", allow_duplicate=True),
            Output(err_id, "style", allow_duplicate=True),
        ]

    def form_invalid_output(self, error: str | None) -> list:
        """Convert a form-level error to values for :attr:`form_validation_output`.

        Pass the ``errors.get("_form")`` value (or ``None`` to clear).
        Returns ``[message, style_dict]``.
        """
        msg = error or ""
        return [
            msg,
            {
                "color": "#d9534f",
                "fontSize": "0.8em",
                "display": "block" if msg else "none",
            },
        ]

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
                    widget_val = _to_widget_value(f, hook.get_default(*resolved))
                    if widget_val == (None, None):
                        results += [dash.no_update, dash.no_update]
                    else:
                        results += list(widget_val)
                elif f.type == "date":
                    if next(cur) not in (None, ""):
                        results.append(dash.no_update)
                        continue
                    widget_val = _to_widget_value(f, hook.get_default(*resolved))
                    results.append(
                        widget_val if widget_val is not None else dash.no_update
                    )
                else:
                    if next(cur) not in (None, ""):
                        results.append(dash.no_update)
                        continue
                    results.append(_to_widget_value(f, hook.get_default(*resolved)))
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
                widget_val = _to_widget_value(f, val)
                if f.type == "datetime":
                    results.extend(widget_val)
                else:
                    results.append(widget_val)
            return results

    @classmethod
    def _collect_fields(cls, styles: dict, class_names: dict) -> list[_Field]:
        """Collect _Field descriptors from a declarative Form subclass."""
        own_names = set(getattr(cls, "__annotations__", {}).keys())
        try:
            hints = get_type_hints(cls, include_extras=True)
        except Exception:
            hints = getattr(cls, "__annotations__", {})

        fields = []
        for name, annotation in hints.items():
            if name not in own_names or name.startswith("_"):
                continue

            raw = getattr(cls, name, inspect.Parameter.empty)

            annotated_spec: Field | None = None
            default = None

            if get_origin(annotation) is Annotated:
                inner_args = get_args(annotation)
                annotation = inner_args[0]
                annotated_spec = next(
                    (m for m in inner_args[1:] if isinstance(m, Field)), None
                )

            if isinstance(raw, Field):
                if annotated_spec is None:
                    annotated_spec = raw
                default = raw.default
            elif raw is not inspect.Parameter.empty:
                default = raw

            field_type, args, optional = _infer_type(annotation, default)
            f = _Field(
                name=name,
                type=field_type,
                default=default,
                args=args,
                optional=optional,
                spec=annotated_spec,
            )
            f.spec = _resolve_spec(f, {}, styles, class_names)
            fields.append(f)

        return fields




class FnForm(Form):
    if TYPE_CHECKING:
        _fn: Callable

    """Build a form by introspecting a typed callable's signature.

    Parameters
    ----------
    config_id :
        Unique namespace for component IDs.
    fn :
        Callable whose parameters define the fields.
    **kwargs :
        Per-field customisation named after the function parameter.  Supported shorthands:

        * ``Field(...)`` / ``FieldHook`` — passed through as-is
        * ``(min, max)`` → ``Field(min=min, max=max)``
        * ``(min, max, step)`` → ``Field(min=min, max=max, step=step)``
        * ``range(a, b, step)`` → ``Field(min=a, max=b, step=step)``
        * ``["a", "b", "c"]`` → ``dcc.Dropdown(options=[...])``
        * ``{"Label": "value", ...}`` → ``dcc.Dropdown`` with label/value pairs
        * ``"My Label"`` → ``Field(label="My Label")``
        * ``dcc.Component`` → ``Field(component=component)``
        * ``callable`` → ``Field(validator=callable)``

        Overridden by ``Annotated[T, Field(...)]`` in the signature.
        Use ``_field_specs`` when you need to build the dict programmatically.
    _field_specs :
        Dict-based alternative to ``**kwargs``.  Takes precedence over
        ``**kwargs`` for the same field name.
    _styles :
        Type-level CSS dicts keyed by slot name (``"str"``, ``"int"``, ``"bool"``,
        ``"date"``, ``"datetime"``, ``"literal"``, ``"enum"``, ``"dict"``,
        ``"path"``, ``"list"``, ``"tuple"``, ``"label"``).
    _class_names :
        Same as *_styles* but for CSS class names.
    _cols :
        Number of columns in the form grid. Default ``1`` (vertical stack).
    _show_docstring :
        Prepend the function's docstring as a paragraph above the fields.
        Default ``True``.
    _exclude :
        Parameter names to skip entirely.
    _include :
        If given, only these parameters are shown, in the order listed.
    _initial_values :
        Pre-fill field defaults from a ``dict`` or any object with matching
        attributes (dataclass, Pydantic model, plain object).
    _validator :
        Cross-field validator ``(kwargs: dict) -> str | None``.  Called after
        per-field validation; return an error string on failure, ``None`` on success.
    _field_components :
        Component factory: ``"dmc"``, ``"dbc"``, ``"dcc"``, ``"auto"``, or any
        callable matching :class:`~dash_fn_interact.FieldMaker`.
    """

    def __init__(
        self,
        config_id: str,
        fn: Callable,
        *,
        _field_specs: dict[str, Field | FieldHook] | None = None,
        _styles: dict[str, dict] | None = None,
        _class_names: dict[str, str] | None = None,
        _cols: int = 1,
        _show_docstring: bool = True,
        _exclude: list[str] | None = None,
        _include: list[str] | None = None,
        _initial_values: dict | object | None = None,
        _validator: Callable[[dict], str | None] | None = None,
        _field_components: Any = None,
        **kwargs: Field | FieldHook | tuple,
    ):
        styles = _styles or {}
        class_names = _class_names or {}

        fixed_values: dict[str, Any] = {}
        normalized: dict[str, Field | FieldHook] = {}
        for name, val in kwargs.items():
            if isinstance(val, _FieldFixed):
                fixed_values[name] = val.value
                continue
            if isinstance(val, (Field, FieldHook)):
                normalized[name] = val
            elif isinstance(val, range):
                normalized[name] = Field(min=val.start, max=val.stop, step=val.step)
            elif isinstance(val, tuple):
                if len(val) == 2:
                    normalized[name] = Field(min=val[0], max=val[1])
                elif len(val) == 3:
                    normalized[name] = Field(min=val[0], max=val[1], step=val[2])
                else:
                    raise ValueError(
                        f"FnForm kwarg {name!r}: tuple must be (min, max) or "
                        f"(min, max, step), got {val!r}"
                    )
            elif isinstance(val, list):
                normalized[name] = Field(
                    component=dcc.Dropdown(options=val, value=val[0] if val else None)
                )
            elif isinstance(val, dict):
                options = [{"label": k, "value": v} for k, v in val.items()]
                normalized[name] = Field(
                    component=dcc.Dropdown(
                        options=options, value=options[0]["value"] if options else None
                    )
                )
            elif isinstance(val, str):
                normalized[name] = Field(label=val)
            elif hasattr(val, "id") or hasattr(val, "_type"):
                normalized[name] = Field(component=val)
            elif callable(val):
                normalized[name] = Field(validator=val)
            else:
                normalized[name] = val
        external_specs = {**normalized, **(_field_specs or {})}

        fields = _get_fields(fn, exclude=_exclude, include=_include)
        if fixed_values:
            fields = [f for f in fields if f.name not in fixed_values]

        if _initial_values is not None:
            for f in fields:
                if isinstance(_initial_values, dict):
                    if f.name in _initial_values:
                        f.default = _initial_values[f.name]
                elif hasattr(_initial_values, f.name):
                    f.default = getattr(_initial_values, f.name)

        for f in fields:
            f.spec = _resolve_spec(f, external_specs, styles, class_names)

        description = inspect.getdoc(fn) if _show_docstring else None

        super().__init__(
            config_id,
            _fields=fields,
            _fixed_values=fixed_values or None,
            _cols=_cols,
            _styles=_styles,
            _class_names=_class_names,
            _validator=_validator,
            _field_components=_field_components,
            _description=description,
        )
        object.__setattr__(self, "_fn", fn)

    def call(self, values: tuple) -> tuple[Any, dict[str, str]]:
        """Validate *values* and call the wrapped function.

        Returns ``(result, errors)``.  If validation fails, ``result`` is
        ``None`` and ``errors`` maps field names to error messages.  On
        success, ``errors`` is ``{}``.

        Example::

            @app.callback(
                Output("result", "children"),
                *cfg.validation_outputs,
                Input("apply", "n_clicks"),
                *cfg.states,
            )
            def on_apply(_n, *values):
                result, errors = cfg.call(values)
                if errors:
                    return dash.no_update, *cfg.invalid_outputs(errors)
                return str(result), *cfg.invalid_outputs({})
        """
        kwargs, errors = self.build_kwargs_validated(values)
        if errors:
            return None, errors
        fn = object.__getattribute__(self, "_fn")
        return fn(**kwargs), {}




def field_id(config_id: str, name: str) -> str:
    """Return the Dash component ID for a field by name."""
    return f"_dft_field_{config_id}_{name}"


def _field_id(config_id: str, f: _Field) -> str:
    return field_id(config_id, f.name)


def _time_field_id(config_id: str, f: _Field) -> str:
    return f"_dft_field_{config_id}_{f.name}_time"


def _resolve_spec(
    f: _Field,
    external_specs: dict[str, Field | FieldHook],
    styles: dict[str, dict],
    class_names: dict[str, str],
) -> Field:
    """Merge tiers: Annotated (tier 3) > field_specs (tier 2) > type-level (tier 1)."""
    if f.spec is not None:
        # Annotated spec wins entirely over external
        spec = copy.copy(f.spec)
    else:
        ext = external_specs.get(f.name)
        if isinstance(ext, FieldHook):
            spec = Field(hook=ext)
        elif isinstance(ext, Field):
            spec = copy.copy(ext)
        else:
            spec = Field()

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
        if param.name in _RESERVED:
            continue
        if param.name in exclude_set:
            continue
        if include_set is not None and param.name not in include_set:
            continue

        raw_default = (
            param.default if param.default is not inspect.Parameter.empty else None
        )

        # Legacy: FieldHook as default — kept for renderer functions (e.g. FromPlotly).
        # For user functions, prefer Field(hook=...) via field_specs or Annotated.
        hook_from_default: FieldHook | None = None
        if isinstance(raw_default, FieldHook):
            hook_from_default = raw_default
            raw_default = None

        annotation = hints.get(param.name, param.annotation)

        # Extract Field (and bare callable validators) from Annotated[T, ...]
        annotated_spec: Field | None = None
        if get_origin(annotation) is Annotated:
            inner_args = get_args(annotation)
            annotation = inner_args[0]
            annotated_spec = next(
                (m for m in inner_args[1:] if isinstance(m, Field)), None
            )
            # A bare callable in Annotated metadata becomes the validator
            bare_validator = next(
                (m for m in inner_args[1:] if callable(m) and not isinstance(m, Field)),
                None,
            )
            if bare_validator is not None:
                if annotated_spec is None:
                    annotated_spec = Field(validator=bare_validator)
                elif annotated_spec.validator is None:
                    annotated_spec = copy.copy(annotated_spec)
                    annotated_spec.validator = bare_validator

        # Legacy hook-as-default: fold into annotated_spec so _resolve_spec sees it
        if hook_from_default is not None and annotated_spec is None:
            annotated_spec = Field(hook=hook_from_default)

        field_type, args, optional = _infer_type(annotation, raw_default)
        fields.append(
            _Field(
                name=param.name,
                type=field_type,
                default=raw_default,
                args=args,
                optional=optional,
                spec=annotated_spec,  # None → resolved later in Config.__init__
            )
        )

    if include:
        order = {name: i for i, name in enumerate(include)}
        fields.sort(key=lambda f: order.get(f.name, len(include)))

    return fields


# Field types with built-in coercion validation.
_VALIDATABLE = frozenset({"str", "int", "float", "list", "tuple", "path"})

# Config.__init__ kwargs that must not appear as field names.
_RESERVED = frozenset(
    {
        "_field_specs",
        "_styles",
        "_class_names",
        "_cols",
        "_show_docstring",
        "_exclude",
        "_include",
        "_initial_values",
        "_validator",
        "_field_components",
    }
)


def _to_widget_value(f: _Field, val: Any) -> Any:
    """Convert a typed Python value to its widget representation.

    For ``datetime`` fields returns a ``(date_str, time_str)`` tuple.
    For all other types returns a single scalar value.
    """
    if f.type == "datetime":
        if isinstance(val, datetime):
            return val.date().isoformat(), val.strftime("%H:%M")
        return None, None
    if f.type == "date":
        return val.isoformat() if isinstance(val, date) else None
    if f.type == "bool":
        return [f.name] if val else []
    if f.type in ("list", "tuple"):
        return ", ".join(str(v) for v in val) if val else ""
    if f.type == "enum":
        return val.name if isinstance(val, Enum) else (val or "")
    if f.type == "dict":
        return json.dumps(val, indent=2) if val is not None else ""
    if f.type == "path":
        return str(val) if val is not None else ""
    return val if val is not None else ""


def _has_error_span(f: _Field) -> bool:
    """True if this field should have an error span rendered."""
    if f.spec and f.spec.component:
        return False  # custom component — caller manages errors
    return f.type in _VALIDATABLE or bool(f.spec and f.spec.validator)


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
        elif f.type in ("list", "tuple"):
            items = [x.strip() for x in str(value).split(",") if x.strip()]
            if f.type == "list":
                elem_type = f.args[0] if f.args else str
                [elem_type(x) for x in items]
            elif f.args:
                tuple(t(v) for t, v in zip(f.args, items, strict=False))
            spec = f.spec
            if spec:
                if spec.min_length is not None and len(items) < spec.min_length:
                    return f"Minimum {spec.min_length} items"
                if spec.max_length is not None and len(items) > spec.max_length:
                    return f"Maximum {spec.max_length} items"
    except (ValueError, TypeError):
        return "Invalid value"

    if f.type in ("str", "path"):
        s = str(value)
        spec = f.spec
        if spec:
            if spec.min_length is not None and len(s) < spec.min_length:
                return f"Minimum {spec.min_length} characters"
            if spec.max_length is not None and len(s) > spec.max_length:
                return f"Maximum {spec.max_length} characters"
            if spec.pattern is not None and not re.fullmatch(spec.pattern, s):
                return f"Must match: {spec.pattern}"

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
    field_maker: Any,
) -> html.Div:
    """Build a labeled input component for a single field."""
    spec = f.spec or Field()
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

    component = field_maker(config_id, f, spec, fid)
    children = [label, component]
    if spec.description:
        children.append(
            html.Small(spec.description, style={"color": "#666", "display": "block"})
        )
    if _has_error_span(f):
        children.append(
            html.Small(
                "",
                id=f"_dft_err_{config_id}_{f.name}",
                style={"color": "#d9534f", "fontSize": "0.8em", "display": "none"},
            )
        )
    return html.Div(children, style=wrapper_style or None)




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
