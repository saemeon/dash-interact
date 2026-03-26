[![PyPI](https://img.shields.io/pypi/v/dash-interact)](https://pypi.org/project/dash-interact/)
[![Python](https://img.shields.io/pypi/pyversions/dash-interact)](https://pypi.org/project/dash-interact/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Dash](https://img.shields.io/badge/Dash-008DE4?logo=plotly&logoColor=white)](https://dash.plotly.com/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![prek](https://img.shields.io/badge/prek-checked-blue)](https://github.com/saemeon/prek)

# dash-interact

pyplot-style convenience layer for Plotly Dash — build interactive apps top-to-bottom with no boilerplate.

## Installation

```bash
pip install dash-interact
```

## Quick example

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

## The page API

`page` works like `matplotlib.pyplot` — a module-level singleton that accumulates content.

```python
from dash_interact import page

page.H1("Title")          # adds html.H1
page.Hr()                 # adds html.Hr
@page.interact            # adds an interact panel
def my_fn(...): ...
page.run()                # builds the Dash app and starts the server
```

## The interact family

Three levels mirroring ipywidgets:

```python
from dash_interact import interact, interactive, interactive_output

# 1. Fire and forget — attaches to the current page
@interact
def plot(amplitude: float = 1.0): ...

# 2. Embeddable — place it yourself
panel = interactive(plot, amplitude=(0, 2, 0.1))

# 3. Fully decoupled — pre-built form, separate output
form = FnForm("plot", plot)
output = interactive_output(plot, form)
```

## License

MIT
