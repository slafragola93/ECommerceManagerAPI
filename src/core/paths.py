"""
Percorsi assoluti del progetto (indipendenti dalla cwd di uvicorn/systemd).
"""
from pathlib import Path

# src/core/paths.py → parents[0]=core, [1]=src, [2]=project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MEDIA_ROOT = PROJECT_ROOT / "media"
PRODUCT_IMAGES_ROOT = MEDIA_ROOT / "product_images"
FALLBACK_PRODUCT_IMAGE = (
    PRODUCT_IMAGES_ROOT / "fallback" / "product_not_found.jpg"
)


def ensure_media_layout() -> Path:
    """
    Crea ``media/product_images/fallback`` e, se manca, un JPEG placeholder minimo.

    Returns:
        Path assoluto di ``MEDIA_ROOT``.
    """
    fallback_dir = FALLBACK_PRODUCT_IMAGE.parent
    fallback_dir.mkdir(parents=True, exist_ok=True)
    if not FALLBACK_PRODUCT_IMAGE.exists() or FALLBACK_PRODUCT_IMAGE.stat().st_size == 0:
        _write_minimal_jpeg(FALLBACK_PRODUCT_IMAGE)
    return MEDIA_ROOT


def _write_minimal_jpeg(path: Path) -> None:
    """Scrive un JPEG 1x1 grigio (nessuna dipendenza runtime oltre stdlib+Pillow)."""
    try:
        from PIL import Image
        import io

        buf = io.BytesIO()
        Image.new("RGB", (80, 80), color=(200, 200, 200)).save(buf, format="JPEG", quality=70)
        path.write_bytes(buf.getvalue())
    except Exception:
        # JPEG 1x1 grigio hard-coded (minimal JFIF) se Pillow non disponibile
        path.write_bytes(
            bytes.fromhex(
                "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707"
                "070909080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c"
                "1c2837292c30313434341f27393d38323c2e333432ffdb0043010909090c0b0c180d"
                "0d1832211c2132323232323232323232323232323232323232323232323232323232"
                "32323232323232323232323232323232323232323232ffc000110800010001030111"
                "00021101031101ffc40014000100000000000000000000000000000000ffc4001410"
                "01000000000000000000000000000000ffda000c03010002110311003f00bf80ffd9"
            )
        )
