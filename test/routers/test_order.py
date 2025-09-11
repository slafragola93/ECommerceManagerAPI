from datetime import datetime, date

from src import get_db
from src.main import app
from src.models import Order
from src.services.auth import get_current_user
from ..utils import client, test_order, test_orders, test_order_detail, test_order_details, test_customer, test_address, \
    test_order_state, test_platform, test_payment, test_shipping, test_sectional, override_get_db, override_get_current_user, \
    TestingSessionLocal, override_get_current_user_read_only

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user

# Dati di test per gli ordini
test_order_data = {
    "id_address_delivery": 1,
    "id_address_invoice": 1,
    "id_customer": 1,
    "id_platform": 1,
    "id_payment": 1,
    "id_shipping": 1,
    "id_sectional": 1,
    "id_order_state": 1,
    "id_origin": 1,
    "is_invoice_requested": False,
    "is_payed": False,
    "total_weight": 1.5,
    "total_price": 99.99,
    "cash_on_delivery": 0.0
}

expected_order_response = {
    "id_order": 1,
    "id_origin": 1,
    "id_address_delivery": 1,
    "id_address_invoice": 1,
    "id_customer": 1,
    "id_platform": 1,
    "id_payment": 1,
    "id_shipping": 1,
    "id_sectional": 1,
    "id_order_state": 1,
    "is_invoice_requested": False,
    "is_payed": False,
    "payment_date": None,
    "total_weight": 1.5,
    "total_price": 99.99,
    "cash_on_delivery": 0.0,
    "insured_value": 0.0,
    "privacy_note": "Privacy note test",
    "general_note": "General note test",
    "delivery_date": None,
    "date_add": date.today().strftime('%Y-%m-%dT00:00:00'),
    "address_delivery": None,
    "address_invoice": None,
    "customer": None,
    "shipping": None,
    "sectional": None,
    "order_states": None
}


