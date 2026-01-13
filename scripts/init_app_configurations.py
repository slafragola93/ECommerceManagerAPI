#!/usr/bin/env python3
"""
Script per inizializzare le configurazioni di default dell'applicazione.
Questo script crea tutte le configurazioni necessarie per il pannello di configurazione dell'app.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import SessionLocal
from src.repository.app_configuration_repository import AppConfigurationRepository
from src.schemas.app_configuration_schema import AppConfigurationSchema


def init_app_configurations():
    """Inizializza tutte le configurazioni di default dell'applicazione"""
    
    db = SessionLocal()
    try:
        acr = AppConfigurationRepository(db)
        
        # Lista di tutte le configurazioni da creare
        configurations = [
            # ANAGRAFICA AZIENDA
            AppConfigurationSchema(
                category="company_info",
                name="company_logo",
                value="",
                description="Logo azienda (path/file)",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="company_info",
                name="company_name",
                value="",
                description="Ragione sociale",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="company_info",
                name="vat_number",
                value="",
                description="Partita IVA",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="company_info",
                name="address",
                value="",
                description="Indirizzo",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="company_info",
                name="civic_number",
                value="",
                description="Numero civico",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="company_info",
                name="postal_code",
                value="",
                description="CAP",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="company_info",
                name="city",
                value="",
                description="Città",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="company_info",
                name="province",
                value="",
                description="Provincia",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="company_info",
                name="phone",
                value="",
                description="Telefono",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="company_info",
                name="email",
                value="",
                description="Email",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="company_info",
                name="bank_name",
                value="",
                description="Banca",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="company_info",
                name="iban",
                value="",
                description="IBAN",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="company_info",
                name="account_holder",
                value="",
                description="Intestazione",
                is_encrypted=False
            ),
            
            # FATTURAZIONE ELETTRONICA
            AppConfigurationSchema(
                category="electronic_invoicing",
                name="tax_regime",
                value="",
                description="Regime fiscale",
                is_encrypted=False
            ),
            
            # FATTURAPA
            AppConfigurationSchema(
                category="fatturapa",
                name="api_key",
                value="",
                description="Chiave API Fatturapa",
                is_encrypted=True
            ),
            AppConfigurationSchema(
                category="fatturapa",
                name="base_url",
                value="",
                description="URL base API Fatturapa",
                is_encrypted=False
            ),
            
            # DDT SENDER
            AppConfigurationSchema(
                category="ddt_sender",
                name="default_sender_address_id",
                value="",
                description="ID indirizzo mittente di default per DDT",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="ddt_sender",
                name="ddt_sender_company_name",
                value="",
                description="Ragione sociale mittente DDT",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="ddt_sender",
                name="ddt_sender_address",
                value="",
                description="Indirizzo mittente DDT",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="ddt_sender",
                name="ddt_sender_vat",
                value="",
                description="Partita IVA mittente DDT",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="ddt_sender",
                name="ddt_sender_phone",
                value="",
                description="Telefono mittente DDT",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="ddt_sender",
                name="ddt_sender_email",
                value="",
                description="Email mittente DDT",
                is_encrypted=False
            ),
            
            # ORDER STATES
            AppConfigurationSchema(
                category="order_states",
                name="is_delivered",
                value="",
                description="ID stato ordine per 'Consegnato'",
                is_encrypted=False
            ),
            
            # ORDER REFERENCE
            AppConfigurationSchema(
                category="order_reference",
                name="order_reference_counter_global",
                value="0",
                description="Contatore globale per generazione internal_reference ordini",
                is_encrypted=False
            ),
            
            # DEFAULT TAX (senza categoria specifica)
            AppConfigurationSchema(
                category="tax",
                name="default_tav",
                value="22.0",
                description="Percentuale IVA di default",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="tax",
                name="default_tax",
                value="22.0",
                description="Percentuale IVA di default (alias)",
                is_encrypted=False
            ),
            
            # IMPOSTAZIONI EMAIL
            AppConfigurationSchema(
                category="email_settings",
                name="sender_name",
                value="",
                description="Nome mittente",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="email_settings",
                name="sender_email",
                value="",
                description="Email",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="email_settings",
                name="password",
                value="",
                description="Password",
                is_encrypted=True
            ),
            AppConfigurationSchema(
                category="email_settings",
                name="ccn",
                value="",
                description="CCN",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="email_settings",
                name="smtp_server",
                value="",
                description="Server SMTP",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="email_settings",
                name="smtp_port",
                value="",
                description="Porta",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="email_settings",
                name="security",
                value="",
                description="Sicurezza",
                is_encrypted=False
            ),
            
            # CHIAVE API APP
            AppConfigurationSchema(
                category="api_keys",
                name="app_api_key",
                value="",
                description="Chiave API App",
                is_encrypted=True
            ),
        ]
        
        # Crea le configurazioni solo se non esistono già
        created_count = 0
        for config in configurations:
            existing = acr.get_by_name_and_category(config.name, config.category)
            if not existing:
                acr.create(config)
                created_count += 1
                print(f"✓ Creata configurazione: {config.category}.{config.name}")
            else:
                print(f"- Configurazione già esistente: {config.category}.{config.name}")
        
        print(f"\n🎉 Inizializzazione completata! {created_count} configurazioni create.")
        
    except Exception as e:
        print(f"❌ Errore durante l'inizializzazione: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("🚀 Inizializzazione configurazioni app...")
    init_app_configurations()
