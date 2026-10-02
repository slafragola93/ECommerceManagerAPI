"""Unit test — recupero immagini prodotto: path fisico vs URL e normalizzazione id_default_image."""
from pathlib import Path

import pytest
from PIL import Image
import io

from src.services.ecommerce.prestashop_service import PrestaShopService
from src.services.media.image_service import ImageService


def _jpeg_bytes(size=(40, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color=(10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()


class TestNormalizeIdDefaultImage:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            (None, 0),
            ("", 0),
            (0, 0),
            ("0", 0),
            (42, 42),
            ("99", 99),
            ({"value": "15"}, 15),
            ({"id": 7}, 7),
            ({"value": ""}, 0),
            ({"id": {"value": "3"}}, 3),
            ("not-a-number", 0),
            (False, 0),
            ([{"id": "1", "value": "12"}], 12),
            ([{"value": ""}, {"value": "8"}], 8),
        ],
    )
    def test_normalize(self, raw, expected):
        assert PrestaShopService._normalize_id_default_image(raw) == expected


class TestMediaRootAbsolute:
    def test_ensure_media_layout_creates_fallback(self, tmp_path, monkeypatch):
        from src.core import paths as paths_mod

        monkeypatch.setattr(paths_mod, "MEDIA_ROOT", tmp_path / "media")
        monkeypatch.setattr(
            paths_mod, "PRODUCT_IMAGES_ROOT", tmp_path / "media" / "product_images"
        )
        monkeypatch.setattr(
            paths_mod,
            "FALLBACK_PRODUCT_IMAGE",
            tmp_path / "media" / "product_images" / "fallback" / "product_not_found.jpg",
        )
        root = paths_mod.ensure_media_layout()
        assert root == tmp_path / "media"
        assert paths_mod.FALLBACK_PRODUCT_IMAGE.exists()
        assert paths_mod.FALLBACK_PRODUCT_IMAGE.stat().st_size > 0


class TestImageServicePaths:
    def test_physical_path_has_no_media_url_prefix(self, tmp_path: Path):
        svc = ImageService(base_path=str(tmp_path / "product_images"))
        physical = svc.get_physical_image_path(platform_id=2, product_id=100)
        public = svc.generate_local_image_path(platform_id=2, product_id=100)

        assert public == "/media/product_images/2/product_100.jpg"
        assert not str(physical).startswith("/media")
        assert physical.name == "product_100.jpg"
        assert physical.parent.name == "2"

    def test_save_image_bytes_creates_file_and_returns_public_url(self, tmp_path: Path):
        svc = ImageService(base_path=str(tmp_path / "product_images"))
        url = svc.save_image_bytes(_jpeg_bytes(), product_id=55, platform_id=1)

        assert url == "/media/product_images/1/product_55.jpg"
        assert svc.get_physical_image_path(1, 55).exists()

    def test_existing_file_is_detected_via_physical_path(self, tmp_path: Path):
        """check_image_exist deve usare il path disco, non os.path.join(cwd, '/media/...')."""
        image_svc = ImageService(base_path=str(tmp_path / "product_images"))
        image_svc.save_image_bytes(_jpeg_bytes(), product_id=77, platform_id=3)

        ps = object.__new__(PrestaShopService)
        ps.platform_id = 3
        ps.image_service = image_svc

        assert ps.check_image_exist(77) is True
        assert ps.check_image_exist(999) is False

        # L'URL pubblico non è un path filesystem valido sotto cwd
        public = image_svc.generate_local_image_path(3, 77)
        assert public.startswith("/media/")
        assert not Path(public).exists()
