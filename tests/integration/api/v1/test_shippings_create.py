"""
Test per creazione spedizioni (single shipment)
"""
import pytest
from fastapi import status
from unittest.mock import patch
from tests.helpers.asserts import (
    assert_success_response,
    assert_error_response,
    assert_event_published
)
from tests.conftest import EventBusSpy
from src.models.order import Order
from src.models.shipping import Shipping
from src.routers.shipments import get_carrier_service_factory


@pytest.mark.integration
class TestShippingsCreate:
    """Test per POST /api/v1/shippings/{order_id}/create"""
    
    @pytest.mark.asyncio
    async def test_create_shipment_success(
        self,
        admin_client,
        db_session,
        event_bus_spy: EventBusSpy,
        fake_carrier_factory
    ):
        """
        Test: Creazione spedizione con successo

        Arrange: Ordine esistente con shipping configurato, fake carrier factory
        Act: POST /api/v1/shippings/{order_id}/create
        Assert: Status 200, awb presente, tracking aggiornato, evento SHIPMENT_CREATED emesso
        """
        shipping = Shipping(id_carrier_api=1)
        db_session.add(shipping)
        db_session.commit()
        db_session.refresh(shipping)

        order = Order(id_shipping=shipping.id_shipping)
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)
        order_id = order.id_order

        # Override carrier factory con fake (va fatto sull'app dietro al client,
        # non sul client stesso).
        fake_factory = fake_carrier_factory(awb="TEST123456789")
        admin_client.app.dependency_overrides[get_carrier_service_factory] = lambda: fake_factory

        try:
            # Act
            response = admin_client.post(f"/api/v1/shippings/{order_id}/create")

            # Assert
            assert_success_response(response)
            data = response.json()
            assert "awb" in data or "tracking" in data
            assert data["awb"] == "TEST123456789"

            # Verifica evento emesso
            assert_event_published(
                event_bus_spy,
                "shipment_created",
                check_data={"order_id": order_id}
            )
        finally:
            admin_client.app.dependency_overrides.pop(get_carrier_service_factory, None)
    
    @pytest.mark.asyncio
    async def test_create_shipment_order_not_found(self, admin_client):
        """
        Test: Creazione spedizione per ordine inesistente
        
        Arrange: Nessun setup
        Act: POST /api/v1/shippings/99999/create
        Assert: Status 404
        """
        order_id = 99999
        
        response = admin_client.post(f"/api/v1/shippings/{order_id}/create")
        
        # Assert
        assert_error_response(response, status_code=status.HTTP_404_NOT_FOUND)
    
    @pytest.mark.skip(
        reason="Feature multispedizioni rimandata (2026-09-15): non implementata ora"
    )
    @pytest.mark.asyncio
    async def test_create_shipment_multishipping_partial(
        self,
        admin_client,
        db_session,
        event_bus_spy: EventBusSpy,
        fake_carrier_factory
    ):
        """
        Test: Creazione spedizione per multi-shipment parziale
        
        Arrange: Ordine con is_multishipping=1, solo una spedizione ha tracking
        Act: POST /api/v1/shippings/{order_id}/create con id_order_document
        Assert: Status 200, stato ordine rimane 7 (Multispedizione)
        """
        # TODO: Setup completo:
        # 1. Creare ordine con is_multishipping=1
        # 2. Creare OrderDocument type="shipping" senza tracking
        # 3. Collegare OrderDocument all'ordine
        
        order_id = 1
        id_order_document = 1
        
        fake_factory = fake_carrier_factory(awb="TEST123456789")
        admin_client.app.dependency_overrides[get_carrier_service_factory] = lambda: fake_factory
        
        # Act
        response = admin_client.post(
            f"/api/v1/shippings/{order_id}/create",
            params={"id_order_document": id_order_document}
        )
        
        # Assert
        assert_success_response(response)
        
        # Verifica che lo stato ordine sia 7 (Multispedizione)
        # TODO: Recuperare ordine e verificare id_order_state == 7
        
        pytest.skip("Richiede setup database completo con multi-shipment")
    
    @pytest.mark.skip(
        reason="Feature multispedizioni rimandata (2026-09-15): non implementata ora"
    )
    @pytest.mark.asyncio
    async def test_create_shipment_multishipping_complete(
        self,
        admin_client,
        db_session,
        event_bus_spy: EventBusSpy,
        fake_carrier_factory
    ):
        """
        Test: Creazione spedizione completa per multi-shipment
        
        Arrange: Ordine con is_multishipping=1, tutte le spedizioni hanno tracking
        Act: POST /api/v1/shippings/{order_id}/create (ultima spedizione)
        Assert: Status 200, stato ordine diventa 4 (Spedizione Confermata)
        """
        # TODO: Setup completo:
        # 1. Creare ordine con is_multishipping=1
        # 2. Creare tutte le OrderDocument type="shipping" tranne una
        # 3. Tutte le spedizioni tranne una hanno tracking
        
        order_id = 1
        
        fake_factory = fake_carrier_factory(awb="TEST123456789")
        admin_client.app.dependency_overrides[get_carrier_service_factory] = lambda: fake_factory
        
        # Act
        response = admin_client.post(f"/api/v1/shippings/{order_id}/create")
        
        # Assert
        assert_success_response(response)
        
        # Verifica che lo stato ordine sia 4 (Spedizione Confermata)
        # TODO: Recuperare ordine e verificare id_order_state == 4
        
        pytest.skip("Richiede setup database completo con multi-shipment")
