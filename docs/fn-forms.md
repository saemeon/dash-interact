# dash-fn-form

Headless engine for `dash-interact`. Introspects a type-hinted Python callable and builds a reactive Dash form panel.

Most users should install [`dash-interact`](index.md) instead — it includes this package and adds the `page` API.

## Installation

```bash
pip install dash-fn-form
```

## Usage

```python
from dash import Dash, html
from dash_fn_form import build_fn_panel

app = Dash(__name__)

def sine_wave(amplitude: float = 1.0, frequency: float = 2.0):
    import numpy as np, plotly.graph_objects as go
    x = np.linspace(0, 6 * np.pi, 600)
    return go.Figure(go.Scatter(x=x, y=amplitude * np.sin(frequency * x)))

panel = build_fn_panel(sine_wave)

app.layout = html.Div([panel])
app.run(debug=True)
```

`build_fn_panel` returns an `html.Div` containing the form and output area — wire it into any layout.

## API

### build_fn_panel

::: dash_fn_form.fn_interact.build_fn_panel

### FnForm

::: dash_fn_form.FnForm

### Field

::: dash_fn_form.Field

### FieldHook

::: dash_fn_form.FieldHook

### FromComponent

::: dash_fn_form.FromComponent

### register_renderer

::: dash_fn_form.register_renderer

### field_id

::: dash_fn_form.field_id
