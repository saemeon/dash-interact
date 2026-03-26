"""Corporate gallery demo — gallery-viewer with corpframe integration.

Usage:
    # First generate demo data:
    cd packages/corpframe-gallery && python demo_setup.py && cd ../..

    # Then run:
    uv run python examples/gallery_corporate_demo.py
"""

from pathlib import Path

from corpframe.gallery import corp_gallery

DEMO_DIR = Path(__file__).parent.parent / "packages" / "gallery_viewer"

gallery = corp_gallery(
    base_dir=DEMO_DIR,
    title="Corporate Gallery",
)

if __name__ == "__main__":
    print(f"Corporate gallery base dir: {DEMO_DIR}")
    gallery.run(debug=False)
