# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Shared utilities."""

from __future__ import annotations

import inspect


def _caller_name(skip_modules: set[str]) -> str:
    """Walk the call stack to find the first frame outside *skip_modules*."""
    for info in inspect.stack():
        mod = info.frame.f_globals.get("__name__", "")
        if mod and mod not in skip_modules:
            return mod
    return "__main__"


def _in_jupyter() -> bool:
    """Return True when running inside a Jupyter kernel."""
    try:
        from IPython import get_ipython  # noqa: PLC0415

        return get_ipython().__class__.__name__ == "ZMQInteractiveShell"
    except (ImportError, AttributeError):
        return False
