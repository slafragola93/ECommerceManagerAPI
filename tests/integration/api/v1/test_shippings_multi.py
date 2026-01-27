"""
Test per creazione multi-shipment
"""
import pytest
from fastapi import status
from tests.helpers.asserts import (
    assert_success_response,
    assert_error_response,
    assert_order_status
)
from tests.factories.shipping_factory import create_simple_multi_shipment_payload


@pytest.mark.integration
class TestShippingsMulti:
    """Test per POST /api/v1/shippings/multi-shipment"""
    
    @pytest.mark.asyncio
    async def test_create_multi_shipment_success(
        self,
        admin_client,
        db_session
    ):
        """
        Test: Creazione multi-shipment con successo
        
        Arrange: Ordine esistente con OrderDetail disponibili
        Act: POST /api/v1/shippings/multi-shipment
        Assert: Status 200, OrderDocument creato, stato ordine = 7 (Multispedizione)
        """
        # TODO: Setup completo:
        # 1. Creare ordine nel database
        # 2. Creare OrderDetail con quantità disponibile
        # 3. Creare carrier_api nel database
        
        order_id = 1
        id_order_detail = 1
        
        payload = create_simple_multi_shipment_payload(
            id_order=order_id,
            id_order_detail=id_order_detail,
            quantity=1,
            id_carrier_api=1
        )
        
        # Act
        response = admin_client.post("/api/v1/shippings/multi-shipment", json=payload)
        
        # Assert
        assert_success_response(response, status_code=status.HTTP_201_CREATED)
        data = response.json()
        assert "id_order_document" in data
        assert "id_shipping" in data
        
        # Verifica che lo stato ordine sia 7 (Multispedizione)
        # TODO: Recuperare ordine e verificare id_order_state == 7 e is_multishipping == 1
        
        pytest.skip("Richiede setup database completo con ordine e OrderDetail")
    
    @pytest.mark.asyncio
    async def test_create_multi_shipment_order_not_found(self, admin_client):
        """
        Test: Creazione multi-shipment per ordine inesistente
        
        Arrange: Nessun setup
        Act: POST /api/v1/shippings/multi-shipment con id_order inesistente
        Assert: Status 404
        """
        payload = create_simple_multi_shipment_payload(
            id_order=99999,
            id_order_detail=1,
            quantity=1,
            id_carrier_api=1
        )
        
        response = admin_client.post("/api/v1/shippings/multi-shipment", json=payload)
        
        # Assert
        assert_error_response(response, status_code=status.HTTP_404_NOT_FOUND)
    
    @pytest.mark.asyncio
    async def test_create_multi_shipment_insufficient_quantity(
        self,
        admin_client,
        db_session
    ):
        """
        Test: Creazione multi-shipment con quantità non disponibile
        
        Arrange: Ordine con OrderDetail con quantità limitata
        Act: POST /api/v1/shippings/multi-shipment con quantità > disponibile
        Assert: Status 400, errore business rule
        """
        # TODO: Setup completo:
        # 1. Creare ordine con OrderDetail (quantity=2)
        # 2. Tentare di spedire quantity=3
        
        order_id = 1
        id_order_detail = 1
        
        payload = create_simple_multi_shipment_payload(
            id_order=order_id,
            id_order_detail=id_order_detail,
            quantity=999,  # Quantità eccessiva
            id_carrier_api=1
        )
        
        response = admin_client.post("/api/v1/shippings/multi-shipment", json=payload)
        
        # Assert
        assert_error_response(
            response,
            status_code=status.HTTP_400_BAD_REQUEST,
            message_contains="quantity" or "disponibile"
        )
        
        pytest.skip("Richiede setup database completo con ordine e OrderDetail")
    
    @pytest.mark.asyncio
    async def test_create_multi_shipment_unauthorized(self, user_client):
        """
        Test: Creazione multi-shipment senza permessi
        
        Arrange: Utente senza permesso C
        Act: POST /api/v1/shippings/multi-shipment
        Assert: Status 403
        """
        payload = create_simple_multi_shipment_payload(
            id_order=1,
            id_order_detail=1,
            quantity=1,
            id_carrier_api=1
        )
        
        response = user_client.post("/api/v1/shippings/multi-shipment", json=payload)
        
        # Assert
        assert_error_response(response, status_code=status.HTTP_403_FORBIDDEN)
