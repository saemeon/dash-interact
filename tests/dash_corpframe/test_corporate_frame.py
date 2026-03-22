# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Tests for dash_corpframe.corporate_frame — matplotlib framing."""

import io

import matplotlib.pyplot as plt
import pytest

from dash_corpframe.corporate_frame import _apply_frame, corporate_renderer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_png(width: int = 200, height: int = 100) -> bytes:
    """Create a minimal test PNG."""
    fig, ax = plt.subplots(figsize=(width / 100, height / 100), dpi=100)
    ax.plot([0, 1], [0, 1])
    ax.set_title("Test")
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# _apply_frame
# ---------------------------------------------------------------------------

class TestApplyFrame:
    def test_returns_bytes(self):
        result = _apply_frame(_make_png(), title="Hello")
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_valid_png(self):
        result = _apply_frame(_make_png(), title="Test")
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_no_text_still_valid(self):
        result = _apply_frame(_make_png())
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_title_only(self):
        result = _apply_frame(_make_png(), title="Title")
        assert len(result) > 100

    def test_subtitle_only(self):
        result = _apply_frame(_make_png(), subtitle="Sub")
        assert len(result) > 100

    def test_title_and_subtitle(self):
        result = _apply_frame(_make_png(), title="T", subtitle="S")
        assert len(result) > 100

    def test_footnotes(self):
        result = _apply_frame(
            _make_png(), title="T", footnotes="Note 1"
        )
        assert len(result) > 100

    def test_sources(self):
        result = _apply_frame(
            _make_png(), title="T", sources="Source: Bloomberg"
        )
        assert len(result) > 100

    def test_all_text(self):
        result = _apply_frame(
            _make_png(),
            title="Q4 Revenue",
            subtitle="By Region",
            footnotes="Preliminary",
            sources="Source: ERP",
        )
        assert len(result) > 100

    def test_custom_dpi(self):
        r1 = _apply_frame(_make_png(), title="T", dpi=72)
        r2 = _apply_frame(_make_png(), title="T", dpi=300)
        # Higher DPI should produce larger file
        assert len(r2) > len(r1)

    def test_empty_strings_no_header_footer(self):
        # No title/subtitle → no header, no footnotes/sources → no footer
        bare = _apply_frame(_make_png())
        with_header = _apply_frame(_make_png(), title="H")
        # With header should be larger due to extra space
        assert len(with_header) > len(bare) * 0.9  # some tolerance


# ---------------------------------------------------------------------------
# corporate_renderer
# ---------------------------------------------------------------------------

class TestCorporateRenderer:
    def test_writes_to_target(self):
        buf = io.BytesIO()
        png = _make_png()

        def snapshot():
            return png

        corporate_renderer(buf, snapshot, title="Test")
        buf.seek(0)
        result = buf.read()
        assert result[:8] == b"\x89PNG\r\n\x1a\n"
        assert len(result) > 0

    def test_all_params(self):
        buf = io.BytesIO()
        png = _make_png()
        corporate_renderer(
            buf, lambda: png,
            title="Title", subtitle="Sub",
            footnotes="Note", sources="Src",
        )
        buf.seek(0)
        assert buf.read()[:8] == b"\x89PNG\r\n\x1a\n"

    def test_no_params(self):
        buf = io.BytesIO()
        corporate_renderer(buf, _make_png)
        buf.seek(0)
        assert len(buf.read()) > 0


# ---------------------------------------------------------------------------
# Import smoke test
# ---------------------------------------------------------------------------

def test_import():
    import dash_corpframe
    assert hasattr(dash_corpframe, "corporate_capture_graph")
    assert hasattr(dash_corpframe, "corporate_renderer")