class TestOrderEndpoints:
    """Test per gli endpoint Order"""

    def test_get_all_orders_empty(self):
        """Test GET /orders/ con database vuoto"""
        response = client.get("/api/v1/orders/")
        assert response.status_code == 404
        assert response.json()["detail"] == "Nessun ordine trovato"

    def test_get_all_orders_success(self, test_orders):
        """Test GET /orders/ con ordini presenti"""
        response = client.get("/api/v1/orders/")
        assert response.status_code == 200
        
        data = response.json()
        assert "orders" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert data["total"] == 3
        assert len(data["orders"]) == 3

    def test_get_all_orders_with_filters(self, test_orders):
        """Test GET /orders/ con filtri"""
        # Filtro per customer
        response = client.get("/api/v1/orders/?customers_ids=1")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2  # 2 ordini per customer 1

        # Filtro per stato pagamento
        response = client.get("/api/v1/orders/?is_payed=true")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1  # 1 ordine pagato

        # Filtro per fattura richiesta
        response = client.get("/api/v1/orders/?is_invoice_requested=true")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1  # 1 ordine con fattura richiesta

    def test_get_all_orders_pagination(self, test_orders):
        """Test GET /orders/ con paginazione"""
        response = client.get("/api/v1/orders/?page=1&limit=2")
        assert response.status_code == 200
        
        data = response.json()
        assert data["page"] == 1
        assert data["limit"] == 2
        assert len(data["orders"]) == 2

    def test_get_order_by_id_success(self, test_order):
        """Test GET /orders/{id} con ordine esistente"""
        response = client.get("/api/v1/orders/1")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id_order"] == 1
        assert data["total_price"] == 99.99
        assert data["total_weight"] == 1.5

    def test_get_order_by_id_not_found(self):
        """Test GET /orders/{id} con ordine non esistente"""
        response = client.get("/api/v1/orders/999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Ordine non trovato"

    def test_create_order_success(self, test_customer, test_address, test_order_state, 
                                 test_platform, test_payment, test_shipping, test_sectional):
        """Test POST /orders/ creazione ordine"""
        response = client.post("/api/v1/orders/", json=test_order_data)
        assert response.status_code == 201

    def test_create_order_invalid_data(self):
        """Test POST /orders/ con dati non validi"""
        invalid_data = {
            "id_address_delivery": "invalid",
            "id_customer": "invalid"
        }
        response = client.post("/api/v1/orders/", json=invalid_data)
        assert response.status_code == 422  # Validation error

    def test_update_order_success(self, test_order):
        """Test PUT /orders/{id} aggiornamento ordine"""
        update_data = {
            "id_address_delivery": 1,
            "id_address_invoice": 1,
            "id_customer": 1,
            "id_platform": 1,
            "id_payment": 1,
            "id_shipping": 1,
            "id_sectional": 1,
            "id_order_state": 2,
            "id_origin": 1,
            "is_invoice_requested": True,
            "is_payed": True,
            "total_weight": 2.0,
            "total_price": 149.99,
            "cash_on_delivery": 5.0
        }
        
        response = client.put("/api/v1/orders/1", json=update_data)
        assert response.status_code == 200

    def test_update_order_not_found(self):
        """Test PUT /orders/{id} con ordine non esistente"""
        response = client.put("/api/v1/orders/999", json=test_order_data)
        assert response.status_code == 404
        assert response.json()["detail"] == "Ordine non trovato"

    def test_delete_order_success(self, test_order):
        """Test DELETE /orders/{id} eliminazione ordine"""
        response = client.delete("/api/v1/orders/1")
        assert response.status_code == 204

    def test_delete_order_not_found(self):
        """Test DELETE /orders/{id} con ordine non esistente"""
        response = client.delete("/api/v1/orders/999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Ordine non trovato"

    def test_update_order_status_success(self, test_order):
        """Test PATCH /orders/{id}/status aggiornamento stato"""
        response = client.patch("/api/v1/orders/1/status?new_status_id=2")
        assert response.status_code == 200
        
        data = response.json()
        assert data["message"] == "Stato ordine aggiornato con successo"
        assert data["order_id"] == 1
        assert data["new_status_id"] == 2

    def test_update_order_status_not_found(self):
        """Test PATCH /orders/{id}/status con ordine non esistente"""
        response = client.patch("/api/v1/orders/999/status?new_status_id=2")
        assert response.status_code == 404
        assert response.json()["detail"] == "Ordine non trovato"

    def test_update_order_payment_success(self, test_order):
        """Test PATCH /orders/{id}/payment aggiornamento pagamento"""
        response = client.patch("/api/v1/orders/1/payment?is_payed=true")
        assert response.status_code == 200
        
        data = response.json()
        assert data["message"] == "Stato pagamento aggiornato con successo"
        assert data["order_id"] == 1
        assert data["is_payed"] is True

    def test_update_order_payment_not_found(self):
        """Test PATCH /orders/{id}/payment con ordine non esistente"""
        response = client.patch("/api/v1/orders/999/payment?is_payed=true")
        assert response.status_code == 404
        assert response.json()["detail"] == "Ordine non trovato"

    def test_get_order_details_success(self, test_order, test_order_details):
        """Test GET /orders/{id}/details recupero dettagli ordine"""
        response = client.get("/api/v1/orders/1/details")
        assert response.status_code == 200
        
        data = response.json()
        assert "order_id" in data
        assert "order_details" in data
        assert data["order_id"] == 1
        assert len(data["order_details"]) == 2  # 2 dettagli per order 1

    def test_get_order_details_not_found(self):
        """Test GET /orders/{id}/details con ordine non esistente"""
        response = client.get("/api/v1/orders/999/details")
        assert response.status_code == 404
        assert response.json()["detail"] == "Ordine non trovato"

    def test_get_order_summary_success(self, test_order, test_order_details):
        """Test GET /orders/{id}/summary recupero riassunto ordine"""
        response = client.get("/api/v1/orders/1/summary")
        assert response.status_code == 200
        
        data = response.json()
        assert "order" in data
        assert "order_details" in data
        assert "order_packages" in data
        assert "summary" in data
        
        summary = data["summary"]
        assert "total_items" in summary
        assert "total_packages" in summary
        assert "total_weight" in summary
        assert "total_price" in summary
        assert summary["total_items"] == 2

    def test_get_order_summary_not_found(self):
        """Test GET /orders/{id}/summary con ordine non esistente"""
        response = client.get("/api/v1/orders/999/summary")
        assert response.status_code == 404
        assert response.json()["detail"] == "Ordine non trovato"


class TestOrderEndpointsAuthorization:
    """Test per l'autorizzazione degli endpoint Order"""

    def test_get_orders_unauthorized(self):
        """Test GET /orders/ senza autenticazione"""
        # Rimuovi temporaneamente l'override dell'utente
        app.dependency_overrides.pop(get_current_user, None)
        
        try:
            response = client.get("/api/v1/orders/")
            assert response.status_code == 401
        finally:
            # Ripristina l'override
            app.dependency_overrides[get_current_user] = override_get_current_user

    def test_get_orders_read_only_user(self, test_orders):
        """Test GET /orders/ con utente read-only"""
        app.dependency_overrides[get_current_user] = override_get_current_user_read_only
        
        try:
            response = client.get("/api/v1/orders/")
            assert response.status_code == 200  # Read-only user può leggere
        finally:
            app.dependency_overrides[get_current_user] = override_get_current_user

    def test_create_order_read_only_user(self):
        """Test POST /orders/ con utente read-only (dovrebbe fallire)"""
        app.dependency_overrides[get_current_user] = override_get_current_user_read_only
        
        try:
            response = client.post("/api/v1/orders/", json=test_order_data)
            assert response.status_code == 403  # Read-only user non può creare
        finally:
            app.dependency_overrides[get_current_user] = override_get_current_user

    def test_update_order_read_only_user(self, test_order):
        """Test PUT /orders/{id} con utente read-only (dovrebbe fallire)"""
        app.dependency_overrides[get_current_user] = override_get_current_user_read_only
        
        try:
            response = client.put("/api/v1/orders/1", json=test_order_data)
            assert response.status_code == 403  # Read-only user non può aggiornare
        finally:
            app.dependency_overrides[get_current_user] = override_get_current_user

    def test_delete_order_read_only_user(self, test_order):
        """Test DELETE /orders/{id} con utente read-only (dovrebbe fallire)"""
        app.dependency_overrides[get_current_user] = override_get_current_user_read_only
        
        try:
            response = client.delete("/api/v1/orders/1")
            assert response.status_code == 403  # Read-only user non può eliminare
        finally:
            app.dependency_overrides[get_current_user] = override_get_current_user


class TestOrderEndpointsValidation:
    """Test per la validazione dei parametri degli endpoint Order"""

    def test_get_orders_invalid_page(self):
        """Test GET /orders/ con pagina non valida"""
        response = client.get("/api/v1/orders/?page=0")
        assert response.status_code == 422  # Validation error

    def test_get_orders_invalid_limit(self):
        """Test GET /orders/ con limite non valido"""
        response = client.get("/api/v1/orders/?limit=0")
        assert response.status_code == 422  # Validation error

    def test_get_order_by_id_invalid_id(self):
        """Test GET /orders/{id} con ID non valido"""
        response = client.get("/api/v1/orders/0")
        assert response.status_code == 422  # Validation error

    def test_update_order_status_invalid_status(self, test_order):
        """Test PATCH /orders/{id}/status con stato non valido"""
        response = client.patch("/api/v1/orders/1/status?new_status_id=0")
        assert response.status_code == 422  # Validation error

    def test_update_order_payment_invalid_boolean(self, test_order):
        """Test PATCH /orders/{id}/payment con valore booleano non valido"""
        response = client.patch("/api/v1/orders/1/payment?is_payed=invalid")
        assert response.status_code == 422  # Validation error

    def test_update_order_partial_single_field(self, test_order):
        """Test PUT /orders/{id} aggiornamento parziale con singolo campo"""
        update_data = {
            "total_price": 199.99
        }
        
        response = client.put("/api/v1/orders/1", json=update_data)
        assert response.status_code == 200
        
        # Verifica che solo il campo specificato sia stato aggiornato
        get_response = client.get("/api/v1/orders/1")
        assert get_response.status_code == 200
        order = get_response.json()
        assert order["total_price"] == 199.99
        # Altri campi dovrebbero rimanere invariati
        assert order["total_weight"] == 1.5  # Valore originale

    def test_update_order_partial_relation_fields(self, test_order, test_address):
        """Test PUT /orders/{id} aggiornamento parziale con campi di relazione"""
        update_data = {
            "id_address_delivery": 1,
            "id_address_invoice": 1
        }
        
        response = client.put("/api/v1/orders/1", json=update_data)
        assert response.status_code == 200
        
        # Verifica che i campi di relazione siano stati aggiornati
        get_response = client.get("/api/v1/orders/1")
        assert get_response.status_code == 200
        order = get_response.json()
        print(order)
        assert order["address_delivery"]["id_address"] == 1
        assert order["address_invoice"]["id_address"] == 1

    def test_update_order_partial_mixed_fields(self, test_order):
        """Test PUT /orders/{id} aggiornamento parziale con campi misti"""
        update_data = {
            "id_customer": 2,
            "is_payed": True,
            "total_weight": 3.0
        }
        
        response = client.put("/api/v1/orders/1", json=update_data)
        assert response.status_code == 200
        
        # Verifica che tutti i campi specificati siano stati aggiornati
        get_response = client.get("/api/v1/orders/1")
        assert get_response.status_code == 200
        order = get_response.json()
        assert order["id_customer"] == 2
        assert order["is_payed"] is True
        assert order["total_weight"] == 3.0

    def test_update_order_empty_data(self, test_order):
        """Test PUT /orders/{id} con dati vuoti (dovrebbe funzionare)"""
        update_data = {}
        
        response = client.put("/api/v1/orders/1", json=update_data)
        assert response.status_code == 200
        
        # Verifica che l'ordine non sia cambiato
        get_response = client.get("/api/v1/orders/1")
        assert get_response.status_code == 200
        order = get_response.json()
        assert order["total_price"] == 99.99  # Valore originale
