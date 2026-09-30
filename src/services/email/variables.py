from typing import Dict, List

PURPOSE_VARIABLES: Dict[str, List[Dict[str, str]]] = {
    "order_shipped": [
        {"key": "firstname", "description": "Nome cliente"},
        {"key": "lastname", "description": "Cognome cliente"},
        {"key": "reference", "description": "Riferimento ordine"},
        {"key": "tracking", "description": "Tracking spedizione"},
        {"key": "carrier_name", "description": "Nome corriere"},
    ],
    "invoice": [
        {"key": "firstname", "description": "Nome cliente"},
        {"key": "lastname", "description": "Cognome cliente"},
        {"key": "document_number", "description": "Numero documento"},
        {"key": "document_date", "description": "Data documento"},
        {"key": "order_reference", "description": "Riferimento ordine"},
        {"key": "total", "description": "Totale documento"},
    ],
    "receipt": [
        {"key": "firstname", "description": "Nome cliente"},
        {"key": "lastname", "description": "Cognome cliente"},
        {"key": "document_number", "description": "Numero ricevuta"},
        {"key": "document_date", "description": "Data emissione"},
        {"key": "order_reference", "description": "Riferimento ordine"},
        {"key": "total", "description": "Totale"},
    ],
    "credit_note": [
        {"key": "firstname", "description": "Nome cliente"},
        {"key": "lastname", "description": "Cognome cliente"},
        {"key": "document_number", "description": "Numero nota di credito"},
        {"key": "document_date", "description": "Data documento"},
        {"key": "order_reference", "description": "Riferimento ordine"},
        {"key": "total", "description": "Totale documento"},
    ],
}


def keys_for_purpose(purpose: str) -> List[str]:
    return [item["key"] for item in PURPOSE_VARIABLES.get(purpose, [])]
