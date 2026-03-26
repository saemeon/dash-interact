[![Python](https://img.shields.io/pypi/pyversions/dash-interact)](https://pypi.org/project/dash-interact/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

# dash-fn-tools

A framework for packaging organizational chart standards as installable Python libraries, with companion tools for interactive dashboards and one-click export from Dash and Shiny.

## Packages

### Framework

| Package | Description |
|---------|-------------|
| **mpl-brand** | Generic matplotlib corporate-design framework. Subclass, configure hooks, ship as `pip install your-brand`. |
| **corpframe** | Example implementation — a concrete corporate design using mpl-brand. |

### Forms & Interaction (Dash)

| Package | Install | Description |
|---------|---------|-------------|
| **dash-fn-form** | `pip install dash-fn-form` | Generate Dash forms from typed Python function signatures. |
| **dash-interact** | `pip install dash-interact` | pyplot-style convenience layer — `page.interact()`, HTML shorthands. Includes dash-fn-form. |

### Capture & Export

| Package | Language | Description |
|---------|----------|-------------|
| **dash-capture** | Python/Dash | Browser capture pipeline — preprocess, capture, postprocess. Pluggable strategies for Plotly, html2canvas, canvas. |
| **shinycapture** | R/Shiny | Same capture pipeline for Shiny applications. |
| **corpframe** (R) | R | Thin R wrapper — calls Python corpframe via subprocess. |

## Architecture

```
mpl-brand                    ← framework: "package your chart standards"
  └── corpframe              ← your company's implementation

dash-fn-form                ← framework: "forms from functions"
  ├── dash-interact          ← convenience: page API, interact()
  └── dash-capture           ← toolkit: browser capture pipeline
        └── corpframe[dash]  ← one-click corporate export

shinycapture                 ← toolkit: browser capture for Shiny
  └── corpframe (R)          ← one-click corporate export in R
```

## Quick Example

```python
from dash_interact import page

page.H1("My App")

@page.interact
def sine_wave(amplitude: float = 1.0, frequency: float = 2.0):
    import numpy as np, plotly.graph_objects as go
    x = np.linspace(0, 6 * np.pi, 600)
    return go.Figure(go.Scatter(x=x, y=amplitude * np.sin(frequency * x)))

page.run()
```

## License

MIT
