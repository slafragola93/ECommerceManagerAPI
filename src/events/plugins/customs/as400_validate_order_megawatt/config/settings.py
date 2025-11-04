"""Impostazioni di configurazione per il plugin di validazione AS400."""

import os
from typing import Optional

# Modalità test di default: 0 = invia al web service (produzione), 1 = solo log XML (test)
TEST_MODE = 1


def get_settings() -> dict:
    """Recupera le impostazioni del plugin."""
    return {
        "test_mode": TEST_MODE,
        "soap_endpoint": os.environ.get(
            "AS400_SOAP_ENDPOINT",
            "http://webservices.gruppomegawatt.it:4500/wsWebMarket.asmx"
        ),
        "soap_action": "http://webservice.gruppomegawatt.it/WS_WebMarket/InserisciOrdineWebMarket",
        "connect_timeout": 10,
        "total_timeout": 30,
        "max_retries": 2,
        "retry_backoff": [1, 2],  # secondi
    }


def set_test_mode(value: int) -> None:
    """Sovrascrive la modalità test programmaticamente."""
    global TEST_MODE
    TEST_MODE = value

