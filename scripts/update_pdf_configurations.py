#!/usr/bin/env python3
"""
Script per aggiungere/aggiornare le configurazioni necessarie per la generazione PDF.
Mappa le configurazioni esistenti ai nomi usati nel codice PDF.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import SessionLocal
from src.repository.app_configuration_repository import AppConfigurationRepository
from src.schemas.app_configuration_schema import AppConfigurationSchema


def update_pdf_configurations():
    """Aggiorna le configurazioni per la generazione PDF"""
    
    db = SessionLocal()
    try:
        acr = AppConfigurationRepository(db)
        
        # Aggiorna company_logo con path di default
        company_logo = acr.get_by_name_and_category("company_logo", "company_info")
        if company_logo:
            if not company_logo.value or company_logo.value == "":
                # Aggiorna con path di default
                from src.schemas.app_configuration_schema import AppConfigurationUpdateSchema
                acr.update(
                    company_logo,
                    AppConfigurationUpdateSchema(value="media/logos/logo.png")
                )
                print("[OK] Aggiornato company_logo con path di default: media/logos/logo.png")
            else:
                print(f"- company_logo già impostato: {company_logo.value}")
        
        # Aggiungi configurazioni per PEC e SDI se non esistono
        additional_configs = [
            AppConfigurationSchema(
                category="company_info",
                name="pec",
                value="",
                description="PEC (Posta Elettronica Certificata)",
                is_encrypted=False
            ),
            AppConfigurationSchema(
                category="company_info",
                name="sdi_code",
                value="",
                description="Codice SDI (Sistema di Interscambio)",
                is_encrypted=False
            ),
        ]
        
        created_count = 0
        for config in additional_configs:
            existing = acr.get_by_name_and_category(config.name, config.category)
            if not existing:
                acr.create(config)
                created_count += 1
                print(f"[OK] Creata configurazione: {config.category}.{config.name}")
            else:
                print(f"- Configurazione già esistente: {config.category}.{config.name}")
        
        # Mostra mappatura delle configurazioni per il PDF
        print("\n[INFO] Mappatura configurazioni per PDF:")
        print("=" * 60)
        print("Configurazione DB              -> Nome nel codice PDF")
        print("-" * 60)
        print("company_name                   -> company_name")
        print("address                        -> company_address")
        print("city + province                -> company_city")
        print("vat_number                     -> company_vat")
        print("fiscal_code                    -> company_cf")
        print("iban                           -> company_iban")
        print("bic_swift                      -> company_bic")
        print("pec                            -> company_pec")
        print("sdi_code                       -> company_sdi")
        print("company_logo                   -> company_logo")
        print("=" * 60)
        
        print(f"\n[DONE] Aggiornamento completato! {created_count} nuove configurazioni create.")
        print("\n[WARNING] NOTA: Assicurati di aggiornare il codice PDF per usare i nomi corretti:")
        print("   - vat_number invece di company_vat")
        print("   - fiscal_code invece di company_cf")
        print("   - bic_swift invece di company_bic")
        print("   - pec invece di company_pec")
        print("   - sdi_code invece di company_sdi")
        
    except Exception as e:
        print(f"[ERROR] Errore durante l'aggiornamento: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("[START] Aggiornamento configurazioni PDF...")
    update_pdf_configurations()

