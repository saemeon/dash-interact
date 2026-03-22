# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Tests for dash_capture.strategies — JS fragment generation."""

import pytest

from dash_capture.strategies import (
    CaptureStrategy,
    _build_strip_patches,
    build_capture_js,
    canvas_strategy,
    html2canvas_strategy,
    plotly_strategy,
)


# ---------------------------------------------------------------------------
# CaptureStrategy dataclass
# ---------------------------------------------------------------------------


class TestCaptureStrategy:
    def test_defaults(self):
        s = CaptureStrategy()
        assert s.preprocess is None
        assert s.capture == ""
        assert s.format == "png"

    def test_custom_js(self):
        s = CaptureStrategy(
            preprocess="el.style.background = 'white';",
            capture="return el.toDataURL();",
        )
        assert "background" in s.preprocess
        assert "toDataURL" in s.capture

    def test_custom_format(self):
        s = CaptureStrategy(format="jpeg")
        assert s.format == "jpeg"


# ---------------------------------------------------------------------------
# Strip patches
# ---------------------------------------------------------------------------


class TestBuildStripPatches:
    def test_no_strips(self):
        assert _build_strip_patches() == []

    def test_strip_title(self):
        patches = _build_strip_patches(strip_title=True)
        assert len(patches) == 2
        assert any("title" in p for p in patches)
        assert any("margin" in p for p in patches)

    def test_strip_legend(self):
        patches = _build_strip_patches(strip_legend=True)
        assert patches == ["layout.showlegend = false;"]

    def test_strip_annotations(self):
        patches = _build_strip_patches(strip_annotations=True)
        assert patches == ["layout.annotations = [];"]

    def test_strip_axis_titles(self):
        patches = _build_strip_patches(strip_axis_titles=True)
        assert len(patches) == 1
        assert "xaxis" in patches[0] or "xy" in patches[0]

    def test_strip_colorbar(self):
        patches = _build_strip_patches(strip_colorbar=True)
        assert "showscale" in patches[0]

    def test_strip_margin(self):
        patches = _build_strip_patches(strip_margin=True)
        assert "l:0" in patches[0]

    def test_all_strips(self):
        patches = _build_strip_patches(
            strip_title=True,
            strip_legend=True,
            strip_annotations=True,
            strip_axis_titles=True,
            strip_colorbar=True,
            strip_margin=True,
        )
        combined = " ".join(patches)
        assert "title" in combined
        assert "showlegend" in combined
        assert "annotations" in combined
        assert "showscale" in combined
        assert "l:0" in combined


# ---------------------------------------------------------------------------
# Built-in strategies
# ---------------------------------------------------------------------------


class TestPlotlyStrategy:
    def test_no_strips_simple_capture(self):
        s = plotly_strategy()
        assert s.preprocess is None
        assert "Plotly.toImage" in s.capture

    def test_with_strips_has_preprocess(self):
        s = plotly_strategy(strip_title=True)
        assert s.preprocess is not None
        assert "newPlot" in s.preprocess
        assert "tmp" in s.preprocess

    def test_with_strips_capture_uses_tmp(self):
        s = plotly_strategy(strip_legend=True)
        assert "_dcap_tmp" in s.capture

    def test_capture_width_in_params(self):
        s = plotly_strategy(strip_title=True, _params={"capture_width": None})
        assert "capture_width" in s.preprocess

    def test_no_capture_width(self):
        s = plotly_strategy(strip_title=True, _params={})
        assert "capture_width" not in s.preprocess

    def test_format_default_png(self):
        s = plotly_strategy()
        assert s.format == "png"

    def test_format_jpeg(self):
        s = plotly_strategy(format="jpeg")
        assert s.format == "jpeg"

    def test_format_svg(self):
        s = plotly_strategy(format="svg")
        assert s.format == "svg"


class TestHtml2canvasStrategy:
    def test_capture_js(self):
        s = html2canvas_strategy()
        assert s.preprocess is None
        assert "html2canvas" in s.capture
        assert "toDataURL" in s.capture

    def test_error_message_for_missing_lib(self):
        s = html2canvas_strategy()
        assert "not loaded" in s.capture

    def test_format_default_png(self):
        s = html2canvas_strategy()
        assert s.format == "png"

    def test_format_jpeg(self):
        s = html2canvas_strategy(format="jpeg")
        assert s.format == "jpeg"

    def test_capture_uses_mime_from_opts(self):
        s = html2canvas_strategy()
        assert "opts.format" in s.capture


