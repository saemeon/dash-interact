"""JSON config file for gallery-viewer.

The config is the gallery's persistent state — it tracks which plots exist,
their paths, and metadata.  The dashboard reads AND writes this file
(e.g. when the user adds a new plot via the UI).

Format::

    {
      "title": "My Gallery",
      "plots": {
        "revenue_chart": {
          "path": "./revenue",
          "description": "Quarterly revenue analysis"
        },
        "inflation": {
          "path": "./inflation",
          "description": "CPI tracking"
        }
      }
    }

Usage::

    from gallery_viewer import Gallery

    gallery = Gallery.from_config("gallery.json")
    gallery.run()
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from gallery_viewer.backend import FileSystemBackend, StorageBackend


def load_config(path: str | Path) -> dict:
    """Load a gallery config JSON file."""
    path = Path(path)
    if not path.exists():
        return {"title": "Gallery Viewer", "plots": {}}
    with open(path) as f:
        return json.load(f)


def save_config(config: dict, path: str | Path) -> None:
    """Atomically write a gallery config JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write to temp file first, then rename (atomic on same filesystem)
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", dir=path.parent, delete=False,
    )
    try:
        json.dump(config, tmp, indent=2)
        tmp.write("\n")
        tmp.close()
        Path(tmp.name).replace(path)
    except Exception:
        Path(tmp.name).unlink(missing_ok=True)
        raise


def backends_from_config(
    config: dict,
    base_dir: str | Path | None = None,
    **backend_kwargs: Any,
) -> dict[str, StorageBackend]:
    """Create backends from a config dict.

    Parameters
    ----------
    config :
        Parsed gallery config (from ``load_config``).
    base_dir :
        If plot paths in the config are relative, resolve them relative
        to this directory.  Defaults to the current directory.
    **backend_kwargs :
        Extra kwargs forwarded to each ``FileSystemBackend()``.
    """
    base = Path(base_dir or ".").resolve()
    backends: dict[str, StorageBackend] = {}
    for name, plot_cfg in config.get("plots", {}).items():
        plot_path = Path(plot_cfg["path"])
        if not plot_path.is_absolute():
            plot_path = base / plot_path
        backends[name] = FileSystemBackend(plot_path, **backend_kwargs)
    return backends


def add_plot_to_config(
    config: dict,
    name: str,
    path: str | Path,
    description: str = "",
    create_dirs: bool = True,
) -> dict:
    """Add a new plot entry to the config and optionally create directories.

    Parameters
    ----------
    config :
        The config dict to modify (mutated in place and returned).
    name :
        Plot name (used as key in the config and sidebar label).
    path :
        Directory path for this plot's data/plots/scripts.
    description :
        Human-readable description shown in the UI.
    create_dirs :
        If True, create the ``data/``, ``plots/``, ``scripts/``
        subdirectories under *path*.

    Returns
    -------
    dict :
        The modified config.
    """
    plot_path = Path(path)
    if create_dirs:
        (plot_path / "data").mkdir(parents=True, exist_ok=True)
        (plot_path / "plots").mkdir(parents=True, exist_ok=True)
        (plot_path / "scripts").mkdir(parents=True, exist_ok=True)

    if "plots" not in config:
        config["plots"] = {}

    config["plots"][name] = {
        "path": str(path),
        "description": description,
    }
    return config


def remove_plot_from_config(config: dict, name: str) -> dict:
    """Remove a plot entry from the config (does NOT delete directories).

    Parameters
    ----------
    config :
        The config dict to modify.
    name :
        Plot name to remove.

    Returns
    -------
    dict :
        The modified config.
    """
    config.get("plots", {}).pop(name, None)
    return config
