"""
Test per endpoint ordini
"""
import pytest
from fastapi import status
from httpx import AsyncClient
from tests.helpers.asserts import (
    assert_success_response,
    assert_error_response,
    assert_order_status,
    assert_event_published
)
from tests.factories.order_factory import create_simple_order_payload
from tests.conftest import EventBusSpy


@pytest.mark.integration
class TestOrders:
    """Test per /api/v1/orders/*"""
    
    @pytest.mark.asyncio
    async def test_create_order_success(
        self,
        async_client: AsyncClient,
        admin_client,
        db_session,
        event_bus_spy: EventBusSpy
    ):
        """
        Test: Creazione ordine con successo
        
        Arrange: Payload ordine valido
        Act: POST /api/v1/orders/
        Assert: Status 201, id_order presente, internal_reference presente, evento ORDER_CREATED emesso
        """
        # Arrange: id_order_state=1 e' lo stato di default assegnato a ogni
        # nuovo ordine (order_repository.create), deve esistere in DB.
        from src.models.order_state import OrderState

        db_session.add(OrderState(id_order_state=1, name="In attesa"))
        db_session.commit()

        payload = create_simple_order_payload()
        
        # Act
        response = admin_client.post("/api/v1/orders/", json=payload)
        
        # Assert
        assert_success_response(response, status_code=status.HTTP_201_CREATED)
        data = response.json()
        assert "id_order" in data
        assert "internal_reference" in data
        assert "total_price_with_tax" in data
        
        # Verifica evento emesso
        assert_event_published(
            event_bus_spy,
            "order_created",
            check_data={"id_order": data["id_order"]}
        )
    
    @pytest.mark.asyncio
    async def test_create_order_unauthorized(self, async_client: AsyncClient, user_client):
        """
        Test: Creazione ordine senza permessi
        
        Arrange: Utente senza permesso C su ORDINI
        Act: POST /api/v1/orders/
        Assert: Status 403
        """
        # Arrange
        payload = create_simple_order_payload()
        
        # Act
        response = user_client.post("/api/v1/orders/", json=payload)
        
        # Assert
        assert_error_response(response, status_code=status.HTTP_403_FORBIDDEN)
    
    @pytest.mark.asyncio
    async def test_get_order_by_id_success(self, admin_client, db_session):
        """
        Test: Recupero ordine per ID

        Arrange: Ordine esistente nel database
        Act: GET /api/v1/orders/{order_id}
        Assert: Status 200, dati ordine corretti
        """
        from src.models.order import Order

        order = Order()
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)

        response = admin_client.get(f"/api/v1/orders/{order.id_order}")

        # Assert
        assert_success_response(response)
        data = response.json()
        assert "id_order" in data
        assert data["id_order"] == order.id_order
    
    @pytest.mark.asyncio
    async def test_get_order_not_found(self, admin_client):
        """
        Test: Recupero ordine inesistente
        
        Arrange: Nessun setup
        Act: GET /api/v1/orders/99999
        Assert: Status 404
        """
        order_id = 99999
        
        response = admin_client.get(f"/api/v1/orders/{order_id}")
        
        # Assert
        assert_error_response(response, status_code=status.HTTP_404_NOT_FOUND)
    
    @pytest.mark.asyncio
    async def test_update_order_status_success(
        self,
        admin_client,
        db_session,
        event_bus_spy: EventBusSpy
    ):
        """
        Test: Aggiornamento stato ordine

        Arrange: Ordine esistente
        Act: PATCH /api/v1/orders/{order_id}/status?new_status_id=... (query param, non body)
        Assert: Status 200, stato aggiornato, evento ORDER_STATUS_CHANGED emesso
        """
        from src.models.order import Order
        from src.models.order_state import OrderState

        db_session.add(OrderState(id_order_state=4, name="Spedizione Confermata"))
        order = Order(id_order_state=1)
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)

        order_id = order.id_order
        new_status = 4

        response = admin_client.patch(
            f"/api/v1/orders/{order_id}/status",
            params={"new_status_id": new_status}
        )

        # Assert
        assert_success_response(response)
        assert_order_status(response, expected_status=new_status, status_field="new_status_id")

        # Verifica evento emesso
        assert_event_published(
            event_bus_spy,
            "order_status_changed",
            check_data={"order_id": order_id, "new_state_id": new_status}
        )
