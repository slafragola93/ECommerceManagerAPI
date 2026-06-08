"""Sync PrestaShop non deve importare helper tax VIES (regola prodotto)."""
from pathlib import Path


def test_prestashop_service_does_not_import_vies_exemption_helpers():
    root = Path(__file__).resolve().parents[3]
    ps_file = root / "src" / "services" / "ecommerce" / "prestashop_service.py"
    source = ps_file.read_text(encoding="utf-8")
    assert "get_vies_exemption_tax_id" not in source
    assert "resolve_vies_exemption_tax_id_with_fallback" not in source
    assert "resolve_tax_id_for_delivery" not in source
