"""gallery-viewer demo — generic gallery with filesystem backend.

Usage:
    # First generate demo data (uses the old demo_setup):
    cd packages/corpframe-gallery && python demo_setup.py && cd ../..

    # Then run:
    uv run python examples/gallery_demo.py
"""

from pathlib import Path

from gallery_viewer import FileSystemBackend, Gallery

DEMO_DIR = Path(__file__).parent.parent / "packages" / "gallery_viewer"

gallery = Gallery(
    backend=FileSystemBackend(DEMO_DIR),
    title="Gallery Demo",
)

if __name__ == "__main__":
    print(f"Gallery base dir: {DEMO_DIR}")
    gallery.run(debug=False)
