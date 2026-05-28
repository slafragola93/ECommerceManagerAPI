"""Unit test — cleanup seed BE-VIES-1 su taxes."""
import pytest

from src.models.country import Country
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.tax import Tax
from src.vies.eu_vat_seed import (
    SEED_NOTE_MARKER,
    delete_be_vies_1_seed_taxes,
    is_be_vies_1_seed_note,
    seed_note_for_country,
    setup_eu_country_taxes,
)


@pytest.fixture
def eu_countries_sample(db_session):
    codes = [("IT", "Italy"), ("DE", "Germany")]
    created = []
    for i, (iso, name) in enumerate(codes):
        c = Country(id_origin=i + 1, name=name, iso_code=iso)
        db_session.add(c)
        created.append(c)
    db_session.commit()
    return created


class TestBeVies1SeedMarkers:
    def test_is_be_vies_1_seed_note(self):
        assert is_be_vies_1_seed_note(seed_note_for_country("IT"))
        assert not is_be_vies_1_seed_note("Aliquota custom")
        assert SEED_NOTE_MARKER in seed_note_for_country("DE")


class TestBeVies1SeedCleanup:
    def test_delete_removes_only_seed_rows(self, db_session):
        country = Country(id_origin=1, name="Italy", iso_code="IT")
        db_session.add(country)
        db_session.commit()
        seed = Tax(
            id_country=country.id_country,
            is_default=1,
            name="IVA IT 22%",
            note=seed_note_for_country("IT"),
            code="VATIT",
            percentage=22,
        )
        user_tax = Tax(
            id_country=country.id_country,
            is_default=0,
            name="Aliquota custom",
            note="Creata dall'utente",
            code="CUS",
            percentage=10,
        )
        db_session.add_all([seed, user_tax])
        db_session.commit()

        deleted = delete_be_vies_1_seed_taxes(db_session.connection())
        db_session.commit()

        assert deleted == 1
        remaining = db_session.query(Tax).all()
        assert len(remaining) == 1
        assert remaining[0].code == "CUS"

    def test_delete_skips_referenced_seed_tax(self, db_session):
        country = Country(id_origin=1, name="Italy", iso_code="IT")
        db_session.add(country)
        db_session.commit()
        seed = Tax(
            id_country=country.id_country,
            is_default=1,
            name="IVA IT 22%",
            note=seed_note_for_country("IT"),
            code="VATIT",
            percentage=22,
        )
        db_session.add(seed)
        db_session.commit()
        order = Order(id_order_state=1)
        db_session.add(order)
        db_session.commit()
        db_session.add(
            OrderDetail(
                id_order=order.id_order,
                id_tax=seed.id_tax,
                product_name="x",
                product_qty=1,
                unit_price_with_tax=10.0,
                unit_price_net=8.0,
                total_price_with_tax=10.0,
                total_price_net=8.0,
            )
        )
        db_session.commit()

        deleted = delete_be_vies_1_seed_taxes(db_session.connection())
        assert deleted == 0
        assert db_session.query(Tax).filter(Tax.id_tax == seed.id_tax).count() == 1

    def test_cleanup_idempotent(self, db_session):
        country = Country(id_origin=1, name="Italy", iso_code="IT")
        db_session.add(country)
        db_session.commit()
        db_session.add(
            Tax(
                id_country=country.id_country,
                is_default=1,
                name="IVA IT 22%",
                note=seed_note_for_country("IT"),
                code="VATIT",
                percentage=22,
            )
        )
        db_session.commit()

        conn = db_session.connection()
        assert delete_be_vies_1_seed_taxes(conn) == 1
        assert delete_be_vies_1_seed_taxes(conn) == 0

    def test_setup_then_cleanup_via_marker(self, db_session, eu_countries_sample):
        setup_eu_country_taxes(db_session)
        assert (
            db_session.query(Tax)
            .filter(Tax.note.like(f"%{SEED_NOTE_MARKER}%"))
            .count()
            >= 1
        )

        deleted = delete_be_vies_1_seed_taxes(db_session.connection())
        assert deleted >= len(eu_countries_sample)
        assert (
            db_session.query(Tax).filter(Tax.note.like(f"%{SEED_NOTE_MARKER}%")).count()
            == 0
        )
