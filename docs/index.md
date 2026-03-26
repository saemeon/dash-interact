# dash-interact

Build interactive Plotly Dash apps from type-hinted Python functions — pyplot-style, no boilerplate.

## Installation

```bash
pip install dash-interact
```

## Quickstart

```python
from dash_interact import page

page.H1("My App")

@page.interact
def sine_wave(amplitude: float = 1.0, frequency: float = 2.0, n_cycles: int = 3):
    import numpy as np, plotly.graph_objects as go
    x = np.linspace(0, n_cycles * 2 * np.pi, 600)
    return go.Figure(go.Scatter(x=x, y=amplitude * np.sin(frequency * x)))

page.run(debug=True)
```

`@page.interact` inspects the function signature and builds the form. The return value is rendered automatically.

## Type mapping

| Python type | Control |
|---|---|
| `float` | Number input (or slider with `(min, max, step)`) |
| `int` | Number input (integer step) |
| `bool` | Checkbox |
| `Literal[A, B, C]` | Dropdown |
| `str` | Text input |
| `date` / `datetime` | Date picker |
| `list[T]` / `tuple[T, ...]` | Comma-separated text input |
| `T \| None` | Same as `T`, submits `None` when empty |

## The page API

`page` works like `matplotlib.pyplot` — a module-level singleton that accumulates content as you go.

```python
from dash_interact import page

page.H1("Title")          # adds html.H1 to the current page
page.Hr()                 # adds html.Hr
@page.interact            # adds an interact panel
def my_fn(...): ...
page.run()                # builds the Dash app and starts the server
page.current()            # returns the Page instance (for embedding)
```

Any `html.*` element is available as `page.<TagName>(...)`.

## Explicit Page object

```python
from dash_interact import Page
from dash import Dash, html

p = Page(max_width=1200, manual=True)
p.H1("My App")

@p.interact
def my_fn(...): ...

app = Dash(__name__)
app.layout = html.Div([navbar, p, footer])
app.run()
```

`Page` is a subclass of `html.Div` — use it anywhere a Dash component is accepted.

## The interact family

Three levels mirroring ipywidgets:

```python
from dash_interact import interact, interactive, interactive_output
from dash_fn_form import FnForm

# 1. Fire and forget — attaches to the current page
@interact
def plot(amplitude: float = 1.0): ...

# 2. Embeddable — place it yourself, split via .form / .output
panel = interactive(plot, amplitude=(0, 2, 0.1))
app.layout = html.Div([
    html.Div([panel.form], className="sidebar"),
    html.Div([panel.output], className="main"),
])

# 3. Fully decoupled — pre-built form, separate output area
form = FnForm("plot", plot)
output = interactive_output(plot, form)
app.layout = html.Div([
    html.Div([form], className="sidebar"),
    html.Div([output], className="main"),
])
```

## Field customization

```python
from dash_fn_form import Field

@page.interact(
    amplitude=(0.1, 3.0, 0.1),                    # tuple → min/max/step
    label=Field(label="Title", col_span=2),        # Field → full control
)
def my_fn(amplitude: float = 1.0, label: str = "Chart"):
    ...
```

`Field` options:

| Option | Description |
|---|---|
| `label` | Display label (default: parameter name) |
| `description` | Help text below the input |
| `min` / `max` / `step` | Numeric bounds |
| `col_span` | Column span in a multi-column grid |
| `component` | Replace the auto-generated Dash component entirely |
| `hook` | `FieldHook` for runtime-populated defaults |

## Panel options

| Option | Default | Description |
|---|---|---|
| `_manual` | `False` | Show an *Apply* button; callback fires on click only |
| `_loading` | `True` | Wrap the output area in `dcc.Loading` |
| `_cache` | `False` | Cache results by field values (LRU) |
| `_cache_maxsize` | `128` | Maximum cached entries |
| `_render` | `None` | Custom renderer for the return value |
| `_id` | fn name | Component ID namespace (set when two panels share a function name) |

## Result caching

Pass `_cache=True` to skip re-calling the function when the same field values are submitted again:

```python
@interact(_cache=True)
def expensive(n: int = 100):
    import time; time.sleep(2)
    return n * n
```

Uses LRU eviction with `_cache_maxsize=128` (default). Each unique combination of field values counts as one cache entry.

## Custom renderers

Register a renderer once at startup — all `interact()` calls that return that type use it automatically:

```python
import pandas as pd
from dash import dash_table
from dash_fn_form import register_renderer

register_renderer(
    pd.DataFrame,
    lambda df: dash_table.DataTable(
        data=df.to_dict("records"),
        columns=[{"name": c, "id": c} for c in df.columns],
    ),
)
```

Built-in renderers (checked in order):

1. Explicit `_render=` on `interact()`
2. Global registry (`register_renderer`)
3. `plotly.graph_objects.Figure` → `dcc.Graph`
4. Dash component → as-is
5. `dict` → labelled card grid
6. `str` → `dcc.Markdown`
7. `int` / `float` / `bool` → `html.P`
8. `pandas.DataFrame` → `DataTable`
9. `matplotlib.figure.Figure` → base64 PNG image
10. Fallback → `html.Pre(repr(result))`

## Dict return

When a function returns a `dict`, each value is rendered as a labelled card:

```python
@interact
def stats(n: int = 100):
    import numpy as np
    data = np.random.randn(n)
    return {
        "mean": f"{data.mean():.4f}",
        "std": f"{data.std():.4f}",
        "min": f"{data.min():.4f}",
        "max": f"{data.max():.4f}",
    }
```

Each value is passed through the normal renderer pipeline — keys can map to strings, numbers, figures, DataFrames, or any registered type.

## API Reference

### interact family

::: dash_interact.interact.interact

::: dash_interact.interact.interactive

::: dash_interact.interact.interactive_output

### page

::: dash_interact.page.current

::: dash_interact.page.interact

::: dash_interact.page.add

::: dash_interact.page.run

### Page

::: dash_interact.page.Page
