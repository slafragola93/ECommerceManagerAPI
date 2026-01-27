"""
Factory per creare dati di test per spedizioni
"""
from typing import Optional, List, Dict, Any
from src.schemas.shipping_schema import (
    MultiShippingDocumentCreateRequestSchema,
    MultiShippingDocumentItemSchema,
    MultiShippingDocumentPackageSchema
)


def create_multi_shipment_item_data(
    id_order_detail: int,
    quantity: int = 1,
    **kwargs
) -> Dict[str, Any]:
    """
    Crea dati per un item in multi-shipment.
    
    Args:
        id_order_detail: ID dell'OrderDetail
        quantity: Quantità da spedire
        **kwargs: Campi aggiuntivi
    
    Returns:
        Dict con dati item
    """
    return {
        "id_order_detail": id_order_detail,
        "quantity": quantity,
        **kwargs
    }


def create_multi_shipment_item_schema(**kwargs) -> MultiShippingDocumentItemSchema:
    """Crea un MultiShippingDocumentItemSchema"""
    data = create_multi_shipment_item_data(**kwargs)
    return MultiShippingDocumentItemSchema(**data)


def create_multi_shipment_package_data(
    weight: float = 1.0,
    height: Optional[float] = 10.0,
    width: Optional[float] = 20.0,
    depth: Optional[float] = 15.0,
    length: Optional[float] = 30.0,
    **kwargs
) -> Dict[str, Any]:
    """
    Crea dati per un package in multi-shipment.
    
    Args:
        weight: Peso in kg
        height: Altezza in cm
        width: Larghezza in cm
        depth: Profondità in cm
        length: Lunghezza in cm
        **kwargs: Campi aggiuntivi
    
    Returns:
        Dict con dati package
    """
    return {
        "weight": weight,
        "height": height,
        "width": width,
        "depth": depth,
        "length": length,
        **kwargs
    }


def create_multi_shipment_package_schema(**kwargs) -> MultiShippingDocumentPackageSchema:
    """Crea un MultiShippingDocumentPackageSchema"""
    data = create_multi_shipment_package_data(**kwargs)
    return MultiShippingDocumentPackageSchema(**data)


def create_multi_shipment_request_data(
    id_order: int,
    id_carrier_api: int = 1,
    items: Optional[List[Dict[str, Any] | MultiShippingDocumentItemSchema]] = None,
    packages: Optional[List[Dict[str, Any] | MultiShippingDocumentPackageSchema]] = None,
    id_address_delivery: Optional[int] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Crea dati per una richiesta di multi-shipment.
    
    Args:
        id_order: ID ordine
        id_carrier_api: ID carrier API
        items: Lista di items da spedire
        packages: Lista di packages (opzionale)
        id_address_delivery: ID indirizzo consegna (opzionale)
        **kwargs: Campi aggiuntivi
    
    Returns:
        Dict con dati richiesta
    """
    # Default items se non forniti
    if items is None:
        items = [create_multi_shipment_item_data(id_order_detail=1, quantity=1)]
    else:
        # Converti dict in schema se necessario
        converted_items = []
        for item in items:
            if isinstance(item, dict):
                converted_items.append(create_multi_shipment_item_schema(**item))
            else:
                converted_items.append(item)
        items = converted_items
    
    # Default packages se non forniti
    if packages is None:
        packages = [create_multi_shipment_package_data()]
    else:
        # Converti dict in schema se necessario
        converted_packages = []
        for package in packages:
            if isinstance(package, dict):
                converted_packages.append(create_multi_shipment_package_schema(**package))
            else:
                converted_packages.append(package)
        packages = converted_packages
    
    data = {
        "id_order": id_order,
        "id_carrier_api": id_carrier_api,
        "items": items,
        "packages": packages,
        "id_address_delivery": id_address_delivery,
        **kwargs
    }
    
    return data


def create_multi_shipment_request_schema(**kwargs) -> MultiShippingDocumentCreateRequestSchema:
    """
    Crea un MultiShippingDocumentCreateRequestSchema completo.
    
    Args:
        **kwargs: Override dei campi di default
    
    Returns:
        MultiShippingDocumentCreateRequestSchema pronto per essere usato
    """
    data = create_multi_shipment_request_data(**kwargs)
    return MultiShippingDocumentCreateRequestSchema(**data)


def create_simple_multi_shipment_payload(
    id_order: int,
    id_order_detail: int,
    quantity: int = 1,
    id_carrier_api: int = 1,
    **kwargs
) -> Dict[str, Any]:
    """
    Crea un payload JSON semplice per POST /api/v1/shippings/multi-shipment.
    Utile per test rapidi.
    
    Args:
        id_order: ID ordine
        id_order_detail: ID OrderDetail da spedire
        quantity: Quantità da spedire
        id_carrier_api: ID carrier API
        **kwargs: Override
    
    Returns:
        Dict pronto per essere serializzato in JSON
    """
    request_data = create_multi_shipment_request_data(
        id_order=id_order,
        id_carrier_api=id_carrier_api,
        items=[create_multi_shipment_item_data(id_order_detail=id_order_detail, quantity=quantity)],
        **kwargs
    )
    
    # Converti in dict semplice (non Pydantic)
    payload = {
        "id_order": request_data["id_order"],
        "id_carrier_api": request_data["id_carrier_api"],
        "items": [
            item.model_dump() if hasattr(item, "model_dump") else item
            for item in request_data["items"]
        ],
        "packages": [
            package.model_dump() if hasattr(package, "model_dump") else package
            for package in request_data["packages"]
        ],
        "id_address_delivery": request_data.get("id_address_delivery"),
    }
    
    # Override con kwargs
    payload.update(kwargs)
    
    return payload
