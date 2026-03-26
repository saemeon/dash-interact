"""Parameter detection for gallery scripts.

Two ways to declare configurable parameters in gallery scripts:

1. **Decorator** — register a function with typed arguments::

    from gallery_viewer import gallery_param

    @gallery_param
    def configure(title: str = "Q4 Revenue", dpi: int = 150):
        pass  # values are injected by the gallery

2. **Convention** — type-annotated assignments in the Configurator section::

    # In the Configurator section:
    title: str = "Q4 Revenue"
    dpi: int = 150

Both approaches produce a ``dict[str, ParamSpec]`` that the Gallery uses
to auto-generate form fields via dash-fn-forms.
"""

from __future__ import annotations

import ast
import inspect
import re
import typing
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ParamSpec:
    """A detected parameter with its type and default value."""

    name: str
    annotation: type | None = None
    default: Any = None

    @property
    def type_name(self) -> str:
        if self.annotation is None:
            return "str"
        if hasattr(self.annotation, "__name__"):
            return self.annotation.__name__
        return str(self.annotation)


# ---------------------------------------------------------------------------
# Decorator approach
# ---------------------------------------------------------------------------

_registered_params: dict[str, ParamSpec] = {}


def gallery_param(fn: Callable) -> Callable:
    """Register a function's typed parameters for the gallery sidebar.

    Usage in a gallery script's Configurator section::

        from gallery_viewer import gallery_param

        @gallery_param
        def configure(title: str = "Q4 Revenue", dpi: int = 150):
            pass

    The gallery will detect these and generate form fields.
    """
    sig = inspect.signature(fn)
    for name, param in sig.parameters.items():
        ann = param.annotation if param.annotation != inspect.Parameter.empty else str
        default = param.default if param.default != inspect.Parameter.empty else ""
        _registered_params[name] = ParamSpec(name=name, annotation=ann, default=default)
    return fn


def get_registered_params() -> dict[str, ParamSpec]:
    """Return parameters registered via @gallery_param."""
    return dict(_registered_params)


def clear_registered_params():
    """Clear the registry (used between script executions)."""
    _registered_params.clear()


# ---------------------------------------------------------------------------
# Convention approach — parse typed assignments from source code
# ---------------------------------------------------------------------------

_SUPPORTED_TYPES = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
}


def parse_typed_assignments(source: str) -> dict[str, ParamSpec]:
    """Extract ``name: type = value`` assignments from Python source.

    Only supports simple types (str, int, float, bool) and literal defaults.

    Parameters
    ----------
    source :
        Python source code to parse.

    Returns
    -------
    dict :
        Mapping of parameter name to ParamSpec.
    """
    params: dict[str, ParamSpec] = {}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return params

    for node in ast.walk(tree):
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name):
            continue
        name = node.target.id

        # Skip private/dunder names
        if name.startswith("_"):
            continue

        # Get type annotation
        ann_type = None
        if isinstance(node.annotation, ast.Name):
            ann_type = _SUPPORTED_TYPES.get(node.annotation.id)
        if isinstance(node.annotation, ast.Attribute):
            # e.g. typing.Optional — skip complex types
            continue

        if ann_type is None:
            continue

        # Get default value
        default = ""
        if node.value is not None:
            try:
                default = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue

        params[name] = ParamSpec(name=name, annotation=ann_type, default=default)

    return params


def detect_params(configurator_source: str) -> dict[str, ParamSpec]:
    """Detect parameters from a Configurator section using both approaches.

    1. Parse typed assignments (``title: str = "Q4"``)
    2. If a ``@gallery_param`` decorator is present, those take precedence

    Parameters
    ----------
    configurator_source :
        The source code of the Configurator section.

    Returns
    -------
    dict :
        Mapping of parameter name to ParamSpec.
    """
    # Convention-based detection
    params = parse_typed_assignments(configurator_source)

    # Decorator-based detection takes precedence
    # (the decorator registers params when the script is executed,
    #  but we can also detect it statically from the source)
    if "@gallery_param" in configurator_source:
        # Parse the decorated function's signature from AST
        try:
            tree = ast.parse(configurator_source)
        except SyntaxError:
            return params

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            # Check if decorated with @gallery_param
            for dec in node.decorator_list:
                dec_name = None
                if isinstance(dec, ast.Name):
                    dec_name = dec.id
                elif isinstance(dec, ast.Attribute):
                    dec_name = dec.attr
                if dec_name == "gallery_param":
                    # Parse the function's arguments
                    for arg in node.args.args:
                        name = arg.arg
                        ann_type = None
                        if isinstance(arg.annotation, ast.Name):
                            ann_type = _SUPPORTED_TYPES.get(arg.annotation.id)
                        if ann_type is None:
                            ann_type = str

                        # Find default (ast.FunctionDef.args.defaults is right-aligned)
                        defaults = node.args.defaults
                        arg_idx = node.args.args.index(arg)
                        default_idx = arg_idx - (len(node.args.args) - len(defaults))
                        default = ""
                        if default_idx >= 0 and default_idx < len(defaults):
                            try:
                                default = ast.literal_eval(defaults[default_idx])
                            except (ValueError, TypeError):
                                pass

                        params[name] = ParamSpec(
                            name=name, annotation=ann_type, default=default
                        )

    return params
