#!/usr/bin/env python3
"""
Script di Setup Iniziale per ECommerceManagerAPI
Esegue il setup necessario: Order State, Shipping State, App Configuration,
Platform, Store, Role, Utente admin, CompanyFiscalInfo.
Tax lasciato vuoto (nessun inserimento).
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import SessionLocal
from src.models.app_configuration import AppConfiguration
from src.models.order_state import OrderState
from src.models.platform import Platform
from src.models.shipping_state import ShippingState
from src.models.store import Store
from src.models.company_fiscal_info import CompanyFiscalInfo
from src.models.role import Role
from src.models.user import User
from passlib.context import CryptContext

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ---------------------------------------------------------------------------
# Order State: ID e nome (inseriti solo se tabella vuota)
# ---------------------------------------------------------------------------
ORDER_STATES_DATA = [
    (1, "In Preparazione"),
    (2, "Pronti Per La Spedizione"),
    (3, "Spediti"),
    (4, "Spedizione Confermata"),
    (5, "Annullati"),
    (6, "In Attesa"),
    (7, "Multispedizione"),
]

# ---------------------------------------------------------------------------
# Shipping State: ID e nome (inseriti solo se tabella vuota)
# ---------------------------------------------------------------------------
SHIPPING_STATES_DATA = [
    (1, "Spedizione In Preparazione"),
    (2, "Tracking Assegnato"),
    (3, "Spedizione Presa In Carico"),
    (4, "Spedizione Partita"),
    (5, "Spedizione In Transito"),
    (6, "Spedizione In Giacenza"),
    (7, "Spedizione In Consegna"),
    (8, "Spedizione Consegnata"),
    (9, "Spedizione In Dogana"),
    (10, "Spedizione Bloccata"),
    (11, "Spedizione Annullata"),
    (12, "Stato Sconosciuto"),
    (13, "In Attesa Di Seconda Spedizione"),
]

# ---------------------------------------------------------------------------
# App Configuration: variabili in tabella (category, name), senza valori
# (category, name, description, is_encrypted)
# ---------------------------------------------------------------------------
APP_CONFIGURATIONS_DATA = [
    # company_info
    ("company_info", "company_logo", "Logo azienda", False),
    ("company_info", "city", "Città", False),
    ("company_info", "province", "Provincia", False),
    ("company_info", "phone", "Telefono", False),
    ("company_info", "email", "Email", False),
    ("company_info", "company_name", "Ragione sociale", False),
    ("company_info", "vat_number", "Partita IVA", False),
    ("company_info", "address", "Indirizzo", False),
    ("company_info", "postal_code", "CAP", False),
    ("company_info", "bank_name", "Banca", False),
    ("company_info", "iban", "IBAN", False),
    ("company_info", "account_holder", "Intestatario conto", False),
    ("company_info", "pec", "PEC", False),
    ("company_info", "sdi_code", "Codice SDI", False),
    ("company_info", "fiscal_code", "Codice fiscale", False),
    ("company_info", "share_capital", "Capitale sociale", False),
    ("company_info", "rea_number", "Numero REA", False),
    ("company_info", "country", "Paese", False),
    ("company_info", "abi", "ABI", False),
    ("company_info", "fax", "Fax", False),
    ("company_info", "bic_swift", "BIC/SWIFT", False),
    ("company_info", "website", "Sito web", False),
    ("company_info", "account_number", "Numero conto", False),
    ("company_info", "cab", "CAB", False),
    # electronic_invoicing
    ("electronic_invoicing", "tax_regime", "Regime fiscale", False),
    ("electronic_invoicing", "payment_reason", "Causale pagamento", False),
    ("electronic_invoicing", "csa_type", "Tipo cassa", False),
    ("electronic_invoicing", "withholding_type", "Tipo ritenuta", False),
    ("electronic_invoicing", "vat_deductibility", "Esigibilità IVA", False),
    ("electronic_invoicing", "payment_type", "Tipo pagamento", False),
    # fatturapa
    ("fatturapa", "api_key", "Chiave API Fatturapa", True),
    # email_settings
    ("email_settings", "sender_name", "Nome mittente", False),
    ("email_settings", "sender_email", "Email mittente", False),
    ("email_settings", "password", "Password email", True),
    ("email_settings", "ccn", "CCN", False),
    ("email_settings", "smtp_server", "Server SMTP", False),
    ("email_settings", "smtp_port", "Porta SMTP", False),
    ("email_settings", "security", "Sicurezza", False),
    # order_states
    ("order_states", "is_delivered", "ID stato ordine Consegnato", False),
    # ddt_sender
    ("ddt_sender", "ddt_sender_company_name", "Ragione sociale mittente DDT", False),
    ("ddt_sender", "ddt_sender_address", "Indirizzo mittente DDT", False),
    ("ddt_sender", "ddt_sender_vat", "P.IVA mittente DDT", False),
    ("ddt_sender", "ddt_sender_phone", "Telefono mittente DDT", False),
    ("ddt_sender", "ddt_sender_email", "Email mittente DDT", False),
    # order_reference
    ("order_reference", "order_reference_counter_global", "Contatore internal_reference", False),
    # invoicing
    ("invoicing", "default_tav", "Percentuale IVA di default", False),
]


def setup_order_states(db):
    """Inserisce Order State (solo se tabella vuota)."""
    print("\n📦 Order States...")
    if db.query(OrderState).count() > 0:
        print(f"  ℹ️  Già presenti: {db.query(OrderState).count()}")
        return
    for id_state, name in ORDER_STATES_DATA:
        db.add(OrderState(id_order_state=id_state, name=name))
        print(f"  ✅ {id_state} - {name}")
    db.commit()
    print(f"  Inseriti {len(ORDER_STATES_DATA)} order states.")


def setup_shipping_states(db):
    """Inserisce Shipping State (solo se tabella vuota)."""
    print("\n🚚 Shipping States...")
    if db.query(ShippingState).count() > 0:
        print(f"  ℹ️  Già presenti: {db.query(ShippingState).count()}")
        return
    for id_state, name in SHIPPING_STATES_DATA:
        db.add(ShippingState(id_shipping_state=id_state, name=name))
        print(f"  ✅ {id_state} - {name}")
    db.commit()
    print(f"  Inseriti {len(SHIPPING_STATES_DATA)} shipping states.")


def setup_app_configurations(db):
    """Inserisce App Configuration (stesse chiavi in tabella, value vuoto)."""
    print("\n🔧 App Configurations...")
    created = 0
    for category, name, description, is_encrypted in APP_CONFIGURATIONS_DATA:
        existing = db.query(AppConfiguration).filter(
            AppConfiguration.category == category,
            AppConfiguration.name == name,
        ).first()
        if not existing:
            db.add(AppConfiguration(
                id_lang=0,
                id_store=None,
                category=category,
                name=name,
                value="",
                description=description,
                is_encrypted=is_encrypted,
            ))
            created += 1
            print(f"  ✅ {category}.{name}")
    db.commit()
    print(f"  Create {created} configurazioni.")


def setup_platform(db):
    """Inserisce Platform: 1 Prestashop (solo se non esiste)."""
    print("\n🛒 Platform...")
    if db.query(Platform).filter(Platform.id_platform == 1).first():
        print("  ℹ️  Platform id=1 già presente.")
        return
    db.add(Platform(id_platform=1, name="Prestashop", is_default=True))
    db.commit()
    print("  ✅ 1 - Prestashop")


def setup_store(db):
    """Inserisce uno Store: Elettronew (solo se id_store 1 non esiste)."""
    print("\n🏪 Store...")
    if db.query(Store).filter(Store.id_store == 1).first():
        print("  ℹ️  Store id=1 già presente.")
        return
    # id_store=1, id_platform=1, name=Elettronew, base_url, api_key, is_active=1, is_default=1, logo=None
    store = Store(
        id_store=1,
        id_platform=1,
        name="Elettronew",
        base_url="https://migrationnine.testelettronw.com",
        api_key="ZTN7KG2W7J6SFGPECW63PHQ6WQSVKYBF",
        logo=None,
        is_active=True,
        is_default=True,
        date_add=datetime(2025, 12, 12, 16, 2, 8),
        updated_at=datetime(2026, 2, 11, 15, 5, 9),
    )
    db.add(store)
    db.commit()
    print("  ✅ Store Elettronew (id=1)")


def setup_role(db):
    """Inserisce Role ADMIN con permissions CRUD (solo se non esiste)."""
    print("\n👤 Role...")
    role = db.query(Role).filter(Role.name == "ADMIN").first()
    if role:
        print("  ℹ️  Role ADMIN già presente.")
        return role
    role = Role(name="ADMIN", permissions="CRUD")
    db.add(role)
    db.commit()
    db.refresh(role)
    print("  ✅ ADMIN (CRUD)")
    return role


def setup_admin_user(db):
    """
    Crea utente admin con tutti i permessi.
    username: admin, firstname: admin, lastname: admin,
    password: admin (SOLO PER SETUP - cambiare in produzione),
    email: admin@elettronew.com, is_active=1.
    """
    print("\n🔐 Utente admin...")
    if db.query(User).filter(User.username == "admin").first():
        print("  ℹ️  Utente admin già presente.")
        return
    admin_role = db.query(Role).filter(Role.name == "ADMIN").first()
    if not admin_role:
        raise RuntimeError("Role ADMIN non trovato. Eseguire prima setup_role().")
    # Password "admin" hashed con bcrypt (come in auth)
    user = User(
        username="admin",
        firstname="admin",
        lastname="admin",
        password=bcrypt_context.hash("admin"),  # SOLO SETUP: cambiare in produzione
        email="admin@elettronew.com",
        is_active=True,
        date_add=datetime.now().date(),
    )
    db.add(user)
    db.flush()
    user.roles.append(admin_role)
    db.commit()
    print("  ✅ admin / admin@elettronew.com (password: admin - cambiare in produzione)")


def setup_company_fiscal_info(db):
    """Inserisce CompanyFiscalInfo per store 1: Elettronew, P.IVA 08632861210, is_default=1."""
    print("\n📄 CompanyFiscalInfo...")
    if db.query(CompanyFiscalInfo).filter(CompanyFiscalInfo.id_company_fiscal_info == 1).first():
        print("  ℹ️  CompanyFiscalInfo id=1 già presente.")
        return
    ts = datetime(2026, 1, 20, 11, 4, 24)
    db.add(CompanyFiscalInfo(
        id_company_fiscal_info=1,
        id_store=1,
        company_name="Elettronew",
        vat_number="08632861210",
        fiscal_code=None,
        rea_number=None,
        address=None,
        postal_code=None,
        city=None,
        province=None,
        country="IT",
        phone=None,
        fax=None,
        email=None,
        pec=None,
        sdi_code=None,
        bank_name=None,
        iban=None,
        bic_swift=None,
        abi=None,
        cab=None,
        account_holder=None,
        account_number=None,
        is_default=True,
        date_add=ts,
        updated_at=ts,
    ))
    db.commit()
    print("  ✅ Elettronew - 08632861210 (id_store=1, is_default=1)")


def main():
    print("🚀 ECommerceManagerAPI - Setup Iniziale")
    print("=" * 50)

    db = SessionLocal()
    try:
        setup_order_states(db)
        setup_shipping_states(db)
        setup_app_configurations(db)
        setup_platform(db)
        setup_store(db)
        setup_role(db)
        setup_admin_user(db)
        setup_company_fiscal_info(db)
        # Tax: lasciato vuoto (nessun inserimento)

        print("\n" + "=" * 50)
        print("🎉 Setup completato.")
        print("  - Order States, Shipping States, App Configurations")
        print("  - Platform Prestashop, Store Elettronew")
        print("  - Role ADMIN (CRUD), Utente admin (admin / admin)")
        print("  - CompanyFiscalInfo Elettronew")
        print("  - Tax: nessun inserimento (tabella vuota)")
        print("\n🚀 Avvio API: uvicorn src.main:app --reload")
    except Exception as e:
        db.rollback()
        print(f"\n❌ Errore: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