class TestCanvasStrategy:
    def test_capture_js(self):
        s = canvas_strategy()
        assert s.preprocess is None
        assert "toDataURL" in s.capture
        assert "canvas" in s.capture.lower()

    def test_format_default_png(self):
        s = canvas_strategy()
        assert s.format == "png"

    def test_format_webp(self):
        s = canvas_strategy(format="webp")
        assert s.format == "webp"


# ---------------------------------------------------------------------------
# JS assembly
# ---------------------------------------------------------------------------


class TestBuildCaptureJs:
    def test_simple_plotly(self):
        s = plotly_strategy()
        js = build_capture_js("my-graph", s, [], {})
        assert "async function" in js
        assert "my-graph" in js
        assert "no_update" in js
        assert "Plotly.toImage" in js

    def test_with_strip_patches(self):
        s = plotly_strategy(strip_title=True)
        js = build_capture_js("g", s, [], {})
        assert "newPlot" in js
        assert "title" in js

    def test_active_capture_params(self):
        s = plotly_strategy()
        js = build_capture_js("g", s, ["capture_width", "capture_height"], {})
        assert "capture_width" in js
        assert "capture_height" in js
        assert "opts.width" in js
        assert "opts.height" in js

    def test_html2canvas_strategy(self):
        s = html2canvas_strategy()
        js = build_capture_js("my-div", s, [], {})
        assert "html2canvas" in js
        assert "my-div" in js

    def test_custom_strategy(self):
        s = CaptureStrategy(
            preprocess="el.classList.add('capturing');",
            capture="return await customCapture(el);",
        )
        js = build_capture_js("el-id", s, [], {})
        assert "capturing" in js
        assert "customCapture" in js

    def test_custom_preprocess_only(self):
        s = CaptureStrategy(
            preprocess="console.log('pre');",
            capture="return 'data:image/png;base64,abc';",
        )
        js = build_capture_js("x", s, [], {})
        assert "console.log" in js
        assert "base64,abc" in js

    def test_format_in_opts(self):
        s = plotly_strategy(format="svg")
        js = build_capture_js("g", s, [], {})
        assert "format: 'svg'" in js

    def test_format_jpeg_in_opts(self):
        s = html2canvas_strategy(format="jpeg")
        js = build_capture_js("g", s, [], {})
        assert "format: 'jpeg'" in js

    def test_element_id_escaping(self):
        s = plotly_strategy()
        js = build_capture_js("test'; alert('xss');//", s, [], {})
        assert "alert" in js  # string is present but escaped
        assert "\\'" in js  # single quote is escaped


# ---------------------------------------------------------------------------
# Batch capture
# ---------------------------------------------------------------------------


class TestBatchCapture:
    def test_batch_creates_bindings(self):
        from dash_capture import BatchBinding, capture_batch

        batch = capture_batch(["g1", "g2", "g3"])
        assert isinstance(batch, BatchBinding)
        assert len(batch.stores) == 3
        assert len(batch.bindings) == 3
        assert "g1" in batch.bindings
        assert "g2" in batch.bindings
        assert "g3" in batch.bindings

    def test_batch_store_ids_unique(self):
        from dash_capture import capture_batch

        batch = capture_batch(["a", "b"])
        ids = [b.store_id for b in batch.bindings.values()]
        assert len(set(ids)) == 2  # all unique

    def test_batch_with_strategy(self):
        from dash_capture import capture_batch

        batch = capture_batch(
            ["x", "y"],
            strategy=plotly_strategy(strip_title=True),
        )
        assert len(batch.bindings) == 2

    def test_batch_empty_list(self):
        from dash_capture import capture_batch

        batch = capture_batch([])
        assert len(batch.stores) == 0
        assert len(batch.bindings) == 0


# ---------------------------------------------------------------------------
# Import smoke test
# ---------------------------------------------------------------------------


def test_import():
    import dash_capture

    assert hasattr(dash_capture, "CaptureStrategy")
    assert hasattr(dash_capture, "plotly_strategy")
    assert hasattr(dash_capture, "html2canvas_strategy")
    assert hasattr(dash_capture, "canvas_strategy")
    assert hasattr(dash_capture, "capture_element")
    assert hasattr(dash_capture, "capture_graph")
    assert hasattr(dash_capture, "capture_binding")
    assert hasattr(dash_capture, "capture_batch")
    assert hasattr(dash_capture, "CaptureBinding")
    assert hasattr(dash_capture, "BatchBinding")
    # backwards compat
    assert hasattr(dash_capture, "graph_exporter")
    assert hasattr(dash_capture, "component_exporter")
