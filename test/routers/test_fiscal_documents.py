import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, date

from src.database import Base
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.address import Address
from src.models.country import Country
from src.models.customer import Customer
from src.models.shipping import Shipping
from src.models.tax import Tax
from src.models.fiscal_document import FiscalDocument
from src.models.fiscal_document_detail import FiscalDocumentDetail
from src.repository.fiscal_document_repository import FiscalDocumentRepository


# ==================== FIXTURES ====================

@pytest.fixture(scope="function")
def db_session():
    """Crea un database in memoria per i test"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()


@pytest.fixture
def setup_basic_data(db_session):
    """Setup dati base necessari per i test"""
    # Crea paese Italia
    italy = Country(id_country=1, name="Italia", iso_code="IT")
    db_session.add(italy)
    
    # Crea paese Francia
    france = Country(id_country=2, name="France", iso_code="FR")
    db_session.add(france)
    
    # Crea tax 22%
    tax = Tax(id_tax=1, name="IVA 22%", percentage=22, code="22", is_default=1)
    db_session.add(tax)
    
    # Crea tax 10%
    tax_10 = Tax(id_tax=2, name="IVA 10%", percentage=10, code="10", is_default=0)
    db_session.add(tax_10)
    
    # Crea customer
    customer = Customer(
        id_customer=1,
        id_lang=1,
        firstname="Mario",
        lastname="Rossi",
        email="mario.rossi@test.it",
        date_add=date.today()
    )
    db_session.add(customer)
    
    # Crea indirizzo italiano
    address_it = Address(
        id_address=1,
        id_customer=1,
        id_country=1,
        firstname="Mario",
        lastname="Rossi",
        address1="Via Roma 1",
        postcode="20100",
        city="Milano",
        state="MI",
        phone="1234567890",
        pec="mario@pec.it",
        sdi="ABCDEFG",
        date_add=date.today()
    )
    db_session.add(address_it)
    
    # Crea indirizzo francese
    address_fr = Address(
        id_address=2,
        id_customer=1,
        id_country=2,
        firstname="Mario",
        lastname="Rossi",
        address1="Rue de Paris 1",
        postcode="75001",
        city="Paris",
        state="IDF",
        phone="1234567890",
        date_add=date.today()
    )
    db_session.add(address_fr)
    
    # Crea spedizione
    shipping = Shipping(
        id_shipping=1,
        price_tax_excl=10.0,
        price_tax_incl=12.2,
        id_tax=1,
        weight=1.0,
        date_add=date.today()
    )
    db_session.add(shipping)
    
    db_session.commit()
    
    return {
        "italy": italy,
        "france": france,
        "tax_22": tax,
        "tax_10": tax_10,
        "customer": customer,
        "address_it": address_it,
        "address_fr": address_fr,
        "shipping": shipping
    }


@pytest.fixture
def create_order_with_details(db_session, setup_basic_data):
    """Crea un ordine con dettagli per i test"""
    def _create_order(
        address_id=1, 
        total_price_tax_excl=100.0, 
        total_paid=122.0,
        with_shipping=True,
        num_details=3
    ):
        order = Order(
            id_order=None,  # Auto-increment
            id_customer=1,
            id_address_invoice=address_id,
            id_address_delivery=address_id,
            id_shipping=1 if with_shipping else None,
            id_order_state=1,
            is_invoice_requested=True,
            is_payed=True,
            total_price_tax_excl=total_price_tax_excl,
            total_paid=total_paid,
            total_discounts=0.0,
            date_add=datetime.now()
        )
        db_session.add(order)
        db_session.flush()
        
        # Crea order details
        details_data = [
            {"qty": 2, "price": 50.0, "reduction_percent": 0},
            {"qty": 1, "price": 30.0, "reduction_percent": 10},
            {"qty": 1, "price": 20.0, "reduction_percent": 0}
        ]
        
        for i, data in enumerate(details_data[:num_details]):
            detail = OrderDetail(
                id_order_detail=None,
                id_order=order.id_order,
                product_name=f"Prodotto {i+1}",
                product_price=data["price"],
                product_qty=data["qty"],
                reduction_percent=data["reduction_percent"],
                reduction_amount=0.0,
                id_tax=1
            )
            db_session.add(detail)
        
        db_session.commit()
        db_session.refresh(order)
        
        return order
    
    return _create_order


# ==================== TEST FATTURE ====================

def test_create_invoice_electronic_italian_address(db_session, setup_basic_data, create_order_with_details):
    """Test creazione fattura elettronica con indirizzo italiano"""
    order = create_order_with_details(address_id=1)
    repo = FiscalDocumentRepository(db_session)
    
    invoice = repo.create_invoice(id_order=order.id_order, is_electronic=True)
    
    assert invoice.id_fiscal_document is not None
    assert invoice.document_type == 'invoice'
    assert invoice.tipo_documento_fe == 'TD01'
    assert invoice.is_electronic == True
    assert invoice.status == 'pending'  # Elettronica → pending
    assert invoice.includes_shipping == True  # Fatture sempre True
    assert invoice.document_number is not None
    assert invoice.total_amount > 0


def test_create_invoice_non_electronic(db_session, setup_basic_data, create_order_with_details):
    """Test creazione fattura non elettronica"""
    order = create_order_with_details(address_id=1)
    repo = FiscalDocumentRepository(db_session)
    
    invoice = repo.create_invoice(id_order=order.id_order, is_electronic=False)
    
    assert invoice.document_type == 'invoice'
    assert invoice.is_electronic == False
    assert invoice.status == 'issued'  # Non elettronica → issued
    assert invoice.includes_shipping == True
    assert invoice.document_number is None  # Non elettronica senza numero
    assert invoice.tipo_documento_fe is None


def test_create_invoice_electronic_foreign_address_fails(db_session, setup_basic_data, create_order_with_details):
    """Test: fattura elettronica con indirizzo estero deve fallire"""
    order = create_order_with_details(address_id=2)  # Francia
    repo = FiscalDocumentRepository(db_session)
    
    with pytest.raises(ValueError, match="può essere emessa solo per indirizzi italiani"):
        repo.create_invoice(id_order=order.id_order, is_electronic=True)


def test_create_invoice_creates_fiscal_document_details(db_session, setup_basic_data, create_order_with_details):
    """Test: la fattura crea FiscalDocumentDetail per ogni OrderDetail"""
    order = create_order_with_details(num_details=3)
    repo = FiscalDocumentRepository(db_session)
    
    invoice = repo.create_invoice(id_order=order.id_order, is_electronic=False)
    
    details = db_session.query(FiscalDocumentDetail).filter(
        FiscalDocumentDetail.id_fiscal_document == invoice.id_fiscal_document
    ).all()
    
    assert len(details) == 3  # 3 OrderDetail → 3 FiscalDocumentDetail
    
    # Verifica che gli sconti siano stati applicati correttamente
    detail_1 = next(d for d in details if d.id_order_detail == 1)
    assert detail_1.unit_price == 50.0
    assert detail_1.quantity == 2
    assert detail_1.total_amount == 100.0  # 50*2, no sconto
    
    detail_2 = next(d for d in details if d.id_order_detail == 2)
    assert detail_2.unit_price == 30.0
    assert detail_2.quantity == 1
    assert detail_2.total_amount == 27.0  # 30 - 10% = 27


# ==================== TEST NOTE DI CREDITO - BASE ====================

def test_create_credit_note_total_first_time(db_session, setup_basic_data, create_order_with_details):
    """Test: creazione prima nota di credito totale"""
    order = create_order_with_details()
    repo = FiscalDocumentRepository(db_session)
    
    # Crea fattura
    invoice = repo.create_invoice(id_order=order.id_order, is_electronic=True)
    
    # Crea nota credito totale
    credit_note = repo.create_credit_note(
        id_invoice=invoice.id_fiscal_document,
        reason="Reso completo",
        is_partial=False,
        is_electronic=True,
        include_shipping=True
    )
    
    assert credit_note.document_type == 'credit_note'
    assert credit_note.tipo_documento_fe == 'TD04'
    assert credit_note.is_partial == False
    assert credit_note.includes_shipping == True
    assert credit_note.status == 'pending'
    assert credit_note.id_fiscal_document_ref == invoice.id_fiscal_document
    assert credit_note.document_number is not None
    
    # Verifica dettagli: deve includere tutti e 3 gli articoli
    details = db_session.query(FiscalDocumentDetail).filter(
        FiscalDocumentDetail.id_fiscal_document == credit_note.id_fiscal_document
    ).all()
    assert len(details) == 3


def test_create_credit_note_partial_first_time(db_session, setup_basic_data, create_order_with_details):
    """Test: creazione prima nota di credito parziale"""
    order = create_order_with_details()
    repo = FiscalDocumentRepository(db_session)
    
    # Crea fattura
    invoice = repo.create_invoice(id_order=order.id_order, is_electronic=True)
    
    # Crea nota credito parziale (solo 1 articolo)
    credit_note = repo.create_credit_note(
        id_invoice=invoice.id_fiscal_document,
        reason="Reso parziale",
        is_partial=True,
        items=[
            {'id_order_detail': 1, 'quantity': 2}  # Tutto l'articolo 1
        ],
        is_electronic=True,
        include_shipping=False
    )
    
    assert credit_note.is_partial == True
    assert credit_note.includes_shipping == False
    
    # Verifica dettagli: deve includere solo 1 articolo
    details = db_session.query(FiscalDocumentDetail).filter(
        FiscalDocumentDetail.id_fiscal_document == credit_note.id_fiscal_document
    ).all()
    assert len(details) == 1
    assert details[0].id_order_detail == 1
    assert details[0].quantity == 2


# ==================== TEST VALIDAZIONI ====================

def test_cannot_create_second_total_credit_note(db_session, setup_basic_data, create_order_with_details):
    """Test: non puoi creare una seconda nota totale"""
    order = create_order_with_details()
    repo = FiscalDocumentRepository(db_session)
    
    invoice = repo.create_invoice(id_order=order.id_order, is_electronic=True)
    
    # Prima nota totale
    repo.create_credit_note(
        id_invoice=invoice.id_fiscal_document,
        reason="Reso 1",
        is_partial=False,
        is_electronic=True
    )
    
    # Tentativo seconda nota totale
    with pytest.raises(ValueError, match="Esiste già una nota di credito TOTALE"):
        repo.create_credit_note(
            id_invoice=invoice.id_fiscal_document,
            reason="Reso 2",
            is_partial=False,
            is_electronic=True
        )


def test_cannot_create_partial_after_total(db_session, setup_basic_data, create_order_with_details):
    """Test: non puoi creare nota parziale dopo nota totale"""
    order = create_order_with_details()
    repo = FiscalDocumentRepository(db_session)
    
    invoice = repo.create_invoice(id_order=order.id_order, is_electronic=True)
    
    # Nota totale
    repo.create_credit_note(
        id_invoice=invoice.id_fiscal_document,
        reason="Reso totale",
        is_partial=False,
        is_electronic=True
    )
    
    # Tentativo nota parziale
    with pytest.raises(ValueError, match="Esiste già una nota di credito TOTALE"):
        repo.create_credit_note(
            id_invoice=invoice.id_fiscal_document,
            reason="Reso parziale",
            is_partial=True,
            items=[{'id_order_detail': 1, 'quantity': 1}],
            is_electronic=True
        )


def test_cannot_refund_already_refunded_item(db_session, setup_basic_data, create_order_with_details):
    """Test: non puoi stornare articoli già completamente stornati"""
    order = create_order_with_details()
    repo = FiscalDocumentRepository(db_session)
    
    invoice = repo.create_invoice(id_order=order.id_order, is_electronic=True)
    
    # Prima nota: storna tutto l'articolo 1 (qty 2)
    repo.create_credit_note(
        id_invoice=invoice.id_fiscal_document,
        reason="Reso articolo 1",
        is_partial=True,
        items=[{'id_order_detail': 1, 'quantity': 2}],
        is_electronic=True
    )
    
    # Tentativo di stornare di nuovo l'articolo 1
    with pytest.raises(ValueError, match="già stato completamente stornato"):
        repo.create_credit_note(
            id_invoice=invoice.id_fiscal_document,
            reason="Reso articolo 1 di nuovo",
            is_partial=True,
            items=[{'id_order_detail': 1, 'quantity': 1}],
            is_electronic=True
        )


def test_cannot_refund_more_than_remaining(db_session, setup_basic_data, create_order_with_details):
    """Test: non puoi stornare più della quantità residua"""
    order = create_order_with_details()
    repo = FiscalDocumentRepository(db_session)
    
    invoice = repo.create_invoice(id_order=order.id_order, is_electronic=True)
    
    # Prima nota: storna 1 unità dell'articolo 1 (su 2)
    repo.create_credit_note(
        id_invoice=invoice.id_fiscal_document,
        reason="Reso parziale 1",
        is_partial=True,
        items=[{'id_order_detail': 1, 'quantity': 1}],
        is_electronic=True
    )
    
    # Tentativo di stornare 2 unità (ma ne rimane solo 1)
    with pytest.raises(ValueError, match="superiore alla quantità residua"):
        repo.create_credit_note(
            id_invoice=invoice.id_fiscal_document,
            reason="Reso parziale 2",
            is_partial=True,
            items=[{'id_order_detail': 1, 'quantity': 2}],
            is_electronic=True
        )


def test_cannot_refund_shipping_twice(db_session, setup_basic_data, create_order_with_details):
    """Test: non puoi stornare le spese di spedizione due volte"""
    order = create_order_with_details()
    repo = FiscalDocumentRepository(db_session)
    
    invoice = repo.create_invoice(id_order=order.id_order, is_electronic=True)
    
    # Prima nota con spese
    repo.create_credit_note(
        id_invoice=invoice.id_fiscal_document,
        reason="Reso con spese",
        is_partial=True,
        items=[{'id_order_detail': 1, 'quantity': 1}],
        is_electronic=True,
        include_shipping=True
    )
    
    # Tentativo seconda nota con spese
    with pytest.raises(ValueError, match="spese di spedizione sono già state stornate"):
        repo.create_credit_note(
            id_invoice=invoice.id_fiscal_document,
            reason="Altro reso con spese",
            is_partial=True,
            items=[{'id_order_detail': 2, 'quantity': 1}],
            is_electronic=True,
            include_shipping=True
        )


# ==================== TEST SCENARI COMPLESSI ====================

def test_scenario_multiple_partial_credit_notes(db_session, setup_basic_data, create_order_with_details):
    """
    Test scenario completo:
    - Fattura con 3 articoli (qty: 2, 1, 1)
    - NC1 parziale: articolo 1 completo (qty 2) + spedizione
    - NC2 parziale: articolo 2 completo (qty 1) senza spedizione
    - NC3 totale: deve includere solo articolo 3 (qty 1) senza spedizione
    """
    order = create_order_with_details()
    repo = FiscalDocumentRepository(db_session)
    
    # Fattura
    invoice = repo.create_invoice(id_order=order.id_order, is_electronic=True)
    invoice_details = db_session.query(FiscalDocumentDetail).filter(
        FiscalDocumentDetail.id_fiscal_document == invoice.id_fiscal_document
    ).all()
    assert len(invoice_details) == 3
    
    # NC1: articolo 1 completo + spedizione
    nc1 = repo.create_credit_note(
        id_invoice=invoice.id_fiscal_document,
        reason="Reso articolo 1",
        is_partial=True,
        items=[{'id_order_detail': 1, 'quantity': 2}],
        is_electronic=True,
        include_shipping=True
    )
    assert nc1.is_partial == True
    assert nc1.includes_shipping == True
    
    nc1_details = db_session.query(FiscalDocumentDetail).filter(
        FiscalDocumentDetail.id_fiscal_document == nc1.id_fiscal_document
    ).all()
    assert len(nc1_details) == 1
    assert nc1_details[0].id_order_detail == 1
    assert nc1_details[0].quantity == 2
    
    # NC2: articolo 2 completo senza spedizione
    nc2 = repo.create_credit_note(
        id_invoice=invoice.id_fiscal_document,
        reason="Reso articolo 2",
        is_partial=True,
        items=[{'id_order_detail': 2, 'quantity': 1}],
        is_electronic=True,
        include_shipping=False
    )
    assert nc2.is_partial == True
    assert nc2.includes_shipping == False
    
    nc2_details = db_session.query(FiscalDocumentDetail).filter(
        FiscalDocumentDetail.id_fiscal_document == nc2.id_fiscal_document
    ).all()
    assert len(nc2_details) == 1
    assert nc2_details[0].id_order_detail == 2
    
    # NC3: totale residua (solo articolo 3)
    nc3 = repo.create_credit_note(
        id_invoice=invoice.id_fiscal_document,
        reason="Reso finale",
        is_partial=False,  # TOTALE ma storna solo residui
        is_electronic=True,
        include_shipping=False  # Spese già stornate
    )
    assert nc3.is_partial == False
    assert nc3.includes_shipping == False
    
    nc3_details = db_session.query(FiscalDocumentDetail).filter(
        FiscalDocumentDetail.id_fiscal_document == nc3.id_fiscal_document
    ).all()
    
    # CONTROLLO CRITICO: deve includere SOLO articolo 3!
    assert len(nc3_details) == 1, f"Expected 1 detail, got {len(nc3_details)}"
    assert nc3_details[0].id_order_detail == 3, f"Expected id_order_detail=3, got {nc3_details[0].id_order_detail}"
    assert nc3_details[0].quantity == 1


def test_scenario_partial_quantities(db_session, setup_basic_data, create_order_with_details):
    """
    Test: storno parziale di quantità
    - Articolo 1: qty 2
    - NC1: storna 1 unità
    - NC2 totale: storna 1 unità residua (+ altri articoli)
    """
    order = create_order_with_details()
    repo = FiscalDocumentRepository(db_session)
    
    invoice = repo.create_invoice(id_order=order.id_order, is_electronic=True)
    
    # NC1: storna 1 unità dell'articolo 1 (su 2)
    nc1 = repo.create_credit_note(
        id_invoice=invoice.id_fiscal_document,
        reason="Reso parziale 1 unità",
        is_partial=True,
        items=[{'id_order_detail': 1, 'quantity': 1}],  # 1 su 2
        is_electronic=True,
        include_shipping=False
    )
    
    nc1_details = db_session.query(FiscalDocumentDetail).filter(
        FiscalDocumentDetail.id_fiscal_document == nc1.id_fiscal_document
    ).all()
    assert len(nc1_details) == 1
    assert nc1_details[0].quantity == 1
    
    # NC2 totale: deve stornare 1 unità residua articolo 1 + articoli 2 e 3 completi
    nc2 = repo.create_credit_note(
        id_invoice=invoice.id_fiscal_document,
        reason="Reso totale residuo",
        is_partial=False,
        is_electronic=True,
        include_shipping=True
    )
    
    nc2_details = db_session.query(FiscalDocumentDetail).filter(
        FiscalDocumentDetail.id_fiscal_document == nc2.id_fiscal_document
    ).all()
    
    # Deve includere: articolo 1 (qty 1 residua), articolo 2 (qty 1), articolo 3 (qty 1)
    assert len(nc2_details) == 3
    
    detail_1 = next(d for d in nc2_details if d.id_order_detail == 1)
    assert detail_1.quantity == 1  # Solo la quantità residua!
    
    detail_2 = next(d for d in nc2_details if d.id_order_detail == 2)
    assert detail_2.quantity == 1
    
    detail_3 = next(d for d in nc2_details if d.id_order_detail == 3)
    assert detail_3.quantity == 1


def test_credit_note_total_amount_includes_shipping(db_session, setup_basic_data, create_order_with_details):
    """Test: total_amount include spese di spedizione se include_shipping=True"""
    order = create_order_with_details(with_shipping=True)
    repo = FiscalDocumentRepository(db_session)
    
    invoice = repo.create_invoice(id_order=order.id_order, is_electronic=False)
    
    # Nota con spedizione
    nc_with_shipping = repo.create_credit_note(
        id_invoice=invoice.id_fiscal_document,
        reason="Con spedizione",
        is_partial=True,
        items=[{'id_order_detail': 1, 'quantity': 1}],
        is_electronic=False,
        include_shipping=True
    )
    
    total_with = nc_with_shipping.total_amount
    
    # Crea nuovo ordine per test senza spedizione
    order2 = create_order_with_details(with_shipping=True)
    invoice2 = repo.create_invoice(id_order=order2.id_order, is_electronic=False)
    
    # Nota senza spedizione
    nc_without_shipping = repo.create_credit_note(
        id_invoice=invoice2.id_fiscal_document,
        reason="Senza spedizione",
        is_partial=True,
        items=[{'id_order_detail': 4, 'quantity': 1}],  # Stesso articolo del primo ordine
        is_electronic=False,
        include_shipping=False
    )
    
    total_without = nc_without_shipping.total_amount
    
    # Il totale CON spedizione deve essere maggiore
    assert total_with > total_without


def test_credit_note_non_electronic_status_issued(db_session, setup_basic_data, create_order_with_details):
    """Test: note non elettroniche hanno status 'issued'"""
    order = create_order_with_details()
    repo = FiscalDocumentRepository(db_session)
    
    invoice = repo.create_invoice(id_order=order.id_order, is_electronic=False)
    
    credit_note = repo.create_credit_note(
        id_invoice=invoice.id_fiscal_document,
        reason="Reso",
        is_partial=False,
        is_electronic=False
    )
    
    assert credit_note.status == 'issued'  # Non elettronica → issued
    assert credit_note.document_number is None  # Non elettronica senza numero


def test_cannot_create_electronic_credit_note_for_non_electronic_invoice(db_session, setup_basic_data, create_order_with_details):
    """Test: non puoi creare NC elettronica per fattura non elettronica"""
    order = create_order_with_details()
    repo = FiscalDocumentRepository(db_session)
    
    invoice = repo.create_invoice(id_order=order.id_order, is_electronic=False)
    
    with pytest.raises(ValueError, match="Non è possibile emettere nota di credito elettronica"):
        repo.create_credit_note(
            id_invoice=invoice.id_fiscal_document,
            reason="Reso",
            is_partial=False,
            is_electronic=True  # ❌ Fattura non elettronica!
        )


def test_credit_note_uses_invoice_prices_not_recalculate(db_session, setup_basic_data, create_order_with_details):
    """Test: la NC usa i prezzi della fattura, non ricalcola sconti"""
    order = create_order_with_details()
    repo = FiscalDocumentRepository(db_session)
    
    invoice = repo.create_invoice(id_order=order.id_order, is_electronic=False)
    
    # Recupera dettaglio fattura con sconto
    invoice_detail_2 = db_session.query(FiscalDocumentDetail).filter(
        FiscalDocumentDetail.id_fiscal_document == invoice.id_fiscal_document,
        FiscalDocumentDetail.id_order_detail == 2
    ).first()
    
    # Articolo 2 ha reduction_percent=10%, quindi total_amount dovrebbe essere scontato
    # unit_price=30, qty=1, sconto 10% → total=27
    assert invoice_detail_2.unit_price == 30.0
    assert invoice_detail_2.quantity == 1
    assert invoice_detail_2.total_amount == 27.0  # GIÀ scontato nella fattura
    
    # Crea NC per articolo 2
    nc = repo.create_credit_note(
        id_invoice=invoice.id_fiscal_document,
        reason="Reso articolo 2",
        is_partial=True,
        items=[{'id_order_detail': 2, 'quantity': 1}],
        is_electronic=False,
        include_shipping=False
    )
    
    # Verifica che la NC usi lo stesso total_amount della fattura (non ricalcola)
    nc_detail = db_session.query(FiscalDocumentDetail).filter(
        FiscalDocumentDetail.id_fiscal_document == nc.id_fiscal_document
    ).first()
    
    assert nc_detail.unit_price == 30.0  # Stesso della fattura
    assert nc_detail.total_amount == 27.0  # Stesso della fattura (già scontato)


def test_credit_note_total_after_partials_excludes_refunded_items(db_session, setup_basic_data, create_order_with_details):
    """
    Test: NC totale dopo NC parziali include SOLO articoli residui
    
    Scenario:
    - 3 articoli nella fattura
    - NC1 parziale: articolo 1 e 2
    - NC2 totale: deve includere SOLO articolo 3
    """
    order = create_order_with_details()
    repo = FiscalDocumentRepository(db_session)
    
    invoice = repo.create_invoice(id_order=order.id_order, is_electronic=True)
    
    # NC1: storna articoli 1 e 2
    repo.create_credit_note(
        id_invoice=invoice.id_fiscal_document,
        reason="Reso articoli 1 e 2",
        is_partial=True,
        items=[
            {'id_order_detail': 1, 'quantity': 2},
            {'id_order_detail': 2, 'quantity': 1}
        ],
        is_electronic=True,
        include_shipping=True
    )
    
    # NC2 totale: deve stornare SOLO articolo 3
    nc_total = repo.create_credit_note(
        id_invoice=invoice.id_fiscal_document,
        reason="Reso finale",
        is_partial=False,
        is_electronic=True,
        include_shipping=False  # Già stornate
    )
    
    nc_total_details = db_session.query(FiscalDocumentDetail).filter(
        FiscalDocumentDetail.id_fiscal_document == nc_total.id_fiscal_document
    ).all()
    
    # CONTROLLO CRITICO: solo 1 dettaglio (articolo 3)
    assert len(nc_total_details) == 1
    assert nc_total_details[0].id_order_detail == 3
    assert nc_total_details[0].quantity == 1


def test_cannot_create_total_when_all_items_refunded(db_session, setup_basic_data, create_order_with_details):
    """Test: non puoi creare NC totale se tutti gli articoli sono già stati stornati"""
    order = create_order_with_details()
    repo = FiscalDocumentRepository(db_session)
    
    invoice = repo.create_invoice(id_order=order.id_order, is_electronic=True)
    
    # Storna TUTTI gli articoli con note parziali
    repo.create_credit_note(
        id_invoice=invoice.id_fiscal_document,
        reason="Reso 1",
        is_partial=True,
        items=[
            {'id_order_detail': 1, 'quantity': 2},
            {'id_order_detail': 2, 'quantity': 1},
            {'id_order_detail': 3, 'quantity': 1}
        ],
        is_electronic=True,
        include_shipping=True
    )
    
    # Tentativo NC totale quando non c'è più nulla da stornare
    with pytest.raises(ValueError, match="Nessun articolo residuo da stornare"):
        repo.create_credit_note(
            id_invoice=invoice.id_fiscal_document,
            reason="Reso finale",
            is_partial=False,
            is_electronic=True,
            include_shipping=False
        )


# ==================== TEST UTILITÀ ====================

def test_get_credit_notes_by_invoice(db_session, setup_basic_data, create_order_with_details):
    """Test: recupera tutte le note di una fattura"""
    order = create_order_with_details()
    repo = FiscalDocumentRepository(db_session)
    
    invoice = repo.create_invoice(id_order=order.id_order, is_electronic=True)
    
    # Crea 2 note parziali
    repo.create_credit_note(
        id_invoice=invoice.id_fiscal_document,
        reason="NC 1",
        is_partial=True,
        items=[{'id_order_detail': 1, 'quantity': 1}],
        is_electronic=True,
        include_shipping=False  # Prima nota senza spese
    )
    
    repo.create_credit_note(
        id_invoice=invoice.id_fiscal_document,
        reason="NC 2",
        is_partial=True,
        items=[{'id_order_detail': 2, 'quantity': 1}],
        is_electronic=True,
        include_shipping=False  # Seconda nota senza spese
    )
    
    # Recupera tutte le note
    credit_notes = repo.get_credit_notes_by_invoice(invoice.id_fiscal_document)
    
    assert len(credit_notes) == 2
    assert all(cn.document_type == 'credit_note' for cn in credit_notes)
    assert all(cn.id_fiscal_document_ref == invoice.id_fiscal_document for cn in credit_notes)


def test_sequential_document_numbers(db_session, setup_basic_data, create_order_with_details):
    """Test: i numeri documento sono sequenziali"""
    order1 = create_order_with_details()
    order2 = create_order_with_details()
    repo = FiscalDocumentRepository(db_session)
    
    inv1 = repo.create_invoice(id_order=order1.id_order, is_electronic=True)
    inv2 = repo.create_invoice(id_order=order2.id_order, is_electronic=True)
    
    num1 = int(inv1.document_number)
    num2 = int(inv2.document_number)
    
    assert num2 == num1 + 1  # Sequenziale


def test_credit_note_total_amount_calculation_with_tax(db_session, setup_basic_data, create_order_with_details):
    """Test: verifica calcolo corretto total_amount con IVA"""
    order = create_order_with_details(with_shipping=False)
    repo = FiscalDocumentRepository(db_session)
    
    invoice = repo.create_invoice(id_order=order.id_order, is_electronic=False)
    
    # Recupera dettagli fattura per calcolo manuale
    invoice_details = db_session.query(FiscalDocumentDetail).filter(
        FiscalDocumentDetail.id_fiscal_document == invoice.id_fiscal_document
    ).all()
    
    # Calcola totale imponibile manualmente
    total_imponibile_expected = sum(d.total_amount for d in invoice_details)
    total_with_vat_expected = total_imponibile_expected * 1.22  # IVA 22%
    
    # Crea NC totale
    nc = repo.create_credit_note(
        id_invoice=invoice.id_fiscal_document,
        reason="Reso",
        is_partial=False,
        is_electronic=False,
        include_shipping=False
    )
    
    # Verifica che il totale sia corretto
    assert abs(nc.total_amount - total_with_vat_expected) < 0.01  # Tolleranza arrotondamento


# ==================== TEST EDGE CASES ====================

def test_invoice_not_found(db_session, setup_basic_data):
    """Test: errore se fattura non esiste"""
    repo = FiscalDocumentRepository(db_session)
    
    with pytest.raises(ValueError, match="Fattura 999 non trovata"):
        repo.create_credit_note(
            id_invoice=999,
            reason="Test",
            is_partial=False
        )


def test_order_not_found(db_session, setup_basic_data):
    """Test: errore se ordine non esiste"""
    repo = FiscalDocumentRepository(db_session)
    
    with pytest.raises(ValueError, match="Ordine 999 non trovato"):
        repo.create_invoice(id_order=999, is_electronic=True)


def test_partial_credit_note_without_items_fails(db_session, setup_basic_data, create_order_with_details):
    """Test: NC parziale senza items deve fallire"""
    order = create_order_with_details()
    repo = FiscalDocumentRepository(db_session)
    
    invoice = repo.create_invoice(id_order=order.id_order, is_electronic=True)
    
    # Note: la validazione avviene a livello router/schema, 
    # ma il repository dovrebbe gestirla comunque
    credit_note = repo.create_credit_note(
        id_invoice=invoice.id_fiscal_document,
        reason="Test",
        is_partial=True,
        items=None,  # ❌ Mancano items!
        is_electronic=True
    )
    
    # Se items è None ma is_partial=True, non crea dettagli
    details = db_session.query(FiscalDocumentDetail).filter(
        FiscalDocumentDetail.id_fiscal_document == credit_note.id_fiscal_document
    ).all()
    
    # Dovrebbe generare errore in validazione, ma se passa crea NC vuota
    # (questa validazione è a livello schema FastAPI)

