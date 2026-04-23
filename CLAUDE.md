# dash-interact

Pyplot-style convenience layer over `dash-fn-form`. Aims to be the **Dash equivalent of ipywidgets `interact`** — same three-level API (`interact`, `interactive`, `interactive_output`), auto-widget-from-type-hints, low-barrier entry.

> Context snapshot (knowledge as of ~2026-03-26). Verify against current code before acting on claims about specific files/APIs.

## Inspirations

Reference implementations are vendored under this directory for comparison:
- `ipywidgets/` — primary model (auto-slider, tuple shorthand, `fixed()`, `interact.options()`, three-level API)
- `py-shiny/` — reactive patterns, `@reactive.event`-style selective triggering (maps to proposed `_trigger` param)
- `../dash-fn-form/dash-pydantic-form/` — form sections, accordion/tabs, read-only mode, extended visibility operators

Streamlit also inspires the page-level layout primitives (`page.columns()`, `page.sidebar()`, `page.tabs()`) and the result-caching pattern.

## Status

### Done
- Auto-slider from numeric defaults (`_auto_slider=True`) with tuple shorthand `(min, max, step)`
- `Literal[...]` / list default → Dropdown
- `fixed()` sentinel
- `interact.options()` factory (`_InteractOptions`)
- Three-level API: `interact`, `interactive`, `interactive_output`
- Result caching (`_cache=True`, `_cache_maxsize`)
- Multi-output from dict return (labelled cards)
- Cross-field validator (`FnForm(_validator=...)`)
- Form-level layout (sections / accordion / tabs — via `dash-fn-form`)
- Page-level layout (columns / sidebar / tabs — context-manager style)

### Open backlog
Full design in `_notes.md`.

- **DataPort — panel-to-panel data coupling** *(designed, not implemented)*. `DataPort("name")` backed by `dcc.Store` lets one panel's output feed another's inputs. Producer writes via extra `Output`; consumer reads via extra `Input`. Open questions: initial value, error propagation, multiple producers (disallow?), layout injection.
- `interact_manual` pre-configured shortcut (trivial: `interact.options(_manual=True)`)
- Enter-to-submit in manual mode (ipywidgets wires `continuous_update=False` + Enter on Text widgets)
- Type-hint-only params without defaults (ipywidgets: `x: int` → `IntText()`; we currently require a default)

### Out of scope / deferred
- **File upload** — caller uses `dcc.Upload` directly
- **Notebook state snapshot** — deferred
- **Auto-display in notebooks** — fundamentally different (Dash server vs Jupyter kernel)
- **Steps layout** — decided against

## Auto-slider range heuristic (differs from ipywidgets)

Our heuristic keeps `min >= 0` for positive defaults (cleaner UX). ipywidgets uses a symmetric range around zero.

| Default | ipywidgets | dash-interact |
|---|---|---|
| `int = 0` | `(0, 1, 1)` | `(-10, 10, 1)` |
| `int = 5` | `(-5, 15, 1)` | `(0, 15, 1)` |
| `float = 0.0` | `(0.0, 1.0)` | `(-1.0, 1.0, 0.1)` |
| `float = 2.5` | `(-2.5, 7.5)` | `(0.0, 7.5, 0.25)` |

## Advantages vs. ipywidgets

- 13+ type hints vs 5 (date, datetime, Path, `list[Literal]`, tuple, dict, Enum, Optional, …)
- `Field()` with validation, description, label, col_span, visible, persist
- Form sections, accordion, tabs
- Page-level layout (columns, sidebar, tabs)
- Result caching
- Multiple component libraries (dcc / dbc / dmc)
- Cross-field validation, read-only mode

## Page-level layout — implementation mechanism

`Page._add_target` redirection: context managers swap where `page.add()` appends children. On `__exit__`, the Dash container component is built and added to the page. Mirrors Shiny Express's `RecallContextManager` pattern, but without AST transformation (Dash has no import-time hook).

```python
with page.columns(2) as cols:
    with cols[0]:
        @page.interact
        def controls(...): ...
    with cols[1]:
        page.add(chart)

with page.sidebar(width=300) as (side, main):
    with side: page.add(form)
    with main: page.add(output)

with page.tabs() as t:
    with t.tab("Analysis"):
        @page.interact
        def analysis(...): ...
```

## Patterns borrowed from Shiny Express

- **Context-manager layouts** — `with ui.card():` captures children; our `_add_target` redirection is the equivalent.
- **Auto-output-ui** — renderers auto-create their output container. Our `interact()` does this via `FnPanel` (form + output).
- **Reactive Calc** — Shiny's `@reactive.calc` caches computed values. Our `_cache=True` is a simpler LRU-by-inputs variant.
- **`@reactive.event` → `_trigger="field_name"`** — more flexible than all-or-nothing `_manual`.

**Not transferable:** AST transformation at import, dynamic dependency tracking, push-pull invalidation. Dash requires explicit `Input`/`Output`/`State` declarations and executes callbacks eagerly.

## Key source locations (vendored)

- `ipywidgets/python/ipywidgets/ipywidgets/widgets/interaction.py` — ipywidgets `interact` impl
- `py-shiny/shiny/express/_run.py` — AST transformation
- `py-shiny/shiny/reactive/_core.py` — reactive Context, Dependents
- `py-shiny/shiny/reactive/_reactives.py` — `Calc_`, `Effect_`
- `py-shiny/shiny/express/_recall_context.py` — `RecallContextManager`
- `py-shiny/shiny/ui/_sidebar.py`, `_card.py`, `_accordion.py` — layout primitives
- `../dash-fn-form/dash-pydantic-form/` — dash-pydantic-form source
