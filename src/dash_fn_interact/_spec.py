# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Public types: FieldHook, FromComponent, Field, fixed."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from dash import State

# --- hook protocol ---


class FieldHook:
    """Base class for field hooks.

    Subclass to define fields whose default value and/or submitted value
    are derived from runtime Dash state rather than a static default.

    Override :meth:`required_states` to declare which Dash ``State`` objects
    your hook needs. Their values are passed positionally to :meth:`get_default`
    and :meth:`transform`.
    """

    def required_states(self) -> list[State]:
        """Dash ``State`` objects this hook needs at runtime."""
        return []

    def get_default(self, *state_values: Any) -> Any:
        """Compute the initial field value from resolved state values."""
        return None

    def transform(self, value: Any, *state_values: Any) -> Any:
        """Transform the user-submitted value before it reaches the renderer."""
        return value


class FromComponent(FieldHook):
    """Read a component property as the field default.

    Parameters
    ----------
    component :
        Any Dash component with an ``.id`` attribute.
    prop :
        The component property to read (e.g. ``"value"``, ``"figure"``).
    """

    def __init__(self, component: Any, prop: str):
        self._state = State(component.id, prop)

    def required_states(self) -> list[State]:
        return [self._state]

    def get_default(self, *state_values: Any) -> Any:
        return state_values[0] if state_values else None


# --- fixed ---


class _FieldFixed:
    """Sentinel returned by :func:`fixed`. Internal — use ``fixed()`` instead."""

    def __init__(self, value: Any) -> None:
        self.value = value


def fixed(value: Any) -> _FieldFixed:
    """Pass a constant to the function without rendering a UI control.

    Analogous to ``ipywidgets.fixed()``.  The field is hidden from the form
    but its value is always injected by :meth:`~dash_fn_interact.Config.build_kwargs`.

    Example::

        cfg = FnForm("render", fn, fig=fixed(current_figure))
        # "fig" has no widget; build_kwargs always returns {"fig": current_figure, ...}

        panel = interact(fn, context=fixed(some_value))
    """
    return _FieldFixed(value)


# --- Field ---


