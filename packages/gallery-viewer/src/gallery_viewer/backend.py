"""Storage backend abstraction for gallery-viewer.

The ``StorageBackend`` base class defines the interface for loading and saving
versioned scripts, data, and plots.  Subclass it or override individual methods
to plug in company-specific storage (S3, database, git, ...).

``FileSystemBackend`` is the default implementation that works with a flat
directory layout::

    base_dir/
        data/   data_{date}.csv
        plots/  plot_{date}_v{version}.png
        scripts/script_{date}_v{version}.py
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from datetime import date as _date
from pathlib import Path
from typing import Callable

import pandas as pd

from gallery_viewer._types import RunResult, ScriptSections


class StorageBackend:
    """Base class for gallery storage.

    Override any method to customise discovery, loading, saving, or execution.
    """

    # -- Discovery -----------------------------------------------------------

    def list_dates(self) -> list[str]:
        """Return available dates, newest first."""
        return []

    def list_versions(self, date: str) -> list[str]:
        """Return available versions for *date*, ascending."""
        return []

    # -- Loading -------------------------------------------------------------

    def load_script(self, date: str, version: str) -> ScriptSections:
        """Load script content for a given date/version."""
        return ScriptSections()

    def load_data(self, date: str) -> pd.DataFrame | None:
        """Load a data preview for *date* (may return ``None``)."""
        return None

    def load_plot(self, date: str, version: str) -> bytes | None:
        """Load the plot image bytes for *date*/*version*."""
        return None

    # -- Saving --------------------------------------------------------------

    def save_version(self, date: str, sections: ScriptSections) -> str:
        """Persist *sections* and return the new version identifier."""
        raise NotImplementedError

    # -- Execution -----------------------------------------------------------

    def run_preview(self, sections: ScriptSections) -> RunResult:
        """Run Load + Plot, capture a preview image, return result."""
        return _run_sections(sections, include_save=False)

    def run_full(self, sections: ScriptSections) -> RunResult:
        """Run Load + Plot + Save, return result."""
        return _run_sections(sections, include_save=True)

    # -- Templates -----------------------------------------------------------

    def starter_template(self, date: str) -> ScriptSections:
        """Return a starter script for a new date (override for branding)."""
        return ScriptSections(
            load=(
                "import pandas as pd\n"
                "import matplotlib\n"
                'matplotlib.use("Agg")\n'
                "import matplotlib.pyplot as plt\n"
            ),
            plot=(
                "fig, ax = plt.subplots(figsize=(8, 5))\n"
                "# ax.plot(...)\n"
                "plt.tight_layout()"
            ),
            save="# plt.savefig(...)",
        )


# ---------------------------------------------------------------------------
# Default subprocess runner (shared by all backends)
# ---------------------------------------------------------------------------

def _run_sections(
    sections: ScriptSections,
    include_save: bool,
    timeout: int = 60,
    cwd: Path | None = None,
) -> RunResult:
    """Execute script sections in a subprocess, capturing output and plot."""
    preview_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    preview_path = Path(preview_file.name)
    preview_file.close()

    if include_save:
        code = sections.to_full()
    else:
        code = sections.to_preview()
        # Auto-save preview (appended after the code)
        code += (
            "\n\nimport matplotlib.pyplot as _plt\n"
            f"_plt.savefig(r'{preview_path}', dpi=100, bbox_inches='tight')\n"
        )

    # Write script inside cwd/scripts/ so Path(__file__).parent.parent == cwd
    script_dir = (cwd / "scripts") if cwd else Path(tempfile.gettempdir())
    script_dir.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", delete=False, dir=str(script_dir),
    )
    tmp.write(code)
    tmp.close()
    tmp_path = Path(tmp.name)

    try:
        result = subprocess.run(
            [sys.executable, str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
        )
        output = result.stdout or ""
        error = result.stderr or ""
        success = result.returncode == 0
    except subprocess.TimeoutExpired:
        output = ""
        error = f"Script timed out after {timeout} seconds."
        success = False
    finally:
        tmp_path.unlink(missing_ok=True)

    plot_bytes = None
    if preview_path.exists():
        plot_bytes = preview_path.read_bytes()
        preview_path.unlink(missing_ok=True)

    return RunResult(
        output=output.strip(),
        error=error.strip(),
        plot_bytes=plot_bytes,
        success=success,
    )


# ---------------------------------------------------------------------------
# FileSystemBackend
# ---------------------------------------------------------------------------

def _patch_version_in_code(sections: ScriptSections, date: str, version: int) -> ScriptSections:
    """Prepend correct ``date`` and ``version`` to the Save section.

    The Code section keeps its original date (for data loading).
    The Save section gets fresh assignments so output filenames are correct.
    """
    # Prepend overrides at the top of the Save section
    save_prefix = f'date = "{date}"\nversion = {version}\n'
    patched_save = save_prefix + sections.save

    return ScriptSections(
        configurator=sections.configurator,
        code=sections.code,
        save=patched_save,
    )


class FileSystemBackend(StorageBackend):
    """Default backend: versioned files in ``data/``, ``plots/``, ``scripts/``.

    Parameters
    ----------
    base_dir :
        Root directory containing data/, plots/, scripts/ subdirectories.
    data_pattern :
        Regex with a ``date`` group for data files.
    script_pattern :
        Regex with ``date`` and ``version`` groups for script files.
    plot_pattern :
        Regex with ``date`` and ``version`` groups for plot files.
    starter_template_fn :
        Optional callable ``(date, base_dir) -> ScriptSections`` for custom
        script templates.
    """

    def __init__(
        self,
        base_dir: str | Path = ".",
        data_pattern: str = r"data_(?P<date>\d{8})\.(csv|parquet)$",
        script_pattern: str = r"script_(?P<date>\d{8})_v(?P<version>\d+)\.py$",
        plot_pattern: str = r"plot_(?P<date>\d{8})_v(?P<version>\d+)\.png$",
        starter_template_fn: Callable[[str, Path], ScriptSections] | None = None,
    ):
        self.base_dir = Path(base_dir).resolve()
        self.data_dir = self.base_dir / "data"
        self.plots_dir = self.base_dir / "plots"
        self.scripts_dir = self.base_dir / "scripts"

        self._data_re = re.compile(data_pattern)
        self._script_re = re.compile(script_pattern)
        self._plot_re = re.compile(plot_pattern)
        self._starter_template_fn = starter_template_fn

    @classmethod
    def discover(
        cls,
        base_dir: str | Path,
        **kwargs,
    ) -> dict[str, "FileSystemBackend"]:
        """Auto-discover sub-plots from a directory.

        Each subdirectory of *base_dir* that contains a ``data/`` or
        ``scripts/`` folder is treated as a separate plot.  Returns a dict
        mapping plot name → backend.

        Parameters
        ----------
        base_dir :
            Parent directory to scan.
        **kwargs :
            Extra arguments forwarded to each ``FileSystemBackend()``.
        """
        base = Path(base_dir).resolve()
        backends: dict[str, FileSystemBackend] = {}
        for child in sorted(base.iterdir()):
            if not child.is_dir():
                continue
            if (child / "data").is_dir() or (child / "scripts").is_dir():
                backends[child.name] = cls(child, **kwargs)
        return backends

    # -- Discovery -----------------------------------------------------------

    def list_dates(self) -> list[str]:
        dates: set[str] = set()
        if self.data_dir.exists():
            for f in self.data_dir.iterdir():
                m = self._data_re.match(f.name)
                if m:
                    dates.add(m.group("date"))
        return sorted(dates, reverse=True)

    def list_versions(self, date: str) -> list[str]:
        versions: list[int] = []
        if self.scripts_dir.exists():
            for f in self.scripts_dir.iterdir():
                m = self._script_re.match(f.name)
                if m and m.group("date") == date:
                    versions.append(int(m.group("version")))
        return [str(v) for v in sorted(versions)] or ["1"]

    # -- Loading -------------------------------------------------------------

    def load_script(self, date: str, version: str) -> ScriptSections:
        path = self.scripts_dir / f"script_{date}_v{version}.py"
        if path.exists():
            return ScriptSections.from_text(path.read_text())
        return self.starter_template(date)

    def load_data(self, date: str) -> pd.DataFrame | None:
        for ext in ("csv", "parquet"):
            p = self.data_dir / f"data_{date}.{ext}"
            if p.exists():
                return pd.read_parquet(p) if ext == "parquet" else pd.read_csv(p)
        return None

    def load_plot(self, date: str, version: str) -> bytes | None:
        path = self.plots_dir / f"plot_{date}_v{version}.png"
        if path.exists():
            return path.read_bytes()
        return None

    # -- Saving --------------------------------------------------------------

    def save_version(self, date: str, sections: ScriptSections) -> str:
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self.plots_dir.mkdir(parents=True, exist_ok=True)
        today = _date.today().strftime("%Y%m%d")
        existing = []
        if self.scripts_dir.exists():
            for f in self.scripts_dir.iterdir():
                m = self._script_re.match(f.name)
                if m and m.group("date") == today:
                    existing.append(int(m.group("version")))
        new_version = max(existing, default=0) + 1

        # Patch version and date in the script code so the save section
        # writes to the correct output path
        patched = _patch_version_in_code(sections, today, new_version)

        path = self.scripts_dir / f"script_{today}_v{new_version}.py"
        path.write_text(patched.to_text())

        # Run the script: first try full (which includes user's save code),
        # then always capture a preview as fallback
        self.run_full(patched)

        plot_path = self.plots_dir / f"plot_{today}_v{new_version}.png"
        if not plot_path.exists():
            # Script didn't save a plot itself — capture preview
            result = self.run_preview(patched)
            if result.plot_bytes:
                plot_path.write_bytes(result.plot_bytes)

        return str(new_version)

    # -- Execution (override to set cwd) ------------------------------------

    def run_preview(self, sections: ScriptSections) -> RunResult:
        return _run_sections(sections, include_save=False, cwd=self.base_dir)

    def run_full(self, sections: ScriptSections) -> RunResult:
        return _run_sections(sections, include_save=True, cwd=self.base_dir)

    # -- Templates -----------------------------------------------------------

    def starter_template(self, date: str) -> ScriptSections:
        if self._starter_template_fn is not None:
            return self._starter_template_fn(date, self.base_dir)

        data_path = self.data_dir / f"data_{date}.csv"
        return ScriptSections(
            configurator=(
                f'title: str = "{date}"\n'
                'dpi: int = 100'
            ),
            code=(
                "import pandas as pd\n"
                "import matplotlib\n"
                'matplotlib.use("Agg")\n'
                "import matplotlib.pyplot as plt\n"
                "from pathlib import Path\n"
                "\n"
                f'BASE_DIR = Path(r"{self.base_dir}")\n'
                f'date = "{date}"\n'
                "\n"
                f'df = pd.read_csv(r"{data_path}")\n'
                "\n"
                "fig, ax = plt.subplots(figsize=(8, 5))\n"
                "ax.plot(df.iloc[:, 0], df.iloc[:, 1], marker='o', linewidth=2)\n"
                "ax.set_title(title)\n"
                "ax.set_xlabel(df.columns[0])\n"
                "ax.set_ylabel(df.columns[1])\n"
                "ax.grid(True, alpha=0.3)\n"
                "plt.tight_layout()"
            ),
            save=(
                "version = 1\n"
                'out = BASE_DIR / "plots" / f"plot_{date}_v{version}.png"\n'
                "out.parent.mkdir(parents=True, exist_ok=True)\n"
                "plt.savefig(out, dpi=dpi)\n"
                'print(f"Saved {out}")'
            ),
        )
