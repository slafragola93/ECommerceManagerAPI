"""Unit test — BE-1 bridge price_persistence."""
import pytest
from sqlalchemy.orm import Session

from src.models.tax import Tax
from src.services.core.price_persistence import (
    calculate_price_fields_legacy,
    has_complete_price_payload,
    has_complete_price_update_payload,
    persisted_price_fields,
    resolve_price_fields,
)


@pytest.fixture
def tax22(db_session: Session) -> Tax:
    tax = Tax(name="IVA 22%", percentage=22, code="T22P", is_default=0)
    db_session.add(tax)
    db_session.commit()
    return tax


@pytest.fixture
def tax0(db_session: Session) -> Tax:
    tax = Tax(name="IVA 0%", percentage=0, code="T0P", is_default=0)
    db_session.add(tax)
    db_session.commit()
    return tax


class TestHasCompletePricePayload:
    def test_complete(self, tax22):
        data = {
            "id_tax": tax22.id_tax,
            "unit_price_net": 50.0,
            "unit_price_with_tax": 61.0,
            "total_price_net": 100.0,
            "total_price_with_tax": 122.0,
        }
        assert has_complete_price_payload(data) is True
        assert has_complete_price_update_payload(data) is True

    def test_missing_net(self, tax22):
        data = {
            "id_tax": tax22.id_tax,
            "unit_price_with_tax": 61.0,
            "total_price_net": 100.0,
            "total_price_with_tax": 122.0,
        }
        assert has_complete_price_payload(data) is False


class TestResolvePriceFields:
    def test_persist_complete_payload(self, db_session, tax22):
        data = {
            "id_tax": tax22.id_tax,
            "unit_price_net": 50.0,
            "unit_price_with_tax": 61.0,
            "total_price_net": 100.0,
            "total_price_with_tax": 122.0,
            "product_qty": 2,
        }
        result = resolve_price_fields(data, db_session)
        assert result == persisted_price_fields(data)

    def test_legacy_from_gross_only(self, db_session, tax22):
        data = {
            "id_tax": tax22.id_tax,
            "unit_price_with_tax": 122.0,
            "product_qty": 1,
        }
        result = resolve_price_fields(data, db_session)
        assert result["unit_price_net"] == pytest.approx(100.0, abs=0.01)
        assert result["total_price_with_tax"] == pytest.approx(122.0, abs=0.01)

    def test_keep_net_after_vies_with_complete_payload(self, db_session, tax22, tax0):
        """Post-VIES: net=50 lordo=50; FE manda keep_net @ 22% → net=50 lordo=61."""
        payload = {
            "id_tax": tax22.id_tax,
            "unit_price_net": 50.0,
            "unit_price_with_tax": 61.0,
            "total_price_net": 100.0,
            "total_price_with_tax": 122.0,
        }
        result = resolve_price_fields(payload, db_session, product_qty=2)
        assert result["unit_price_net"] == 50.0
        assert result["unit_price_with_tax"] == 61.0
        assert result["total_price_net"] == 100.0
        assert result["total_price_with_tax"] == 122.0

    def test_legacy_id_tax_only_recalculates_from_net(self, db_session, tax22, tax0):
        """Solo id_tax (legacy): net esistente 50, lordo VIES 50 → totali ricalcolati @ 22%."""
        result = calculate_price_fields_legacy(
            id_tax=tax22.id_tax,
            unit_price_net=50.0,
            unit_price_with_tax=50.0,
            product_qty=2,
            db=db_session,
        )
        assert result["total_price_net"] == 100.0
        assert result["total_price_with_tax"] == pytest.approx(122.0, abs=0.01)
