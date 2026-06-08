"""Unit test TaxRepository.find_usages (BE-ALIQ-02)."""
import pytest

from src.models.fiscal_document import FiscalDocument
from src.models.fiscal_document_detail import FiscalDocumentDetail
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.tax import Tax
from src.repository.tax_repository import TaxRepository
from src.vies.vies_app_configuration import set_reverse_charge_id_tax


@pytest.fixture
def tax_repo(db_session):
    return TaxRepository(db_session)


@pytest.fixture
def unused_tax(db_session):
    tax = Tax(name="IVA 10%", percentage=10, code="T10", is_default=0)
    db_session.add(tax)
    db_session.commit()
    db_session.refresh(tax)
    return tax


class TestTaxRepositoryFindUsages:
    def test_no_usages(self, tax_repo, unused_tax):
        usages = tax_repo.find_usages(unused_tax.id_tax)
        assert usages.order_count == 0
        assert usages.document_count == 0
        assert usages.is_reverse_charge is False
        assert usages.has_any() is False

    def test_order_detail_usage(self, tax_repo, db_session, unused_tax):
        order = Order(
            id_order_state=1,
            total_price_with_tax=10.0,
            total_price_net=8.0,
            products_total_price_with_tax=10.0,
            products_total_price_net=8.0,
        )
        db_session.add(order)
        db_session.commit()
        db_session.add(
            OrderDetail(
                id_order=order.id_order,
                id_tax=unused_tax.id_tax,
                product_name="Item",
                product_qty=1,
                unit_price_with_tax=10.0,
                unit_price_net=8.0,
                total_price_with_tax=10.0,
                total_price_net=8.0,
            )
        )
        db_session.commit()

        usages = tax_repo.find_usages(unused_tax.id_tax)
        assert usages.order_count == 1
        assert usages.has_any() is True

    def test_fiscal_document_usage(self, tax_repo, db_session, unused_tax):
        order = Order(
            id_order_state=1,
            total_price_with_tax=10.0,
            total_price_net=8.0,
            products_total_price_with_tax=10.0,
            products_total_price_net=8.0,
        )
        db_session.add(order)
        db_session.commit()
        detail = OrderDetail(
            id_order=order.id_order,
            id_tax=unused_tax.id_tax,
            product_name="Item",
            product_qty=1,
            unit_price_with_tax=10.0,
            unit_price_net=8.0,
            total_price_with_tax=10.0,
            total_price_net=8.0,
        )
        db_session.add(detail)
        db_session.commit()
        fiscal_doc = FiscalDocument(
            document_type="invoice",
            id_order=order.id_order,
            status="pending",
        )
        db_session.add(fiscal_doc)
        db_session.commit()
        db_session.add(
            FiscalDocumentDetail(
                id_fiscal_document=fiscal_doc.id_fiscal_document,
                id_order_detail=detail.id_order_detail,
                product_qty=1,
                id_tax=unused_tax.id_tax,
                unit_price_with_tax=10.0,
                total_price_with_tax=10.0,
                total_price_net=8.0,
            )
        )
        db_session.commit()

        usages = tax_repo.find_usages(unused_tax.id_tax)
        assert usages.order_count == 1
        assert usages.document_count == 1

    def test_reverse_charge_usage(self, tax_repo, db_session, unused_tax):
        set_reverse_charge_id_tax(db_session, unused_tax.id_tax)
        usages = tax_repo.find_usages(unused_tax.id_tax)
        assert usages.is_reverse_charge is True
        assert usages.has_any() is True
