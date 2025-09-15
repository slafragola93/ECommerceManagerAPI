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
                name="fiscal_code",
                value="",
                description="Codice Fiscale",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="company_info",
                name="share_capital",
                value="",
                description="Capitale sociale",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="company_info",
                name="rea_number",
                value="",
                description="Numero REA",
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
                name="country",
                value="",
                description="Nazione",
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
                name="fax",
                value="",
                description="FAX",
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
                name="website",
                value="",
                description="Sito web",
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
                name="bic_swift",
                value="",
                description="BIC/SWIFT",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="company_info",
                name="account_holder",
                value="",
                description="Intestazione",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="company_info",
                name="account_number",
                value="",
                description="Numero conto",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="company_info",
                name="abi",
                value="",
                description="ABI",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="company_info",
                name="cab",
                value="",
                description="CAB",
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
            AppConfigurationSchema(
                category="electronic_invoicing",
                name="transmitter_fiscal_code",
                value="",
                description="Codice fiscale trasmittente",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="electronic_invoicing",
                name="send_progressive",
                value="",
                description="Progressivo Invio",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="electronic_invoicing",
                name="register_number",
                value="",
                description="Iscrizione Albo",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="electronic_invoicing",
                name="rea_registration",
                value="",
                description="Iscrizione REA",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="electronic_invoicing",
                name="cash_type",
                value="",
                description="Tipo Cassa",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="electronic_invoicing",
                name="withholding_type",
                value="",
                description="Tipo Ritenuta",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="electronic_invoicing",
                name="payment_reason",
                value="",
                description="Causale Pagamento",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="electronic_invoicing",
                name="vat_exigibility",
                value="",
                description="Esigibilità IVA",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="electronic_invoicing",
                name="intermediary_name",
                value="",
                description="Intermediario - Denominazione",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="electronic_invoicing",
                name="intermediary_vat",
                value="",
                description="Intermediario - Partita IVA",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="electronic_invoicing",
                name="intermediary_fiscal_code",
                value="",
                description="Intermediario - Codice Fiscale",
                is_encrypted=False
            ),
            
            # ALIQUOTE ESENTI
            AppConfigurationSchema(
                category="exempt_rates",
                name="exempt_rate_standard",
                value="",
                description="Aliquota esente",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="exempt_rates",
                name="exempt_rate_no",
                value="",
                description="Aliquota no",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="exempt_rates",
                name="exempt_rate_no_x",
                value="",
                description="Aliquota noX",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="exempt_rates",
                name="exempt_rate_vat_refund",
                value="",
                description="Restituzione IVA",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="exempt_rates",
                name="exempt_rate_spring",
                value="",
                description="Aliquota spring",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="exempt_rates",
                name="exempt_rate_san_marino",
                value="",
                description="Aliquota San Marino",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="exempt_rates",
                name="exempt_rate_commissions",
                value="",
                description="Aliquota commissioni",
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
