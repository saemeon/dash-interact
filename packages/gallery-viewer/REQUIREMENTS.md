# gallery-viewer — Requirements

## What is it?

A generic, configurable dashboard for browsing, editing, and running versioned data visualization scripts. Built on Dash, designed so that any company can wrap it with their own corporate design and storage backend.

## How it fits in the ecosystem

```
gallery-viewer (generic engine)
    |
    |-- used by --> corpframe.gallery (company wrapper)
    |                   |-- uses --> corpframe (corporate design)
    |                   |-- uses --> dash-capture (optional export)
    |
    |-- depends on --> dash, dash-bootstrap-components, pandas
    |-- optional ----> dash-ace (syntax highlighting)
```

The gallery-viewer does NOT know about corporate design, capture pipelines, or Shiny. It only knows about backends, scripts, and plots.

## Core concepts

- **Plot**: A named collection of versioned scripts, data files, and output images.
- **Backend**: Pluggable storage layer (filesystem, S3, database, git...).
- **Script**: A Python file with two sections — Configurator (typed parameters) and Code (the actual logic).
- **gallery.json**: Config file listing available plots. The dashboard reads and writes it.

## User stories

### Data analyst

> As a data analyst, I want to open a dashboard, select a plot from the sidebar, tweak parameters (title, DPI, date range) via form fields, click RUN, and see the result immediately — without editing Python code.

### Data scientist

> As a data scientist, I want to write a matplotlib script, save it as a new version, and have it appear in the gallery alongside previous versions — so I can compare outputs over time.

### Team lead

> As a team lead, I want to add a new plot type to the gallery from the dashboard (click "+ Add Plot", give it a name) — without touching config files or creating folders manually.

### DevOps / IT

> As an IT admin, I want to plug in a custom storage backend (e.g. S3 or a shared network drive) by subclassing `StorageBackend` — without forking the gallery code.

### Company design owner

> As the person responsible for corporate design, I want to wrap the gallery with `corpframe` so all exported plots have our header/footer — by writing a 10-line `corp_gallery()` function.

## Script format

```python
# === CONFIGURATOR ===
title: str = "Q4 Revenue"
dpi: int = 150
show_target: bool = True

# === CODE ===
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
# ... load data, make plot, save ...
```

- **Configurator section**: Typed variable assignments. The gallery detects these and renders form fields. Editing a field updates the variable in the script before execution.
- **Code section**: Everything else — imports, data loading, plotting, saving. Runs as a single Python subprocess.

## Functional requirements

| # | Requirement | Status |
|---|---|---|
| F1 | Browse multiple named plots in a sidebar | Done |
| F2 | Select date and version for each plot | Done |
| F3 | View the plot image and data table | Done |
| F4 | Edit the script in a syntax-highlighted editor | Done (dash-ace) |
| F5 | Detect typed parameters and render form fields | Done |
| F6 | Run the script and show live preview | Done |
| F7 | Save as a new version (with confirmation) | Done |
| F8 | Refresh dates/versions from disk | Done |
| F9 | Search/filter plots by name | Done |
| F10 | Add new plots from the dashboard | Done (with gallery.json) |
| F11 | Pluggable storage backend | Done |
| F12 | JSON config file (read + write) | Done |
| F13 | Auto-discover plots from directory structure | Done |
| F14 | Optional export button (post-process with corpframe) | Done |

## Non-functional requirements

| # | Requirement | Status |
|---|---|---|
| N1 | No corporate-design dependency (generic) | Done |
| N2 | Works without dash-ace (falls back to textarea) | Done |
| N3 | Scripts execute in isolated subprocesses (60s timeout) | Done |
| N4 | Config file writes are atomic (temp + rename) | Done |
| N5 | Backwards-compatible with old 3-section scripts (LOAD/PLOT/SAVE) | Done |

## Future / backlog

| # | Item |
|---|---|
| B1 | Diff view between versions |
| B2 | Two-way binding: editing param fields auto-updates script AND vice versa |
| B3 | Delete plot / delete version from the dashboard |
| B4 | Authentication / access control |
| B5 | Quarto / RMarkdown integration |
| B6 | Git-backed storage backend |
| B7 | Scheduled script execution (cron-like) |
| B8 | Thumbnail previews in sidebar |
