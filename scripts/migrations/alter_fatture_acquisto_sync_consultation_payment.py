#!/usr/bin/env python3
"""
Migration: ciclo passivo — colonne consultazione/pagamento su fatture_acquisto_sync
e tabella figlia fatture_acquisto_sync_details.

Uso:
    python scripts/migrations/alter_fatture_acquisto_sync_consultation_payment.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from sqlalchemy import inspect, text

from src.database import engine


HEADER_COLUMNS = {
    "tipo_documento": "VARCHAR(10) NULL",
    "numero_documento": "VARCHAR(100) NULL",
    "data_documento": "DATE NULL",
    "fornitore_denominazione": "VARCHAR(255) NULL",
    "fornitore_piva": "VARCHAR(30) NULL",
    "importo_totale": "DECIMAL(15,2) NULL",
    "fattura_collegata_numero": "VARCHAR(100) NULL",
    "fattura_collegata_data": "DATE NULL",
    "is_paid": "BOOLEAN NOT NULL DEFAULT 0",
    "id_payment": "INT NULL",
    "paid_at": "DATETIME NULL",
    "note": "TEXT NULL",
}


def upgrade() -> None:
    inspector = inspect(engine)

    with engine.begin() as conn:
        if not inspector.has_table("fatture_acquisto_sync"):
            print("Creazione tabella fatture_acquisto_sync...")
            conn.execute(
                text(
                    """
                    CREATE TABLE fatture_acquisto_sync (
                        id INT NOT NULL AUTO_INCREMENT,
                        identificativo_sdi VARCHAR(50) NOT NULL,
                        nome_file VARCHAR(255) NOT NULL,
                        direzione VARCHAR(50) NULL,
                        tipo VARCHAR(50) NULL,
                        blob_uri VARCHAR(1000) NULL,
                        xml_content TEXT NULL,
                        file_path VARCHAR(500) NULL,
                        partition_key VARCHAR(100) NULL,
                        row_key VARCHAR(100) NULL,
                        etag VARCHAR(100) NULL,
                        tipo_documento VARCHAR(10) NULL,
                        numero_documento VARCHAR(100) NULL,
                        data_documento DATE NULL,
                        fornitore_denominazione VARCHAR(255) NULL,
                        fornitore_piva VARCHAR(30) NULL,
                        importo_totale DECIMAL(15,2) NULL,
                        fattura_collegata_numero VARCHAR(100) NULL,
                        fattura_collegata_data DATE NULL,
                        is_paid BOOLEAN NOT NULL DEFAULT 0,
                        id_payment INT NULL,
                        paid_at DATETIME NULL,
                        note TEXT NULL,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        date_add DATETIME DEFAULT CURRENT_TIMESTAMP,
                        date_upd DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        PRIMARY KEY (id),
                        UNIQUE KEY idx_sdi_nomefile (identificativo_sdi, nome_file),
                        KEY ix_fatture_acquisto_sync_identificativo_sdi (identificativo_sdi),
                        KEY ix_fatture_acquisto_sync_nome_file (nome_file),
                        KEY ix_fatture_acquisto_sync_tipo_documento (tipo_documento),
                        KEY ix_fatture_acquisto_sync_is_paid (is_paid),
                        KEY ix_fatture_acquisto_sync_id_payment (id_payment),
                        CONSTRAINT fk_acquisto_payment
                            FOREIGN KEY (id_payment) REFERENCES payments (id_payment)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """
                )
            )
            print("Tabella fatture_acquisto_sync creata.")
        else:
            columns = {
                col["name"] for col in inspector.get_columns("fatture_acquisto_sync")
            }
            for name, ddl in HEADER_COLUMNS.items():
                if name in columns:
                    print(f"Colonna {name} già presente, skip.")
                    continue
                conn.execute(
                    text(f"ALTER TABLE fatture_acquisto_sync ADD COLUMN {name} {ddl}")
                )
                print(f"Colonna fatture_acquisto_sync.{name} aggiunta.")

            # FK id_payment se assente
            fks = {
                fk["constrained_columns"][0]
                for fk in inspector.get_foreign_keys("fatture_acquisto_sync")
                if fk.get("constrained_columns")
            }
            if "id_payment" not in fks and "id_payment" in (
                columns | set(HEADER_COLUMNS.keys())
            ):
                try:
                    conn.execute(
                        text(
                            """
                            ALTER TABLE fatture_acquisto_sync
                            ADD CONSTRAINT fk_acquisto_payment
                            FOREIGN KEY (id_payment) REFERENCES payments (id_payment)
                            """
                        )
                    )
                    print("FK id_payment -> payments aggiunta.")
                except Exception as exc:
                    print(f"FK id_payment skip/warning: {exc}")

        # Refresh inspector after possible create
        inspector = inspect(engine)
        if not inspector.has_table("fatture_acquisto_sync_details"):
            print("Creazione tabella fatture_acquisto_sync_details...")
            conn.execute(
                text(
                    """
                    CREATE TABLE fatture_acquisto_sync_details (
                        id INT NOT NULL AUTO_INCREMENT,
                        id_purchase_invoice_sync INT NOT NULL,
                        numero_linea INT NOT NULL DEFAULT 1,
                        descrizione VARCHAR(1000) NULL,
                        codice_articolo VARCHAR(100) NULL,
                        quantita DECIMAL(12,5) NOT NULL DEFAULT 1,
                        unita_misura VARCHAR(20) NULL,
                        prezzo_unitario DECIMAL(15,5) NULL,
                        prezzo_totale DECIMAL(15,5) NULL,
                        aliquota_iva DECIMAL(5,2) NULL,
                        natura VARCHAR(10) NULL,
                        PRIMARY KEY (id),
                        KEY ix_acquisto_details_invoice (id_purchase_invoice_sync),
                        CONSTRAINT fk_acquisto_details_invoice
                            FOREIGN KEY (id_purchase_invoice_sync)
                            REFERENCES fatture_acquisto_sync (id)
                            ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """
                )
            )
            print("Tabella fatture_acquisto_sync_details creata.")
        else:
            print("Tabella fatture_acquisto_sync_details già presente, skip.")


if __name__ == "__main__":
    upgrade()
