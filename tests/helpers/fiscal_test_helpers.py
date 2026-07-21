"""Helper condivisi per test corrispettivi, ricevute e resi."""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from src.models.address import Address
from src.models.app_configuration import AppConfiguration
from src.models.country import Country
from src.models.customer import Customer
from src.models.fiscal_document import FiscalDocument
from src.models.fiscal_document_detail import FiscalDocumentDetail
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.ricevuta import Ricevuta, RicevutaStato
from src.models.shipping import Shipping
from src.models.tax import Tax
from src.services.routers.auth_service import get_current_user


def admin_full_crud_user() -> dict:
    """Bypass permessi granulari in SQLite in-memory (AppModule vuota)."""
    return {
        "id": 1,
        "username": "admin",
        "role_type": "full_crud",
        "roles": [{"name": "ADMIN", "permissions": ["C", "R", "U", "D"]}],
    }


def override_admin_client(test_app):
    test_app.dependency_overrides[get_current_user] = admin_full_crud_user


def seed_tax(db_session, *, name="IVA 22%", percentage=22, code="22") -> Tax:
    row = Tax(name=name, percentage=percentage, code=code, is_default=0)
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def seed_company_info(db_session) -> None:
    rows = [
        AppConfiguration(category="company_info", name="company_name", value="Test Srl"),
        AppConfiguration(category="company_info", name="address", value="Via Roma 1"),
        AppConfiguration(category="company_info", name="city", value="Milano"),
    ]
    db_session.add_all(rows)
    db_session.commit()


def seed_country(db_session, *, iso_code: str, name: str) -> Country:
    country = Country(iso_code=iso_code, name=name)
    db_session.add(country)
    db_session.commit()
    db_session.refresh(country)
    return country


def seed_paid_order(
    db_session,
    tax: Tax,
    *,
    reference: str,
    order_date: datetime,
    payment_date: Optional[date] = None,
    is_payed: bool = True,
    id_platform: Optional[int] = None,
    id_store: Optional[int] = None,
    country_iso: Optional[str] = None,
    product_qty: int = 1,
    unit_gross: Decimal = Decimal("122.00"),
    unit_net: Decimal = Decimal("100.00"),
    with_shipping: bool = False,
    shipping_gross: Decimal = Decimal("12.20"),
    shipping_net: Decimal = Decimal("10.00"),
) -> tuple[Order, OrderDetail]:
    customer = Customer(
        id_lang=1,
        firstname="Mario",
        lastname="Rossi",
        email=f"{reference}@example.com",
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    id_address_delivery = None
    if country_iso:
        country = seed_country(db_session, iso_code=country_iso, name=country_iso)
        address = Address(
            id_customer=customer.id_customer,
            id_country=country.id_country,
            address1="Via Test 1",
            city="Test City",
            postcode="00100",
            date_add=order_date.date(),
        )
        db_session.add(address)
        db_session.commit()
        db_session.refresh(address)
        id_address_delivery = address.id_address

    id_shipping = None
    if with_shipping:
        shipping = Shipping(
            price_tax_incl=shipping_gross,
            price_tax_excl=shipping_net,
            id_tax=tax.id_tax,
        )
        db_session.add(shipping)
        db_session.commit()
        db_session.refresh(shipping)
        id_shipping = shipping.id_shipping

    total_gross = unit_gross * product_qty + (shipping_gross if with_shipping else Decimal("0"))
    total_net = unit_net * product_qty + (shipping_net if with_shipping else Decimal("0"))

    order = Order(
        id_customer=customer.id_customer,
        id_order_state=1,
        reference=reference,
        date_add=order_date,
        payment_date=payment_date or order_date.date(),
        is_payed=is_payed,
        id_platform=id_platform,
        id_store=id_store,
        id_address_delivery=id_address_delivery,
        id_shipping=id_shipping,
        total_price_with_tax=total_gross,
        total_price_net=total_net,
        products_total_price_with_tax=unit_gross * product_qty,
        products_total_price_net=unit_net * product_qty,
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    detail = OrderDetail(
        id_order=order.id_order,
        id_tax=tax.id_tax,
        product_name=f"Prodotto {reference}",
        product_qty=product_qty,
        unit_price_with_tax=unit_gross,
        unit_price_net=unit_net,
        total_price_with_tax=unit_gross * product_qty,
        total_price_net=unit_net * product_qty,
    )
    db_session.add(detail)
    db_session.commit()
    db_session.refresh(detail)
    return order, detail


def seed_ricevuta(
    db_session,
    order: Order,
    customer: Customer,
    *,
    emission_date: date,
    incasso_date: Optional[date] = None,
    numero: int = 1,
    anno: Optional[int] = None,
) -> Ricevuta:
    ricevuta = Ricevuta(
        numero=numero,
        anno=anno or emission_date.year,
        id_order=order.id_order,
        id_customer=customer.id_customer,
        data_incasso=incasso_date or emission_date,
        data_emissione=emission_date,
        stato=RicevutaStato.EMESSA,
    )
    db_session.add(ricevuta)
    db_session.commit()
    db_session.refresh(ricevuta)
    return ricevuta


def seed_return(
    db_session,
    tax: Tax,
    order: Order,
    detail: OrderDetail,
    *,
    return_date: datetime,
    qty: int = 1,
    return_net: Decimal = Decimal("30.00"),
    return_gross: Decimal = Decimal("36.60"),
    includes_shipping: bool = False,
) -> FiscalDocument:
    return_doc = FiscalDocument(
        document_type="return",
        id_order=order.id_order,
        status="issued",
        date_add=return_date,
        includes_shipping=includes_shipping,
        total_price_net=return_net,
        total_price_with_tax=return_gross,
        products_total_price_net=return_net,
        products_total_price_with_tax=return_gross,
    )
    db_session.add(return_doc)
    db_session.commit()
    db_session.refresh(return_doc)
    db_session.add(
        FiscalDocumentDetail(
            id_fiscal_document=return_doc.id_fiscal_document,
            id_order_detail=detail.id_order_detail,
            product_qty=qty,
            id_tax=tax.id_tax,
            unit_price_with_tax=return_gross / qty,
            total_price_with_tax=return_gross,
            total_price_net=return_net,
        )
    )
    db_session.commit()
    return return_doc


def seed_invoice(db_session, order: Order) -> FiscalDocument:
    invoice = FiscalDocument(
        document_type="invoice",
        id_order=order.id_order,
        status="issued",
        total_price_net=order.total_price_net,
        total_price_with_tax=order.total_price_with_tax,
    )
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(invoice)
    return invoice


def seed_credit_note(db_session, order: Order) -> FiscalDocument:
    credit_note = FiscalDocument(
        document_type="credit_note",
        id_order=order.id_order,
        status="pending",
        is_electronic=True,
        total_price_net=Decimal("50.00"),
        total_price_with_tax=Decimal("61.00"),
    )
    db_session.add(credit_note)
    db_session.commit()
    db_session.refresh(credit_note)
    return credit_note
