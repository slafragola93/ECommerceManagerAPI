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
        # TODO: Setup completo:
        # 1. Creare ordine nel database
        # 2. Creare shipping con id_carrier_api
        # 3. Collegare shipping all'ordine
        
        order_id = 1  # Sostituire con ID reale
        
        # Override carrier factory con fake
        # Nota: l'override va fatto sul test_app, non sul client
        # Per ora commentato fino a setup completo
        # fake_factory = fake_carrier_factory(awb="TEST123456789")
        # admin_client.app.dependency_overrides[get_carrier_service_factory] = lambda: fake_factory
        
        # Act
        response = admin_client.post(f"/api/v1/shippings/{order_id}/create")
        
        # Assert
        assert_success_response(response)
        data = response.json()
        assert "awb" in data or "tracking" in data
        
        # Verifica evento emesso
        assert_event_published(
            event_bus_spy,
            "shipment_created",
            check_data={"order_id": order_id}
        )
        
        pytest.skip("Richiede setup database completo con ordine e shipping")
    
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
