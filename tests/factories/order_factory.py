"""
Factory per creare dati di test per ordini
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from src.schemas.order_schema import OrderSchema
from src.schemas.order_detail_schema import OrderDetailSchema
from src.schemas.customer_schema import CustomerSchema
from src.schemas.address_schema import AddressSchema
from src.schemas.shipping_schema import ShippingSchema
from tests.factories.address_factory import create_address_schema


def create_order_detail_data(
    id_product: Optional[int] = None,
    product_name: str = "Prodotto Test",
    product_reference: str = "PROD001",
    product_qty: int = 1,
    product_weight: float = 0.5,
    unit_price_net: float = 10.0,
    unit_price_with_tax: float = 12.2,
    total_price_net: Optional[float] = None,
    total_price_with_tax: Optional[float] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Crea dati per un OrderDetail.
    
    Args:
        id_product: ID prodotto
        product_name: Nome prodotto
        product_reference: Riferimento prodotto
        product_qty: Quantità
        product_weight: Peso
        unit_price_net: Prezzo unitario senza IVA
        unit_price_with_tax: Prezzo unitario con IVA
        total_price_net: Totale senza IVA (calcolato se None)
        total_price_with_tax: Totale con IVA (calcolato se None)
        **kwargs: Campi aggiuntivi
    
    Returns:
        Dict con dati OrderDetail
    """
    if total_price_net is None:
        total_price_net = unit_price_net * product_qty
    
    if total_price_with_tax is None:
        total_price_with_tax = unit_price_with_tax * product_qty
    
    data = {
        "id_product": id_product,
        "product_name": product_name,
        "product_reference": product_reference,
        "product_qty": product_qty,
        "product_weight": product_weight,
        "unit_price_net": unit_price_net,
        "unit_price_with_tax": unit_price_with_tax,
        "total_price_net": total_price_net,
        "total_price_with_tax": total_price_with_tax,
        **kwargs
    }
    
    return data


def create_order_detail_schema(**kwargs) -> OrderDetailSchema:
    """Crea un OrderDetailSchema"""
    data = create_order_detail_data(**kwargs)
    return OrderDetailSchema(**data)



def create_shipping_data(
    id_carrier_api: Optional[int] = 1,
    price_tax_incl: float = 10.0,
    price_tax_excl: float = 8.2,
    weight: float = 1.0,
    **kwargs
) -> Dict[str, Any]:
    """Crea dati per un Shipping"""
    return {
        "id_carrier_api": id_carrier_api,
        "price_tax_incl": price_tax_incl,
        "price_tax_excl": price_tax_excl,
        "weight": weight,
        **kwargs
    }


def create_shipping_schema(**kwargs) -> ShippingSchema:
    """Crea un ShippingSchema"""
    data = create_shipping_data(**kwargs)
    return ShippingSchema(**data)