@dataclass
class Field:
    """Per-field configuration for :class:`~dash_fn_interact.FnForm`.

    Can be supplied in three ways (highest priority wins):

    1. **In-signature** via ``Annotated[T, Field(...)]`` — for functions
       you own.
    2. **External** via keyword argument on
       :class:`~dash_fn_interact.FnForm` — for functions you don't own.
    3. Type-level ``_styles`` / ``_class_names`` dicts on
       :class:`~dash_fn_interact.FnForm` fill in any visual properties
       not set by the above.

    A :class:`FieldHook` instance may also be passed directly as a kwarg
    and is treated as ``Field(hook=hook)``.
    """

    # --- default value ---
    default: Any = None
    """Default value for the field.

    Used in :class:`~dash_fn_interact.Form` declarative subclasses::

        class MyForm(Form):
            dpi: int = Field(min=72, max=300, default=150)

    Ignored when the field is defined via a typed callable (the callable's
    parameter default takes precedence).
    """

    # --- label / help ---
    label: str | None = None
    """Override the auto-generated label (default: param name in title case)."""
    description: str | None = None
    """Help text rendered below the component."""

    # --- layout ---
    col_span: int = 1
    """Column span in a multi-column grid (see ``_cols`` on :func:`build_config`)."""

    # --- styling ---
    style: dict | None = None
    """CSS dict applied to the component (not the wrapper div)."""
    class_name: str = ""
    """CSS class applied to the component."""

    # --- component override ---
    component: Any = None
    """Replace the auto-generated component entirely. ``id`` is set internally."""
    component_prop: str = "value"
    """Property to read back from a custom ``component`` (default: ``"value"``)."""
    widget: str | None = None
    """Select an alternative widget for supported types.

    * ``"slider"`` — render a ``dcc.Slider`` (or ``dmc.Slider``) instead of a
      number input.  Requires ``min`` and ``max`` to be set.
    """

    # --- numeric constraints (int / float only) ---
    min: float | None = None
    """Minimum value (inclusive). Only applied to ``int`` / ``float`` fields."""
    max: float | None = None
    """Maximum value (inclusive). Only applied to ``int`` / ``float`` fields."""
    step: float | int | str | None = None
    """Step size. Only applied to ``int`` / ``float`` fields."""

    # pydantic-style aliases — resolved in __post_init__, canonical names win
    ge: float | None = field(default=None, repr=False)
    """Alias for ``min`` (greater-than-or-equal). Ignored if ``min`` is set."""
    le: float | None = field(default=None, repr=False)
    """Alias for ``max`` (less-than-or-equal). Ignored if ``max`` is set."""
    gt: float | None = field(default=None, repr=False)
    """Alias for ``min`` (greater-than, exclusive semantics not enforced by widget).
    Ignored if ``min`` is set."""
    lt: float | None = field(default=None, repr=False)
    """Alias for ``max`` (less-than, exclusive semantics not enforced by widget).
    Ignored if ``max`` is set."""
    multiple_of: float | int | None = field(default=None, repr=False)
    """Alias for ``step``. Ignored if ``step`` is set."""

    # --- string / collection constraints ---
    min_length: int | None = None
    """Minimum length. For ``str`` / ``path``: character count.
    For ``list`` / ``tuple``: item count."""
    max_length: int | None = None
    """Maximum length. For ``str`` / ``path``: character count.
    For ``list`` / ``tuple``: item count."""
    pattern: str | None = None
    """Regex the value must fully match. Only applied to ``str`` / ``path`` fields."""

    # --- runtime default ---
    hook: FieldHook | None = None
    """Runtime hook that derives the field's default from Dash state."""

    # --- input behaviour ---
    persist: bool = False
    """Persist the field value across page reloads using the browser's session storage.

    When ``True``, the generated component is rendered with
    ``persistence=True, persistence_type="session"`` so the browser remembers
    the last value even after a full page refresh.  Set to ``False`` (default)
    to keep the component stateless (always loads with the default value).

    Equivalent to wrapping every field manually in a ``dcc.Store`` —
    useful for sliders or dropdowns whose position the user adjusts frequently.
    """

    debounce: bool | None = None
    """Control debounce on ``dcc.Input`` / ``dcc.Textarea`` fields.

    * ``None`` (default) — use the type default (``True`` for all text and
      number inputs).
    * ``False`` — update on every keystroke (useful for live search/filter).
    * ``True`` — force debounce even if the type default would be ``False``.

    Has no effect on ``bool``, ``date``, ``datetime``, ``literal``, or
    ``enum`` fields, which don't use debounce.
    """

    # --- interactivity ---
    visible: tuple | None = None
    """Conditional visibility rule: ``("other_field", "==", value)``."""

    # --- validation ---
    validator: Callable[[Any], str | None] | None = None
    """Custom validator called with the *coerced* value after type checking.

    Return a human-readable error string on failure, ``None`` on success.

    Example::

        Field(validator=lambda v: "Must be positive" if v <= 0 else None)
        Field(validator=lambda v: None if "@" in v else "Not a valid email")

    Can also be supplied as a bare callable in ``Annotated`` metadata::

        def positive(v): return "Must be > 0" if v <= 0 else None

        def fn(dpi: Annotated[int, positive] = 150): ...
    """

    def __post_init__(self) -> None:
        # Resolve pydantic-style aliases into canonical names.
        # Canonical names always win — aliases only fill in when not set.
        if self.min is None:
            if self.ge is not None:
                self.min = self.ge
            elif self.gt is not None:
                self.min = self.gt
        if self.max is None:
            if self.le is not None:
                self.max = self.le
            elif self.lt is not None:
                self.max = self.lt
        if self.step is None and self.multiple_of is not None:
            self.step = self.multiple_of
