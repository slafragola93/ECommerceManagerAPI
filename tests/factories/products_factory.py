from typing import Any, Dict, Optional


def create_product_data(
    id_origin: Optional[int] = None,
    id_category: Optional[int] = None,
    id_brand: Optional[int] = None,
    id_store: Optional[int] = None,
    name: str = "Product Test",
    sku: str = "PROD001",
    type: str = "standard",
    reference: str = "REF001",
    weight: float = 0.0,
    depth: float = 0.0,
    height: float = 0.0,
    width: float = 0.0,
    price: float = 0.0,
    quantity: int = 0,
    purchase_price: float = 0.0,
    minimal_quantity: int = 0,
    **kwargs
) -> Dict[str, Any]:
    """Crea dati per un Product"""
    return {
        "id_origin": id_origin,
        "id_category": id_category,
        "id_brand": id_brand,
        "id_store": id_store,
        "name": name,
        "sku": sku,
        "type": type,
        "reference": reference,
        "weight": weight,
        "depth": depth,
        "height": height,
        "width": width,
        "price": price,
        "quantity": quantity,
        "purchase_price": purchase_price,
        "minimal_quantity": minimal_quantity,
        **kwargs
    }
    