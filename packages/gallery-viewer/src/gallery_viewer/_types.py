"""Core data types for gallery-viewer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScriptSections:
    """A script split into Configurator, Code, and Save sections.

    - **Configurator**: Typed variable assignments rendered as form fields.
    - **Code**: The main script logic (imports, data, plotting).
    - **Save**: Only executed on "Save Version" (writes files to disk).

    RUN  = Configurator + Code  (preview only)
    SAVE = Configurator + Code + Save  (writes to disk)
    """

    configurator: str = ""
    code: str = ""
    save: str = ""

    MARKER_CONFIGURATOR = "# === CONFIGURATOR ==="
    MARKER_CODE = "# === CODE ==="
    MARKER_SAVE = "# === SAVE ==="

    # Legacy markers (backwards compat)
    _LEGACY_LOAD = "# === LOAD ==="
    _LEGACY_PLOT = "# === PLOT ==="

    @classmethod
    def from_text(cls, text: str) -> ScriptSections:
        """Parse a script with section markers."""
        # New format: CONFIGURATOR + CODE + SAVE
        if cls.MARKER_CONFIGURATOR in text or cls.MARKER_CODE in text:
            parts: dict[str, list[str]] = {"configurator": [], "code": [], "save": []}
            current = None
            for line in text.splitlines():
                stripped = line.strip()
                if stripped == cls.MARKER_CONFIGURATOR:
                    current = "configurator"
                elif stripped == cls.MARKER_CODE:
                    current = "code"
                elif stripped == cls.MARKER_SAVE:
                    current = "save"
                elif current:
                    parts[current].append(line)
            return cls(
                configurator="\n".join(parts["configurator"]).strip(),
                code="\n".join(parts["code"]).strip(),
                save="\n".join(parts["save"]).strip(),
            )

        # Legacy format: LOAD + PLOT + SAVE
        if cls._LEGACY_LOAD in text:
            parts_legacy: dict[str, list[str]] = {"load": [], "plot": [], "save": []}
            current = None
            for line in text.splitlines():
                stripped = line.strip()
                if stripped == cls._LEGACY_LOAD:
                    current = "load"
                elif stripped == cls._LEGACY_PLOT:
                    current = "plot"
                elif stripped == "# === SAVE ===" or stripped == cls.MARKER_SAVE:
                    current = "save"
                elif current:
                    parts_legacy[current].append(line)
            load = "\n".join(parts_legacy["load"]).strip()
            plot = "\n".join(parts_legacy["plot"]).strip()
            save = "\n".join(parts_legacy["save"]).strip()
            code_parts = [p for p in [load, plot] if p]
            return cls(configurator="", code="\n\n".join(code_parts), save=save)

        # No markers — everything is code
        return cls(code=text.strip())

    def to_text(self) -> str:
        """Join sections back into a single script."""
        parts = []
        if self.configurator:
            parts.append(f"{self.MARKER_CONFIGURATOR}\n{self.configurator}")
        parts.append(f"{self.MARKER_CODE}\n{self.code}")
        if self.save:
            parts.append(f"{self.MARKER_SAVE}\n{self.save}")
        return "\n\n".join(parts) + "\n"

    def to_preview(self) -> str:
        """Configurator + Code (for RUN — no Save)."""
        if self.configurator:
            return self.configurator + "\n\n" + self.code
        return self.code

    def to_full(self) -> str:
        """Configurator + Code + Save (for Save Version)."""
        parts = []
        if self.configurator:
            parts.append(self.configurator)
        parts.append(self.code)
        if self.save:
            parts.append(self.save)
        return "\n\n".join(parts)


@dataclass
class RunResult:
    """Result of executing a script."""

    output: str = ""
    error: str = ""
    plot_bytes: bytes | None = None
    success: bool = True
