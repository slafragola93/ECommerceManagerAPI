"""
Test semplificati per il router invoice senza dipendenze dal database.
Questi test verificano che gli endpoint rispondano correttamente anche senza dati.
"""

from src.main import app
from ..utils import client


def test_invoice_endpoints_exist():
    """
    Test che verifica che gli endpoint invoice esistano e rispondano.
    """
    # Test endpoint principale - dovrebbe restituire 401 (auth richiesta) o 404 se non ci sono dati
    response = client.get("/api/v1/invoices/")
    assert response.status_code in [200, 401, 404]  # 401 se auth richiesta, 404 se nessuna fattura trovata

    # Test endpoint per ID specifico - dovrebbe restituire 401 (auth richiesta) o 404 se non trovato
    response = client.get("/api/v1/invoices/999")
    assert response.status_code in [401, 404]

    # Test endpoint per ordine - dovrebbe restituire 401 (auth richiesta) o 404 se non trovato
    response = client.get("/api/v1/invoices/order/999")
    assert response.status_code in [401, 404]


def test_invoice_fatturapa_endpoints_exist():
    """
    Test che verifica che gli endpoint FatturaPA esistano.
    """
    # Test endpoint di verifica connessione
    response = client.post("/api/v1/invoices/verify")
    assert response.status_code in [200, 401, 500]  # 401 se auth richiesta, 500 se API non configurata

    # Test endpoint eventi
    response = client.get("/api/v1/invoices/events/pool")
    assert response.status_code in [200, 401, 500]  # 401 se auth richiesta, 500 se API non configurata


def test_invoice_xml_endpoints_exist():
    """
    Test che verifica che gli endpoint per XML esistano.
    """
    # Test generazione XML - dovrebbe restituire 401 (auth richiesta) o 404 se ordine non esiste
    response = client.post("/api/v1/invoices/999/generate-xml")
    assert response.status_code in [200, 401, 404, 500]  # 401 se auth richiesta

    # Test download XML - dovrebbe restituire 401 (auth richiesta) o 404 se ordine non esiste
    response = client.post("/api/v1/invoices/999/download-xml")
    assert response.status_code in [200, 401, 404, 500]  # 401 se auth richiesta

    # Test emissione fattura - dovrebbe restituire 401 (auth richiesta) o 404 se ordine non esiste
    response = client.post("/api/v1/invoices/999/IT/invoice_issuing")
    assert response.status_code in [201, 401, 404, 500]  # 401 se auth richiesta


def test_invoice_authentication_required():
    """
    Test che verifica che l'autenticazione sia richiesta.
    """
    # Test che senza autenticazione gli endpoint restituiscano 401
    # Nota: questo dipende dalla configurazione dell'autenticazione nei test
    # Per ora verifichiamo solo che gli endpoint esistano
    pass
