"""Unit test — calcolo esenzione VIES reale (sottrazione IVA)."""
from src.vies.exemption_calculation import (
    apply_vies_prices_to_detail_fields,
    apply_vies_prices_to_shipping_dict,
)


class TestApplyViesPricesToDetailFields:
    def test_subtracts_22_percent_from_gross(self):
        prices = apply_vies_prices_to_detail_fields(
            unit_price_with_tax=122.0,
            total_price_with_tax=122.0,
            product_qty=1,
            source_tax_percentage=22.0,
        )
        assert prices["unit_price_net"] == 100.0
        assert prices["unit_price_with_tax"] == 100.0
        assert prices["total_price_net"] == 100.0
        assert prices["total_price_with_tax"] == 100.0

    def test_zero_source_tax_leaves_amounts_unchanged(self):
        prices = apply_vies_prices_to_detail_fields(
            unit_price_with_tax=100.0,
            total_price_with_tax=100.0,
            product_qty=1,
            source_tax_percentage=0.0,
        )
        assert prices["total_price_with_tax"] == 100.0
        assert prices["total_price_net"] == 100.0


class TestApplyViesPricesToShippingDict:
    def test_subtracts_vat_from_shipping(self):
        data = {"price_tax_incl": 12.20, "price_tax_excl": 10.0, "id_tax": 5}
        apply_vies_prices_to_shipping_dict(data, 22.0, vies_tax_id=99)
        assert data["id_tax"] == 99
        assert data["price_tax_incl"] == 10.0
        assert data["price_tax_excl"] == 10.0
