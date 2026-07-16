"""Test export CSV/Excel ricevute (BE-2.5)."""
from datetime import date, datetime
from decimal import Decimal

import pytest

from src.models.customer import Customer
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.ricevuta import Ricevuta, RicevutaStato
from src.models.tax import Tax
from src.schemas.ricevuta_schema import (
    RicevutaCustomerEmbedSchema,
    RicevutaExportFormatSchema,
    RicevutaFiltersSchema,
    RicevutaListItemSchema,
    RicevutaOrderDetailEmbedSchema,
    RicevutaResponseSchema,
    RicevutaStatoSchema,
)
from src.services.export.ricevuta_export_service import RicevutaExportService
from src.services.routers.ricevuta_service import RicevutaService


@pytest.fixture
def export_service():
    return RicevutaExportService()


@pytest.fixture
def sample_detail():
    return RicevutaResponseSchema(
        id_ricevuta=12,
        numero=7,
        anno=2026,
        data_incasso=date(2026, 6, 1),
        data_emissione=datetime(2026, 6, 5, 10, 30),
        stato=RicevutaStatoSchema.EMESSA,
        created_at=datetime(2026, 6, 5, 10, 0, 0),
        updated_at=datetime(2026, 6, 5, 10, 0, 0),
        is_modifiable=True,
        id_order=45001,
        order_reference="ORD-1",
        id_order_state=1,
        is_payed=True,
        total_price_with_tax=244.0,
        total_price_net=200.0,
        customer=RicevutaCustomerEmbedSchema(
            id_customer=1,
            firstname="Luigi",
            lastname="Verdi",
            email="luigi@example.com",
        ),
        order_details=[
            RicevutaOrderDetailEmbedSchema(
                id_order_detail=901,
                product_reference="REF-1",
                product_name="Articolo test",
                product_qty=2,
                unit_price_net=100.0,
                unit_price_with_tax=122.0,
                total_price_net=200.0,
                total_price_with_tax=244.0,
            )
        ],
    )


class TestRicevutaExportService:
    def test_detail_csv_contains_header_and_line(self, export_service, sample_detail):
        content = export_service.build_detail_csv(sample_detail)
        text = content.decode("utf-8-sig")

        assert "product_name" in text
        assert "Articolo test" in text
        assert "7;2026" in text or "7;2026;" in text

    def test_detail_xlsx_not_empty(self, export_service, sample_detail):
        content = export_service.build_detail_xlsx(sample_detail)
        assert content[:2] == b"PK"

    def test_list_csv_from_list_items(self, export_service):
        item = RicevutaListItemSchema(
            id_ricevuta=1,
            numero=3,
            anno=2026,
            data_incasso=date(2026, 7, 1),
            data_emissione=datetime(2026, 7, 2, 9, 15),
            stato=RicevutaStatoSchema.EMESSA,
            id_order=100,
            order_reference="ORD-100",
            order_total_with_tax=150.0,
            customer=RicevutaCustomerEmbedSchema(
                id_customer=9,
                firstname="Anna",
                lastname="Bianchi",
                email="anna@example.com",
            ),
        )
        text = export_service.build_list_csv([item]).decode("utf-8-sig")
        assert "Anna Bianchi" in text
        assert "ORD-100" in text


class TestRicevutaServiceExport:
    @pytest.fixture
    def service(self, db_session):
        from src.repository.address_repository import AddressRepository
        from src.repository.customer_repository import CustomerRepository
        from src.repository.order_detail_repository import OrderDetailRepository
        from src.repository.order_repository import OrderRepository
        from src.repository.ricevuta_repository import RicevutaRepository

        return RicevutaService(
            RicevutaRepository(db_session),
            OrderRepository(db_session),
            OrderDetailRepository(db_session),
            CustomerRepository(db_session),
            AddressRepository(db_session),
        )

    def test_export_single_ricevuta_csv(self, db_session, service):
        tax = Tax(name="IVA 22%", percentage=22, code="22", is_default=0)
        db_session.add(tax)
        customer = Customer(
            id_lang=1,
            firstname="Mario",
            lastname="Rossi",
            email="mario@example.com",
        )
        db_session.add(customer)
        db_session.commit()

        order = Order(
            id_customer=customer.id_customer,
            id_order_state=1,
            reference="EXP-1",
            date_add=datetime(2026, 7, 1, 10, 0, 0),
            is_payed=True,
            total_price_with_tax=Decimal("122.00"),
            total_price_net=Decimal("100.00"),
            products_total_price_with_tax=Decimal("122.00"),
            products_total_price_net=Decimal("100.00"),
        )
        db_session.add(order)
        db_session.commit()
        db_session.add(
            OrderDetail(
                id_order=order.id_order,
                id_tax=tax.id_tax,
                product_name="Prodotto export",
                product_qty=1,
                unit_price_with_tax=Decimal("122.00"),
                unit_price_net=Decimal("100.00"),
                total_price_with_tax=Decimal("122.00"),
                total_price_net=Decimal("100.00"),
            )
        )
        db_session.add(
            Ricevuta(
                numero=5,
                anno=2026,
                id_order=order.id_order,
                id_customer=customer.id_customer,
                data_incasso=date(2026, 7, 1),
                data_emissione=datetime(2026, 7, 2, 9, 15),
                stato=RicevutaStato.EMESSA,
            )
        )
        db_session.commit()
        ricevuta = db_session.query(Ricevuta).one()

        content, media_type, filename = service.export_ricevuta(
            ricevuta.id_ricevuta, RicevutaExportFormatSchema.CSV.value
        )

        assert media_type.startswith("text/csv")
        assert filename == "Ricevuta-5-2026.csv"
        assert b"Prodotto export" in content

    def test_export_list_rejects_invalid_format(self, service):
        with pytest.raises(Exception) as exc_info:
            service.export_ricevute(
                RicevutaFiltersSchema(),
                "pdf",
            )
        assert "Formato export" in str(exc_info.value)
