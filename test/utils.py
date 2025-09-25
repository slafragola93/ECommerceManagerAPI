from datetime import datetime, date
import os
import pytest
from dateutil.relativedelta import relativedelta
from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient
from src import Country, Role, OrderState, Invoice, OrderPackage
from src.database import *
from src.main import app
from src.models import CarrierApi, Customer, Category, Brand, User, ShippingState, Product, Address, Carrier, Platform, \
    Lang, Sectional, Message, Configuration, AppConfiguration, Payment, Tax, Shipping, Order, OrderDetail
from src.routers.auth import bcrypt_context

MAX_LIMIT = os.environ.get("MAX_LIMIT")
LIMIT_DEFAULT = int(os.environ.get("LIMIT_DEFAULT"))

# Creazione fake DB SQLITE3
SQLALCHEMY_DATABASE_URL = 'sqlite:///./test.db'

"""
   Crea e restituisce un motore di database SQLAlchemy.

    Questo motore è configurato per connettersi a un database SQLite e utilizza 
    il pool di connessione StaticPool per mantenere una singola connessione aperta.

"""
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={'check_same_thread': False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    """
    Sovrascrive il comportamento predefinito per ottenere una connessione al database.
    Questa funzione genera un'istanza del database TestingSessionLocal.
    Si assicura che la connessione al database sia chiusa correttamente una volta terminato.
    """
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


# Override user con un fake user
def override_get_current_user():
    """
     Sovrascrive l'utente corrente con un utente fittizio.
     Ritorna un dizionario rappresentante un utente fittizio per i test.
     """
    return {"username": "elettronewtest", "id": 1, "roles": [{"name": "ADMIN", "permissions": "CRUD"}]}


def override_get_current_user_read_only():
    """
     Sovrascrive l'utente corrente con un utente fittizio.
     Ritorna un dizionario rappresentante un utente fittizio per i test.
     """
    return {"username": "elettronewtest", "id": 1, "roles": [{"name": "USER", "permissions": "R"}]}


client = TestClient(app)


@pytest.fixture()
def test_brand():
    """
    Crea un record di prova per il marchio nel database fittizio.
    Dopo il test, elimina tutti i record dalla tabella dei marchi.
    """
    brand = Brand(
        id_origin=1,
        name="Samsung",
    )
    db = TestingSessionLocal()
    db.add(brand)
    db.commit()
    yield brand
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM brands;"))
        conn.commit()


@pytest.fixture()
def test_category():
    """
    Crea un record di prova per la categoria nel database fittizio.
    Dopo il test, non viene effettuata nessuna azione di pulizia specifica.
    """
    category_test = Category(
        id_origin=702,
        name="Climatizzatori"
    )
    db = TestingSessionLocal()
    db.add(category_test)
    db.commit()
    yield category_test
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM categories;"))
        conn.commit()


@pytest.fixture()
def test_customer():
    """
    Crea un record di prova per il cliente nel database fittizio.
    Dopo il test, elimina tutti i record dalla tabella dei clienti.
    """
    customer_test = Customer(
        id_origin=0,
        id_lang=1,
        firstname="Enzo",
        lastname="Cristiano",
        email="enzocristiano@elettronew.com",
        date_add=datetime.today()
    )

    db = TestingSessionLocal()
    db.add(customer_test)
    db.commit()
    yield customer_test
    # Quando definisci una fixture che utilizza yield,
    # tutto ciò che scrivi prima di yield fa parte del setup del test,
    # ovvero viene eseguito prima del test vero e proprio.
    # Dopo yield, puoi aggiungere codice che verrà eseguito dopo il test,
    # per fare pulizia o teardown.
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM customers;"))
        conn.commit()


# Creiamo record di un user per poterlo utilizzare nei test
@pytest.fixture()
def test_user(test_roles):
    """
     Crea un record di prova per l'utente nel database fittizio.
     Dopo il test, elimina tutti i record dalla tabella degli utenti.
     """
    user_test = User(
        username="elettronewtest",
        email="enzocristiano@elettronew.com",
        firstname="Enzo",
        lastname="Cristiano",
        password=bcrypt_context.hash("elettronew")
    )
    db = TestingSessionLocal()
    db.add(user_test)
    db.commit()
    yield user_test
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM users;"))
        conn.commit()


@pytest.fixture()
def test_users():
    """
     Crea un record di prova per l'utente nel database fittizio.
     Dopo il test, elimina tutti i record dalla tabella degli utenti.
     """
    queries = [
        User(
            username="salvioc",
            email="salvioc@elettronew.com",
            firstname="Salvio",
            lastname="Esposito",
            password=bcrypt_context.hash("elettronew")
        ),
        User(
            username="mastrict",
            email="trattatomastrict@elettronew.com",
            firstname="Enzo",
            lastname="Mastrict",
            password=bcrypt_context.hash("elettronew")
        ),
    ]
    db = TestingSessionLocal()
    db.add_all(queries)
    db.commit()
    yield queries
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM users;"))
        conn.commit()


@pytest.fixture()
def test_user_read_only():
    """
     Crea un record di prova per l'utente nel database fittizio.
     Dopo il test, elimina tutti i record dalla tabella degli utenti.
     """
    user_test = User(
        username="elettronewtest",
        email="enzocristiano@elettronew.com",
        firstname="Enzo",
        lastname="Cristiano",
        password=bcrypt_context.hash("elettronew"),
        roles=Role(name="USER", permissions="R")
    )
    db = TestingSessionLocal()
    db.add(user_test)
    db.commit()
    yield user_test
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM users;"))
        conn.commit()


@pytest.fixture()
def test_roles():
    queries = [
        Role(
            name="ADMIN",
            permissions="CRUD"
        ),
        Role(
            name="USER",
            permissions="R"
        )
    ]
    db = TestingSessionLocal()
    db.add_all(queries)
    db.commit()
    yield queries
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM roles;"))
        conn.commit()


### TEST PRODOTTO SINGOLO ####
@pytest.fixture()
def test_product():
    """
    Un fixture di Pytest per creare un singolo record di prodotto nel database di test prima dell'esecuzione del test.

    Questo fixture inserisce un record di prova per un prodotto nel database e lo rende disponibile per il test.
    Dopo l'esecuzione del test, effettua la pulizia eliminando tutti i record dalla tabella dei prodotti,
    assicurando che il database di test sia pulito e pronto per i successivi test.

    Yields:
        Product: Un'istanza del prodotto inserito, utile per accedere ai suoi dati nei test.
    """


    product_test = Product(
        id_origin=0,
        id_brand=1,
        id_category=1,
        id_image=None,
        name="Climatizzatore Daikin",
        sku="123456",
        reference="ND",
        type="DUAL",
        weight=0.0,
        depth=0.0,
        height=0.0,
        width=0.0
    )

    db = TestingSessionLocal()
    db.add(product_test)
    db.commit()
    yield product_test
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM products;"))
        conn.commit()


###TEST PRODOTTI#####
@pytest.fixture()
def test_brands():
    """
    Crea record di prova per i brand nel database di test.
    Dopo il test, elimina tutti i record dalla tabella dei brand.
    """
    brands_test = [
        Brand(name="Daikin", id_origin=0),
        Brand(name="Samsung", id_origin=10),
        Brand(name="Dell", id_origin=100)
    ]
    db = TestingSessionLocal()
    db.add_all(brands_test)
    db.commit()
    yield brands_test  # Rende disponibili i brand di prova per i test
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM brands;"))
        conn.commit()


@pytest.fixture()
def test_categories():
    """
    Crea record di prova per le categorie nel database di test.
    Dopo il test, elimina tutti i record dalla tabella delle categorie.
    """
    categories_test = [
        Category(name="Climatizzatori", id_origin=0),
        Category(name="Smartphone", id_origin=10),
        Category(name="Laptop", id_origin=100)
    ]
    db = TestingSessionLocal()
    db.add_all(categories_test)
    db.commit()
    yield categories_test
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM categories;"))
        conn.commit()


### TEST INDIRIZZI ###
@pytest.fixture()
def test_address():
    queries = [
        Country(name="Italia", iso_code="IT"),
        Address(
            id_origin=0,
            id_customer=1,
            id_country=1,
            company="Elettronew",
            firstname="Enzo",
            lastname="Cristiano",
            address1="Via Roma",
            address2="Casa",
            state="Campania",
            postcode="80010",
            city="Napoli",
            phone="34567890",
            mobile_phone="34567890",
            vat="02469660209",
            dni="dni",
            pec="enzocristiano@pec.it",
            sdi="sdi",
            date_add=date.today()
        )
    ]
    db = TestingSessionLocal()
    db.add_all(queries)
    db.commit()
    yield queries
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM addresses;"))
        conn.commit()


@pytest.fixture()
def test_addresses():
    queries = [
        Country(name="Italia", iso_code="IT"),
        Address(
            id_origin=0,
            id_customer=1,
            id_country=1,
            company="Elettronew",
            firstname="Enzo",
            lastname="Cristiano",
            address1="Via Roma",
            address2="Casa",
            state="Campania",
            postcode="80010",
            city="Napoli",
            phone="34567890",
            mobile_phone="34567890",
            vat="02469660209",
            dni="dni",
            pec="enzocristiano@pec.it",
            sdi="sdi",
            date_add=date.today()
        ),
        Country(name="Francia", iso_code="FR"),
        Address(
            id_origin=150,
            id_customer=1,
            id_country=2,
            company="Elettronew FR",
            firstname="Enzo",
            lastname="Cristiano",
            address1="Rue Sainte 10",
            address2="",
            state="Bouche du rhone",
            postcode="13007",
            city="Marseille",
            phone="34567890",
            mobile_phone="34567890",
            vat="02469660209",
            dni="dni",
            pec="enzocristiano@pec.it",
            sdi="sdi",
            date_add=date.today()
        )
    ]
    db = TestingSessionLocal()
    db.add_all(queries)
    db.commit()
    yield queries
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM addresses;"))
        conn.commit()


@pytest.fixture()
def test_carriers():
    queries = [
        Carrier(
            id_origin=10,
            name="Fedex",
        ),
        Carrier(
            id_origin=20,
            name="DHL",
        ),
        Carrier(
            id_origin=21,
            name="UPS",
        ),
        Carrier(
            id_origin=22,
            name="Mondial Relay",
        ),
    ]
    db = TestingSessionLocal()
    db.add_all(queries)
    db.commit()
    yield queries
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM carriers;"))
        conn.commit()


@pytest.fixture()
def test_api_carriers():
    queries = [
        CarrierApi(
            name="DHL Italia",
            account_number=45856558,
            password="dkjhfdshkls",
            site_id="jHLKJFSHkl_jkfd",
            national_service="EHN",
            international_service="PPR",
            is_active=True,
            api_key=""
        ),
        CarrierApi(
            name="DHL Francia",
            account_number=999999854,
            password="ipoopiro",
            site_id="jbjkb",
            national_service="EHN",
            international_service="PPR",
            is_active=False,
            api_key=""
        ),
    ]
    db = TestingSessionLocal()
    db.add_all(queries)
    db.commit()
    yield queries
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM carriers_api;"))
        conn.commit()


@pytest.fixture()
def test_platform():
    queries = [
        Platform(
            name="Prestashop",
            url="https://prestashop.com",
            api_key="GMFDJLKGDSJLGKD"
        ),
        Platform(
            name="Amazon",
            url="https://amazon.com",
            api_key=""
        ),
        Platform(
            name="EBAY",
            url="https://ebay.com",
            api_key="ASFGGSDHJFR"
        ),
    ]
    db = TestingSessionLocal()
    db.add_all(queries)
    db.commit()
    yield queries
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM platforms;"))
        conn.commit()


@pytest.fixture()
def test_lang():
    queries = [
        Lang(
            name="Italian",
            iso_code="it",
        ),
        Lang(
            name="English",
            iso_code="en",
        ),
        Lang(
            name="Spanish",
            iso_code="es",
        ),
        Lang(
            name="French",
            iso_code="fr",
        ),
        Lang(
            name="Deutsch",
            iso_code="de",
        ),
    ]
    db = TestingSessionLocal()
    db.add_all(queries)
    db.commit()
    yield queries
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM languages;"))
        conn.commit()


@pytest.fixture()
def test_sectional():
    queries = [
        Sectional(
            name="p",
        ),
        Sectional(
            name="s",
        ),
        Sectional(
            name="m",
        ),
        Sectional(
            name="n",
        ),
        Sectional(
            name="o",
        ),
    ]
    db = TestingSessionLocal()
    db.add_all(queries)
    db.commit()
    yield queries
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM sectionals;"))
        conn.commit()


@pytest.fixture()
def test_message():
    queries = [
        Message(
            id_user=1,
            message="Necessary breakfast he attention expenses resolution. Outward general passage another as it. Very his are come man walk one next. mN8dM T72cEAfKWGeiA2j4cKpJBClC66m0M0D0fBc7GAZdQqjfZuiDM0K8LwZ3kSd",
        ),
        Message(
            message="Sense child do state to defer mr of forty. Become latter but nor abroad wisdom waited. Was delivered gentleman acuteness but daughters. MCBRPh0Vx0tK6aQD6hhKkEOPxsVZ4O4CWIbI0Wl1MhKJA8RKu1RdmG1VQJr",
        ),
        Message(
            message="Carriage quitting securing be appetite it declared. High eyes kept so busy feel call in. Would day nor ask walls known. But preserved advantage. 8G4rAsZmzgDV0sDJYwzrBrhXEFXsi1ZtNDbU5GgxD5rj2uHcXV0Dg54AAX9WpnNFUya8IM3EowysKvX",
        ),
        Message(
            id_user=1,
            message="Started his hearted any civilly. So me by marianne admitted speaking. Men bred fine call ask. Cease one miles truth day above seven. lCG5XSxlDzXaJf6gIOGD4htTn2FV5I8bCQdYBlQb3Z9nJAp1xS7KdZC9xhUHXL",
        ),
        Message(
            id_user=1,
            message="Admiration stimulated cultivated reasonable be projection possession of. Real no near room ye bred sake if some. Is arranging furnished knowledge. t27CnFwQbbK0uSn1w8iNFrLldmdV2RmXnflQ",
        ),
    ]
    db = TestingSessionLocal()
    db.add_all(queries)
    db.commit()
    yield queries
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM messages;"))
        conn.commit()


@pytest.fixture()
def test_configuration():
    queries = [
        Configuration(
            id_lang=1,
            name="ECOMMERCE_PS",
            value="1"
        ),
        Configuration(
            id_lang=5,
            name="SCRIPT_DEBUG",
            value="1"
        ),
        Configuration(
            id_lang=0,
            name="Tipo Caricamento",
            value="Cron"
        )
    ]
    db = TestingSessionLocal()
    db.add_all(queries)
    db.commit()
    yield queries
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM configurations;"))
        conn.commit()


@pytest.fixture()
def test_payment():
    queries = [
        Payment(
            name="Bonifico Bancario",
            is_complete_payment=False
        ),
        Payment(
            name="Carta Credito",
            is_complete_payment=True
        ),
        Payment(
            name="Contrassegno",
            is_complete_payment=False
        )
    ]
    db = TestingSessionLocal()
    db.add_all(queries)
    db.commit()
    yield queries
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM payments;"))
        conn.commit()


@pytest.fixture()
def test_order_state():
    queries = [
        OrderState(
            name="In attesa di conferma"
        ),
        OrderState(
            name="In corso"
        ),
        OrderState(
            name="Confermata"
        ),
        OrderState(
            name="Annullata"
        )]
    db = TestingSessionLocal()
    db.add_all(queries)
    db.commit()
    yield queries
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM order_states;"))
        conn.commit()


@pytest.fixture()
def test_shipping():
    shipping = Shipping(
        id_carrier_api=1,
        id_shipping_state=1,
        id_tax=3,
        tracking=None,
        weight=0,
        price_tax_incl=0,
        price_tax_excl=0,
        shipping_message=None
    )
    db = TestingSessionLocal()
    db.add(shipping)
    db.commit()
    yield shipping
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM shipments;"))
        conn.commit()


@pytest.fixture()
def test_tax():
    queries = [
        Tax(
            id_country=4,
            is_default=False,
            name="Tassa Francia",
            note="",
            percentage=22,
            electronic_code=""
        ),
        Tax(
            id_country=2,
            is_default=False,
            name="Tassa Italia",
            note="Nei sensi dell'articolo 13",
            percentage=20,
            electronic_code="FR"
        ),
        Tax(
            id_country=1,
            is_default=True,
            name="Tassa Germania",
            note="Nei sensi dell'articolo 13",
            percentage=19,
            electronic_code=""
        )
    ]
    db = TestingSessionLocal()
    db.add_all(queries)
    db.commit()
    yield queries
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM taxes;"))
        conn.commit()


@pytest.fixture()
def test_shipping_state():
    """
    Crea un record di prova per lo stato della spedizione nel database fittizio.
    Dopo il test, elimina tutti i record dalla tabella degli stati di spedizione.
    """
    shipping_state_test = ShippingState(
        name="Spedito"
    )

    db = TestingSessionLocal()
    db.add(shipping_state_test)
    db.commit()
    yield shipping_state_test
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM shipping_state;"))
        conn.commit()


@pytest.fixture()
def test_invoices():
    anno_precedente = datetime.now() - relativedelta(years=1)
    due_anni_precedenti = datetime.now() - relativedelta(years=2)

    queries = [
        Invoice(
            id_order=1,
            document_number="00005",
            filename="IT12345678901_00005.xml",
            xml_content="<?xml version='1.0' encoding='utf-8'?><FatturaElettronica>...</FatturaElettronica>",
            status="sent",
            upload_result='{"status": "success", "message": "Fattura inviata a SdI"}',
            date_add=datetime.now()
        ),
        Invoice(
            id_order=10,
            document_number="00004",
            filename="IT12345678901_00004.xml",
            xml_content="<?xml version='1.0' encoding='utf-8'?><FatturaElettronica>...</FatturaElettronica>",
            status="uploaded",
            upload_result='{"status": "success", "message": "Upload completato"}',
            date_add=datetime.now()
        ),
        Invoice(
            id_order=1,
            document_number="00003",
            filename="IT12345678901_00003.xml",
            xml_content="<?xml version='1.0' encoding='utf-8'?><FatturaElettronica>...</FatturaElettronica>",
            status="error",
            upload_result='{"status": "error", "message": "Errore validazione"}',
            date_add=datetime.now()
        ),
        Invoice(
            id_order=1,
            document_number="00002",
            filename="IT12345678901_00002.xml",
            xml_content="<?xml version='1.0' encoding='utf-8'?><FatturaElettronica>...</FatturaElettronica>",
            status="pending",
            upload_result=None,
            date_add=anno_precedente
        ),
        Invoice(
            id_order=1,
            document_number="00001",
            filename="IT12345678901_00001.xml",
            xml_content="<?xml version='1.0' encoding='utf-8'?><FatturaElettronica>...</FatturaElettronica>",
            status="uploaded",
            upload_result='{"status": "success", "message": "Upload completato"}',
            date_add=due_anni_precedenti
        )
    ]
    db = TestingSessionLocal()
    db.add_all(queries)
    db.commit()
    yield queries
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM invoices;"))
        conn.commit()


@pytest.fixture()
def test_order_package():
    queries = [
        OrderPackage(
            id_order=1,
            height=15.0,
            width=30.0,
            depth=9.5,
            weight=8,
            value=500.0
        ),
        OrderPackage(
            id_order=2,
            height=15.0,
            width=30.0,
            depth=9.5,
            weight=8,
            value=500.0
        ),
        OrderPackage(
            id_order=2,
            height=15.0,
            width=30.0,
            depth=9.5,
            weight=8,
            value=500.0
        )
    ]
    db = TestingSessionLocal()
    db.add_all(queries)
    db.commit()
    yield queries
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM order_packages;"))
        conn.commit()


@pytest.fixture()
def test_order():
    """
    Crea un record di prova per l'ordine nel database fittizio.
    Dopo il test, elimina tutti i record dalla tabella degli ordini.
    """
    order_test = Order(
        id_origin=1,
        id_address_delivery=1,
        id_address_invoice=1,
        id_customer=1,
        id_platform=1,
        id_payment=1,
        id_shipping=1,
        id_sectional=1,
        id_order_state=1,
        is_invoice_requested=False,
        is_payed=False,
        total_weight=1.5,
        total_price=99.99,
        cash_on_delivery=0.0,
        insured_value=0.0,
        privacy_note="Privacy note test",
        general_note="General note test",
        date_add=datetime.today()
    )
    
    db = TestingSessionLocal()
    db.add(order_test)
    db.commit()
    yield order_test
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM orders;"))
        conn.commit()


@pytest.fixture()
def test_orders():
    """
    Crea record di prova per gli ordini nel database fittizio.
    Dopo il test, elimina tutti i record dalla tabella degli ordini.
    """
    orders_test = [
        Order(
            id_origin=1,
            id_address_delivery=1,
            id_address_invoice=1,
            id_customer=1,
            id_platform=1,
            id_payment=1,
            id_shipping=1,
            id_sectional=1,
            id_order_state=1,
            is_invoice_requested=False,
            is_payed=False,
            total_weight=1.5,
            total_price=99.99,
            cash_on_delivery=0.0,
            insured_value=0.0,
            privacy_note="Privacy note test 1",
            general_note="General note test 1",
            date_add=datetime.today()
        ),
        Order(
            id_origin=2,
            id_address_delivery=2,
            id_address_invoice=2,
            id_customer=2,
            id_platform=2,
            id_payment=2,
            id_shipping=1,
            id_sectional=2,
            id_order_state=2,
            is_invoice_requested=True,
            is_payed=True,
            total_weight=2.5,
            total_price=199.99,
            cash_on_delivery=5.0,
            insured_value=10.0,
            privacy_note="Privacy note test 2",
            general_note="General note test 2",
            date_add=datetime.today()
        ),
        Order(
            id_origin=3,
            id_address_delivery=1,
            id_address_invoice=1,
            id_customer=1,
            id_platform=1,
            id_payment=1,
            id_shipping=1,
            id_sectional=1,
            id_order_state=3,
            is_invoice_requested=False,
            is_payed=False,
            total_weight=0.8,
            total_price=49.99,
            cash_on_delivery=0.0,
            insured_value=0.0,
            privacy_note="Privacy note test 3",
            general_note="General note test 3",
            date_add=datetime.today()
        )
    ]
    
    db = TestingSessionLocal()
    db.add_all(orders_test)
    db.commit()
    yield orders_test
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM orders;"))
        conn.commit()


@pytest.fixture()
def test_order_detail():
    """
    Crea un record di prova per il dettaglio ordine nel database fittizio.
    Dopo il test, elimina tutti i record dalla tabella dei dettagli ordine.
    """
    order_detail_test = OrderDetail(
        id_order=1,
        id_invoice=None,
        id_order_document=None,
        id_origin=1,
        id_product=1,
        product_name="Climatizzatore Daikin",
        product_reference="DAI-123",
        product_qty=2,
        product_price=49.99,
        product_weight=0.75,
        rda="RDA123",
        reduction_percent=0.0,
        reduction_amount=0.0
    )
    
    db = TestingSessionLocal()
    db.add(order_detail_test)
    db.commit()
    yield order_detail_test
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM order_details;"))
        conn.commit()


@pytest.fixture()
def test_order_details():
    """
    Crea record di prova per i dettagli ordine nel database fittizio.
    Dopo il test, elimina tutti i record dalla tabella dei dettagli ordine.
    """
    order_details_test = [
        OrderDetail(
            id_order=1,
            id_invoice=None,
            id_order_document=None,
            id_origin=1,
            id_product=1,
            product_name="Climatizzatore Daikin",
            product_reference="DAI-123",
            product_qty=2,
            product_price=49.99,
            product_weight=0.75,
            rda="RDA123",
            reduction_percent=0.0,
            reduction_amount=0.0
        ),
        OrderDetail(
            id_order=1,
            id_invoice=None,
            id_order_document=None,
            id_origin=2,
            id_product=2,
            product_name="Smartphone Samsung",
            product_reference="SAM-456",
            product_qty=1,
            product_price=299.99,
            product_weight=0.2,
            rda="RDA456",
            reduction_percent=10.0,
            reduction_amount=29.99
        ),
        OrderDetail(
            id_order=2,
            id_invoice=None,
            id_order_document=None,
            id_origin=3,
            id_product=3,
            product_name="Laptop Dell",
            product_reference="DEL-789",
            product_qty=1,
            product_price=899.99,
            product_weight=2.1,
            rda="RDA789",
            reduction_percent=0.0,
            reduction_amount=0.0
        )
    ]
    
    db = TestingSessionLocal()
    db.add_all(order_details_test)
    db.commit()
    yield order_details_test
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM order_details;"))
        conn.commit()


@pytest.fixture()
def test_app_configuration():
    """
    Crea record di prova per le configurazioni app nel database fittizio.
    Dopo il test, elimina tutti i record dalla tabella app_configurations.
    """
    queries = [
        AppConfiguration(
            id_lang=0,
            category="company_info",
            name="company_name",
            value="Elettronew S.r.l.",
            description="Ragione sociale",
            is_encrypted=False
        ),
        AppConfiguration(
            id_lang=0,
            category="company_info",
            name="vat_number",
            value="02469660209",
            description="Partita IVA",
            is_encrypted=False
        ),
        AppConfiguration(
            id_lang=0,
            category="electronic_invoicing",
            name="tax_regime",
            value="RF01",
            description="Regime fiscale",
            is_encrypted=False
        ),
        AppConfiguration(
            id_lang=0,
            category="email_settings",
            name="sender_email",
            value="noreply@elettronew.com",
            description="Email mittente",
            is_encrypted=False
        ),
        AppConfiguration(
            id_lang=0,
            category="api_keys",
            name="app_api_key",
            value="secret_api_key_123",
            description="Chiave API App",
            is_encrypted=True
        )
    ]
    db = TestingSessionLocal()
    db.add_all(queries)
    db.commit()
    yield queries
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM app_configurations;"))
        conn.commit()
