"""
Data extractors for event system.

These functions extract relevant data from service method results
to be included in event payloads.
"""

from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


def extract_address_created_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per evento ADDRESS_CREATED.
    
    Args:
        result: Address creato dal service
        kwargs: Contiene 'user' per contesto
    
    Returns:
        Dictionary con dati completi dell'indirizzo
    """
    try:
        if not result:
            return None
        
        address = result
        
        return {
            "id_address": address.id_address,
            "id_customer": address.id_customer,
            "id_country": address.id_country,
            "company": address.company,
            "firstname": address.firstname,
            "lastname": address.lastname,
            "address1": address.address1,
            "address2": address.address2,
            "city": address.city,
            "postcode": address.postcode,
            "phone": address.phone,
            "created_by": kwargs.get('user', {}).get('id')
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati address: {e}")
        return None


def extract_product_created_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per evento PRODUCT_CREATED.
    
    Args:
        result: Product creato dal service
        kwargs: Contiene 'user' per contesto
    
    Returns:
        Dictionary con dati completi del prodotto
    """
    try:
        if not result:
            return None
        
        product = result
        
        return {
            "id_product": product.id_product,
            "id_origin": product.id_origin,
            "id_category": product.id_category,
            "id_brand": product.id_brand,
            "id_platform": product.id_platform,
            "name": product.name,
            "sku": product.sku,
            "reference": product.reference,
            "type": product.type,
            "price_without_tax": float(product.price_without_tax or 0),
            "quantity": product.quantity or 0,
            "created_by": kwargs.get('user', {}).get('id')
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati product created: {e}")
        return None


def extract_product_updated_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per evento PRODUCT_UPDATED.
    
    Args:
        result: Product aggiornato dal service
        kwargs: Contiene 'user' per contesto
    
    Returns:
        Dictionary con dati completi del prodotto
    """
    try:
        if not result:
            return None
        
        product = result
        
        return {
            "id_product": product.id_product,
            "id_origin": product.id_origin,
            "id_category": product.id_category,
            "id_brand": product.id_brand,
            "id_platform": product.id_platform,
            "name": product.name,
            "sku": product.sku,
            "reference": product.reference,
            "type": product.type,
            "price_without_tax": float(product.price_without_tax or 0),
            "quantity": product.quantity or 0,
            "updated_by": kwargs.get('user', {}).get('id')
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati product updated: {e}")
        return None


def extract_customer_created_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per evento CUSTOMER_CREATED.
    
    Args:
        result: Tupla (Customer, bool) dal service o Customer
        kwargs
    
    Returns:
        Dictionary con dati completi del customer
    """
    try:
        if not result:
            return None
        
        # Gestisce sia tupla (customer, is_created) che solo customer
        if isinstance(result, tuple):
            customer, is_created = result
        else:
            customer = result
            is_created = True
        
        return {
            "id_customer": customer.id_customer,
            "id_origin": customer.id_origin,
            "email": customer.email,
            "firstname": customer.firstname,
            "lastname": customer.lastname,
            "is_new": is_created,
            "created_by": kwargs.get('user', {}).get('id')
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati customer created: {e}")
        return None


def extract_customer_updated_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per evento CUSTOMER_UPDATED.
    
    Args:
        result: Customer aggiornato dal service
        kwargs: Contiene 'user' per contesto
    
    Returns:
        Dictionary con dati completi del customer
    """
    try:
        if not result:
            return None
        
        customer = result
        
        return {
            "id_customer": customer.id_customer,
            "id_origin": customer.id_origin,
            "email": customer.email,
            "firstname": customer.firstname,
            "lastname": customer.lastname,
            "updated_by": kwargs.get('user', {}).get('id')
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati customer updated: {e}")
        return None


def extract_customer_deleted_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per evento CUSTOMER_DELETED.
    
    Args:
        result: ID del customer eliminato o Customer stesso
        kwargs: Contiene 'user' per contesto
    
    Returns:
        Dictionary con dati del customer eliminato
    """
    try:
        customer_id = None
        
        if result:
            if isinstance(result, int):
                customer_id = result
            elif hasattr(result, 'id_customer'):
                customer_id = result.id_customer
        
        if customer_id is None:
            # Prova a estrarre da args o kwargs
            customer_id = kwargs.get('customer_id') or (args[0] if args else None)
        
        return {
            "id_customer": customer_id,
            "deleted_by": kwargs.get('user', {}).get('id')
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati customer deleted: {e}")
        return None


def extract_invoice_created_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per evento DOCUMENT_CREATED (invoice).
    
    Args:
        result: FiscalDocument creato dal service
        kwargs: Contiene 'user' per contesto
    
    Returns:
        Dictionary con dati completi del documento fiscale
    """
    try:
        if not result:
            return None
        
        document = result
        
        return {
            "id_fiscal_document": document.id_fiscal_document,
            "document_type": "invoice",
            "document_source": "fiscal_document",
            "number": document.number,
            "id_customer": document.id_customer,
            "total": float(document.total or 0),
            "created_by": kwargs.get('user', {}).get('id')
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati invoice created: {e}")
        return None


def extract_credit_note_created_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per evento DOCUMENT_CREATED (credit_note).
    
    Args:
        result: FiscalDocument creato dal service
        kwargs: Contiene 'user' per contesto
    
    Returns:
        Dictionary con dati completi del documento fiscale
    """
    try:
        if not result:
            return None
        
        document = result
        
        return {
            "id_fiscal_document": document.id_fiscal_document,
            "document_type": "credit_note",
            "document_source": "fiscal_document",
            "number": document.number,
            "id_customer": document.id_customer,
            "total": float(document.total or 0),
            "created_by": kwargs.get('user', {}).get('id')
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati credit note created: {e}")
        return None


def extract_ddt_created_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per evento DOCUMENT_CREATED (ddt).
    
    Args:
        result: OrderDocument creato dal service
        kwargs: Contiene 'user' per contesto
    
    Returns:
        Dictionary con dati completi del DDT
    """
    try:
        if not result:
            return None
        
        document = result
        
        return {
            "id_order_document": document.id_order_document,
            "document_type": "ddt",
            "document_source": "order_document",
            "number": getattr(document, 'number', None),
            "id_customer": document.id_customer,
            "total": float(getattr(document, 'total', 0) or 0),
            "created_by": kwargs.get('user', {}).get('id')
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati ddt created: {e}")
        return None


def extract_ddt_updated_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per evento DOCUMENT_UPDATED (ddt).
    
    Args:
        result: OrderDocument aggiornato dal service
        kwargs: Contiene 'user' per contesto
    
    Returns:
        Dictionary con dati completi del DDT
    """
    try:
        if not result:
            return None
        
        document = result
        
        return {
            "id_order_document": document.id_order_document,
            "document_type": "ddt",
            "document_source": "order_document",
            "number": getattr(document, 'number', None),
            "id_customer": document.id_customer,
            "total": float(getattr(document, 'total', 0) or 0),
            "updated_by": kwargs.get('user', {}).get('id')
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati ddt updated: {e}")
        return None


def extract_ddt_deleted_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per evento DOCUMENT_DELETED (ddt).
    
    Args:
        result: ID del DDT eliminato o OrderDocument stesso
        kwargs: Contiene 'user' per contesto
    
    Returns:
        Dictionary con dati del DDT eliminato
    """
    try:
        document_id = None
        
        if result:
            if isinstance(result, int):
                document_id = result
            elif hasattr(result, 'id_order_document'):
                document_id = result.id_order_document
        
        if document_id is None:
            document_id = kwargs.get('document_id') or (args[0] if args else None)
        
        return {
            "id_order_document": document_id,
            "document_type": "ddt",
            "document_source": "order_document",
            "deleted_by": kwargs.get('user', {}).get('id')
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati ddt deleted: {e}")
        return None


def extract_preventivo_created_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per evento DOCUMENT_CREATED (preventivo).
    
    Args:
        result: OrderDocument creato dal service
        kwargs: Contiene 'user' per contesto
    
    Returns:
        Dictionary con dati completi del preventivo
    """
    try:
        if not result:
            return None
        
        document = result
        
        return {
            "id_order_document": document.id_order_document,
            "document_type": "preventivo",
            "document_source": "order_document",
            "number": getattr(document, 'number', None),
            "id_customer": document.id_customer,
            "total": float(getattr(document, 'total', 0) or 0),
            "created_by": kwargs.get('user', {}).get('id')
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati preventivo created: {e}")
        return None


def extract_preventivo_updated_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per evento DOCUMENT_UPDATED (preventivo).
    
    Args:
        result: OrderDocument aggiornato dal service o dict PreventivoDetailResponseSchema
        kwargs: Contiene 'user' per contesto
    
    Returns:
        Dictionary con dati completi del preventivo
    """
    try:
        if not result:
            return None
        
        # Gestisce sia oggetto OrderDocument che dict (PreventivoDetailResponseSchema)
        if isinstance(result, dict):
            return {
                "id_order_document": result.get('id_order_document'),
                "document_type": "preventivo",
                "document_source": "order_document",
                "number": result.get('document_number'),
                "id_customer": result.get('customer', {}).get('id_customer') if isinstance(result.get('customer'), dict) else None,
                "total": float(result.get('total_price_with_tax', 0) or 0),
                "updated_by": kwargs.get('user', {}).get('id')
            }
        else:
            # Oggetto OrderDocument
            document = result
            return {
                "id_order_document": document.id_order_document,
                "document_type": "preventivo",
                "document_source": "order_document",
                "number": getattr(document, 'number', None),
                "id_customer": document.id_customer,
                "total": float(getattr(document, 'total', 0) or 0),
                "updated_by": kwargs.get('user', {}).get('id')
            }
    except Exception as e:
        logger.error(f"Errore estrazione dati preventivo updated: {e}")
        return None


def extract_preventivo_deleted_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per evento DOCUMENT_DELETED (preventivo).
    
    Args:
        result: ID del preventivo eliminato o OrderDocument stesso
        kwargs: Contiene 'user' per contesto
    
    Returns:
        Dictionary con dati del preventivo eliminato
    """
    try:
        document_id = None
        
        if result:
            if isinstance(result, int):
                document_id = result
            elif hasattr(result, 'id_order_document'):
                document_id = result.id_order_document
        
        if document_id is None:
            document_id = kwargs.get('document_id') or (args[0] if args else None)
        
        return {
            "id_order_document": document_id,
            "document_type": "preventivo",
            "document_source": "order_document",
            "deleted_by": kwargs.get('user', {}).get('id')
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati preventivo deleted: {e}")
        return None


def extract_preventivo_converted_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per evento DOCUMENT_CONVERTED (preventivo -> order).
    
    Args:
        result: Tupla (OrderDocument, Order) o Order creato
        kwargs: Contiene 'user' per contesto
    
    Returns:
        Dictionary con dati della conversione
    """
    try:
        if not result:
            return None
        
        # Gestisce sia tupla che solo order
        if isinstance(result, tuple):
            preventivo, order = result
        else:
            order = result
            preventivo = kwargs.get('preventivo')
        
        data = {
            "document_type": "preventivo",
            "document_source": "order_document",
            "converted_by": kwargs.get('user', {}).get('id')
        }
        
        if preventivo:
            data["id_order_document"] = preventivo.id_order_document if hasattr(preventivo, 'id_order_document') else None
        
        if order:
            data["id_order"] = order.id_order if hasattr(order, 'id_order') else None
        
        return data
    except Exception as e:
        logger.error(f"Errore estrazione dati preventivo converted: {e}")
        return None


def extract_bulk_preventivo_deleted_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per evento DOCUMENT_BULK_DELETED (preventivi).
    
    Args:
        result: Lista di ID eliminati o numero di record eliminati
        kwargs: Contiene 'user' per contesto e 'ids' con lista ID
    
    Returns:
        Dictionary con dati del bulk delete
    """
    try:
        deleted_ids = []
        
        if result:
            if isinstance(result, list):
                deleted_ids = result
            elif isinstance(result, int):
                deleted_ids = [result]
        
        if not deleted_ids:
            deleted_ids = kwargs.get('ids', [])
        
        return {
            "document_type": "preventivo",
            "document_source": "order_document",
            "deleted_count": len(deleted_ids),
            "deleted_ids": deleted_ids,
            "deleted_by": kwargs.get('user', {}).get('id')
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati bulk preventivo deleted: {e}")
        return None