def create_order_data(
    customer: Optional[Dict[str, Any] | CustomerSchema | int] = None,
    address_delivery: Optional[Dict[str, Any] | AddressSchema | int] = None,
    address_invoice: Optional[Dict[str, Any] | AddressSchema | int] = None,
    shipping: Optional[Dict[str, Any] | ShippingSchema | int] = None,
    order_details: Optional[List[Dict[str, Any] | OrderDetailSchema]] = None,
    total_price_with_tax: Optional[float] = None,
    id_order_state: int = 1,
    id_platform: int = 1,
    id_store: Optional[int] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Crea dati per un Order.
    
    Args:
        customer: Customer (dict, schema o ID)
        address_delivery: Indirizzo consegna (dict, schema o ID)
        address_invoice: Indirizzo fatturazione (dict, schema o ID)
        shipping: Shipping (dict, schema o ID)
        order_details: Lista di OrderDetail
        total_price_with_tax: Totale con IVA (calcolato se None)
        id_order_state: Stato ordine (default: 1)
        id_platform: ID piattaforma (default: 1)
        id_store: ID store
        **kwargs: Campi aggiuntivi
    
    Returns:
        Dict con dati Order
    """
    # Default customer
    if customer is None:
        customer = create_customer_schema()
    elif isinstance(customer, dict):
        customer = create_customer_schema(**customer)
    
    # Default address
    if address_delivery is None:
        address_delivery = create_address_schema()
    elif isinstance(address_delivery, dict):
        address_delivery = create_address_schema(**address_delivery)
    
    if address_invoice is None:
        address_invoice = address_delivery
    elif isinstance(address_invoice, dict):
        address_invoice = create_address_schema(**address_invoice)
    
    # Default shipping
    if shipping is None:
        shipping = create_shipping_schema()
    elif isinstance(shipping, dict):
        shipping = create_shipping_schema(**shipping)
    
    # Default order details
    if order_details is None:
        order_details = [create_order_detail_schema()]
    else:
        # Converti dict in schema se necessario
        converted_details = []
        for detail in order_details:
            if isinstance(detail, dict):
                converted_details.append(create_order_detail_schema(**detail))
            else:
                converted_details.append(detail)
        order_details = converted_details
    
    # Calcola total_price_with_tax se non fornito
    if total_price_with_tax is None:
        total_price_with_tax = sum(
            detail.total_price_with_tax if hasattr(detail, 'total_price_with_tax') 
            else detail.get('total_price_with_tax', 0)
            for detail in order_details
        )
        # Aggiungi shipping se presente
        if isinstance(shipping, ShippingSchema) and shipping.price_tax_incl:
            total_price_with_tax += shipping.price_tax_incl
        elif isinstance(shipping, dict) and shipping.get('price_tax_incl'):
            total_price_with_tax += shipping['price_tax_incl']
    
    data = {
        "customer": customer,
        "address_delivery": address_delivery,
        "address_invoice": address_invoice,
        "shipping": shipping,
        "order_details": order_details,
        "total_price_with_tax": total_price_with_tax,
        "id_order_state": id_order_state,
        "id_platform": id_platform,
        "id_store": id_store,
        "is_invoice_requested": False,
        **kwargs
    }
    
    return data


def create_order_schema(**kwargs) -> OrderSchema:
    """
    Crea un OrderSchema completo per i test.
    
    Args:
        **kwargs: Override dei campi di default
    
    Returns:
        OrderSchema pronto per essere usato
    """
    data = create_order_data(**kwargs)
    return OrderSchema(**data)


def create_simple_order_payload(
    product_name: str = "Prodotto Test",
    product_qty: int = 1,
    unit_price_with_tax: float = 12.2,
    **kwargs
) -> Dict[str, Any]:
    """
    Crea un payload JSON semplice per POST /api/v1/orders/.
    Utile per test rapidi.
    
    Args:
        product_name: Nome prodotto
        product_qty: Quantità
        unit_price_with_tax: Prezzo unitario con IVA
        **kwargs: Override
    
    Returns:
        Dict pronto per essere serializzato in JSON
    """
    order_data = create_order_data(**kwargs)
    
    # Converti in dict semplice (non Pydantic)
    payload = {
        "customer": order_data["customer"].model_dump() if hasattr(order_data["customer"], "model_dump") else order_data["customer"],
        "address_delivery": order_data["address_delivery"].model_dump() if hasattr(order_data["address_delivery"], "model_dump") else order_data["address_delivery"],
        "address_invoice": order_data["address_invoice"].model_dump() if hasattr(order_data["address_invoice"], "model_dump") else order_data["address_invoice"],
        "shipping": order_data["shipping"].model_dump() if hasattr(order_data["shipping"], "model_dump") else order_data["shipping"],
        "order_details": [
            detail.model_dump() if hasattr(detail, "model_dump") else detail
            for detail in order_data["order_details"]
        ],
        "total_price_with_tax": order_data["total_price_with_tax"],
        "id_order_state": order_data["id_order_state"],
        "id_platform": order_data.get("id_platform", 1),
        "id_store": order_data.get("id_store"),
        "is_invoice_requested": order_data.get("is_invoice_requested", False),
    }
    
    # Override con kwargs
    payload.update(kwargs)
    
    return payload
