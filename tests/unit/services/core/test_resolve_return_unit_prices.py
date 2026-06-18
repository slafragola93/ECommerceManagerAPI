import pytest

from src.services.core.tool import resolve_return_unit_prices


class TestResolveReturnUnitPrices:
    """Regression tests for return line price resolution (avoid double VAT)."""

    def test_legacy_unit_price_matching_gross_uses_reference_net(self):
        net, gross = resolve_return_unit_prices(
            unit_price=289.97,
            reference_unit_price_net=231.05,
            reference_unit_price_with_tax=289.97,
            tax_percentage=25.5,
        )
        assert net == pytest.approx(231.05)
        assert gross == pytest.approx(289.97)

    def test_missing_prices_falls_back_to_order_detail(self):
        net, gross = resolve_return_unit_prices(
            reference_unit_price_net=231.05,
            reference_unit_price_with_tax=289.97,
            tax_percentage=25.5,
        )
        assert net == pytest.approx(231.05)
        assert gross == pytest.approx(289.97)

    def test_explicit_net_price_is_respected(self):
        net, gross = resolve_return_unit_prices(
            unit_price_net=200.0,
            reference_unit_price_net=231.05,
            reference_unit_price_with_tax=289.97,
            tax_percentage=25.5,
        )
        assert net == pytest.approx(200.0)
        assert gross == pytest.approx(251.0)

    def test_legacy_unit_price_matching_net_is_kept(self):
        net, gross = resolve_return_unit_prices(
            unit_price=231.05,
            reference_unit_price_net=231.05,
            reference_unit_price_with_tax=289.97,
            tax_percentage=25.5,
        )
        assert net == pytest.approx(231.05)
        assert gross == pytest.approx(289.97)
