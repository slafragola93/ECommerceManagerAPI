"""
Helper per assertion nei test
"""
from typing import Dict, Any, List, Optional
from fastapi.testclient import TestClient
from httpx import Response
from src.events.core.event import Event
from tests.conftest import EventBusSpy


def assert_error_response(
    response: Response,
    status_code: int,
    error_code: Optional[str] = None,
    message_contains: Optional[str] = None
):
    """
    Verifica che una response sia un errore con i dettagli specificati.
    
    Args:
        response: Response HTTP
        status_code: Status code atteso
        error_code: Codice errore atteso (opzionale)
        message_contains: Stringa che deve essere contenuta nel messaggio (opzionale)
    """
    assert response.status_code == status_code, \
        f"Expected status {status_code}, got {response.status_code}. Response: {response.text}"
    
    data = response.json()
    
    if error_code:
        assert "error_code" in data, f"Response should contain 'error_code'. Got: {data}"
        assert data["error_code"] == error_code, \
            f"Expected error_code '{error_code}', got '{data.get('error_code')}'"
    
    if message_contains:
        assert "message" in data, f"Response should contain 'message'. Got: {data}"
        assert message_contains.lower() in data["message"].lower(), \
            f"Message should contain '{message_contains}'. Got: {data['message']}"


def assert_success_response(
    response: Response,
    status_code: int = 200,
    check_fields: Optional[List[str]] = None
):
    """
    Verifica che una response sia di successo con i campi specificati.
    
    Args:
        response: Response HTTP
        status_code: Status code atteso (default: 200)
        check_fields: Lista di campi che devono essere presenti nella response (opzionale)
    """
    assert response.status_code == status_code, \
        f"Expected status {status_code}, got {response.status_code}. Response: {response.text}"
    
    if check_fields:
        data = response.json()
        for field in check_fields:
            assert field in data, f"Response should contain '{field}'. Got: {list(data.keys())}"


def assert_order_status(
    response: Response,
    expected_status: int,
    status_field: str = "id_order_state"
):
    """
    Verifica lo stato di un ordine nella response.
    
    Args:
        response: Response HTTP
        expected_status: Stato atteso
        status_field: Nome del campo che contiene lo stato (default: "id_order_state")
    """
    assert_success_response(response)
    data = response.json()
    
    # Supporta sia response diretta che nested
    if status_field in data:
        assert data[status_field] == expected_status, \
            f"Expected order status {expected_status}, got {data[status_field]}"
    elif "order" in data and status_field in data["order"]:
        assert data["order"][status_field] == expected_status, \
            f"Expected order status {expected_status}, got {data['order'][status_field]}"
    else:
        raise AssertionError(f"Status field '{status_field}' not found in response: {data}")


def assert_event_published(
    event_bus_spy: EventBusSpy,
    event_type: str,
    min_count: int = 1,
    check_data: Optional[Dict[str, Any]] = None
) -> List[Event]:
    """
    Verifica che un evento sia stato pubblicato.
    
    Args:
        event_bus_spy: EventBus spy
        event_type: Tipo di evento atteso
        min_count: Numero minimo di eventi attesi (default: 1)
        check_data: Dict con chiavi/valori che devono essere presenti in event.data (opzionale)
    
    Returns:
        Lista di eventi trovati
    """
    events = event_bus_spy.get_events_by_type(event_type)
    
    assert len(events) >= min_count, \
        f"Expected at least {min_count} events of type '{event_type}', got {len(events)}"
    
    if check_data:
        # Verifica che almeno un evento contenga i dati specificati
        found = False
        for event in events:
            if all(event.data.get(k) == v for k, v in check_data.items()):
                found = True
                break
        
        assert found, \
            f"No event of type '{event_type}' contains the expected data: {check_data}"
    
    return events


def assert_no_event_published(
    event_bus_spy: EventBusSpy,
    event_type: str
):
    """
    Verifica che un evento NON sia stato pubblicato.
    
    Args:
        event_bus_spy: EventBus spy
        event_type: Tipo di evento che NON deve essere presente
    """
    events = event_bus_spy.get_events_by_type(event_type)
    assert len(events) == 0, \
        f"Expected no events of type '{event_type}', but found {len(events)}"


def assert_pagination_response(
    response: Response,
    expected_fields: Optional[List[str]] = None
):
    """
    Verifica che una response di paginazione contenga i campi standard.
    
    Args:
        response: Response HTTP
        expected_fields: Campi aggiuntivi da verificare (opzionale)
    """
    assert_success_response(response)
    data = response.json()
    
    # Campi standard di paginazione
    standard_fields = ["page", "limit", "total"]
    for field in standard_fields:
        assert field in data, f"Pagination response should contain '{field}'. Got: {list(data.keys())}"
    
    if expected_fields:
        for field in expected_fields:
            assert field in data, f"Response should contain '{field}'. Got: {list(data.keys())}"
