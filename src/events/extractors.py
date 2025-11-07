"""
Estrattori di dati per eventi business.

Questo modulo contiene funzioni estrattore che trasformano i risultati delle operazioni
business in dati ricchi e completi per gli eventi, permettendo ai plugin di operare
senza query aggiuntive al database.

Ogni estrattore:
- Accetta *args, result=None, **kwargs
- Estrae dati completi dall'entità (non solo ID)
- Include tenant/contesto dal parametro 'user'
- Gestisce None/errori gracefully
- Segue principio SOLID SRP (Single Responsibility Principle)
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)


# ==================== HELPER FUNCTIONS ====================

def _safe_get_tenant(kwargs: dict) -> str:
    """
    Estrae il tenant dal contesto utente in modo sicuro.
    
    Args:
        kwargs: Keyword arguments contenenti possibilmente 'user'
    
    Returns:
        Nome del tenant o 'default' se non trovato
    """
    try:
        user = kwargs.get('user', {})
        return user.get('tenant', 'default') if isinstance(user, dict) else 'default'
    except Exception:
        return 'default'


def _safe_get_user_id(kwargs: dict) -> Optional[int]:
    """
    Estrae l'ID utente dal contesto in modo sicuro.
    
    Args:
        kwargs: Keyword arguments contenenti possibilmente 'user'
    
    Returns:
        ID utente o None se non trovato
    """
    try:
        user = kwargs.get('user', {})
        return user.get('id') if isinstance(user, dict) else None
    except Exception:
        return None


def _safe_datetime_to_iso(dt: Optional[datetime]) -> Optional[str]:
    """
    Converte datetime in stringa ISO in modo sicuro.
    
    Args:
        dt: Datetime da convertire
    
    Returns:
        Stringa ISO o None se dt è None
    """
    try:
        if dt is None:
            return None
        if isinstance(dt, (datetime, date)):
            return dt.isoformat()
        return str(dt)
    except Exception:
        return None


# ==================== CUSTOMER EXTRACTORS ====================

def extract_customer_created_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per evento CUSTOMER_CREATED.
    
    Args:
        result: Tupla (Customer, bool) dal service
        kwargs: Contiene 'user' per tenant
    
    Returns:
        Dictionary con dati completi del customer o None in caso di errore
    
    Example:
        {
            "id_customer": 123,
            "email": "customer@example.com",
            "firstname": "Mario",
            "lastname": "Rossi",
            "company": "ACME Corp",
            "is_new": True,
            "tenant": "default",
            "created_by": 1
        }
    """
    try:
        if not result or not isinstance(result, tuple):
            return None
        
        customer, is_created = result
        if not customer:
            return None
        
        return {
            # IDs e riferimenti
            "id_customer": getattr(customer, 'id_customer', None),
            "id_origin": getattr(customer, 'id_origin', None),
            
            # Dati anagrafici
            "email": getattr(customer, 'email', None),
            "firstname": getattr(customer, 'firstname', None),
            "lastname": getattr(customer, 'lastname', None),
            "company": getattr(customer, 'company', None),
            
            # Dati di contesto
            "is_new": is_created,
            "date_add": _safe_datetime_to_iso(getattr(customer, 'date_add', None)),
            
            # Metadata
            "tenant": _safe_get_tenant(kwargs),
            "created_by": _safe_get_user_id(kwargs)
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati customer created: {e}", exc_info=True)
        return None


def extract_customer_updated_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per evento CUSTOMER_UPDATED.
    
    Args:
        result: Customer aggiornato dal service
        kwargs: Contiene 'customer_id' e 'user'
    
    Returns:
        Dictionary con dati completi del customer aggiornato
    """
    try:
        customer = result
        if not customer:
            return None
        
        return {
            "id_customer": getattr(customer, 'id_customer', None) or kwargs.get('customer_id'),
            "email": getattr(customer, 'email', None),
            "firstname": getattr(customer, 'firstname', None),
            "lastname": getattr(customer, 'lastname', None),
            "company": getattr(customer, 'company', None),
            "tenant": _safe_get_tenant(kwargs),
            "updated_by": _safe_get_user_id(kwargs)
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati customer updated: {e}", exc_info=True)
        return None


def extract_customer_deleted_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati per evento CUSTOMER_DELETED.
    
    Args:
        kwargs: Contiene 'customer_id' e 'user'
    
    Returns:
        Dictionary con ID customer e contesto
    """
    try:
        return {
            "id_customer": kwargs.get('customer_id'),
            "tenant": _safe_get_tenant(kwargs),
            "deleted_by": _safe_get_user_id(kwargs)
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati customer deleted: {e}", exc_info=True)
        return None


# ==================== PRODUCT EXTRACTORS ====================

def extract_product_created_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per evento PRODUCT_CREATED.
    
    Args:
        result: Product creato dal service
        kwargs: Contiene 'user'
    
    Returns:
        Dictionary con dati completi del prodotto
    """
    try:
        product = result
        if not product:
            return None
        
        return {
            "id_product": getattr(product, 'id_product', None),
            "id_platform": getattr(product, 'id_platform', None),
            "id_origin": getattr(product, 'id_origin', None),
            "name": getattr(product, 'name', None),
            "reference": getattr(product, 'reference', None),
            "ean13": getattr(product, 'ean13', None),
            "price_without_tax": float(getattr(product, 'price_without_tax', 0) or 0),
            "weight": float(getattr(product, 'weight', 0) or 0),
            "active": getattr(product, 'active', True),
            "tenant": _safe_get_tenant(kwargs),
            "created_by": _safe_get_user_id(kwargs)
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati product created: {e}", exc_info=True)
        return None


def extract_product_updated_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per evento PRODUCT_UPDATED.
    
    Args:
        result: Product aggiornato
        kwargs: Contiene 'product_id' e 'user'
    
    Returns:
        Dictionary con dati del prodotto aggiornato
    """
    try:
        product = result
        if not product:
            return None
        
        return {
            "id_product": getattr(product, 'id_product', None) or kwargs.get('product_id'),
            "name": getattr(product, 'name', None),
            "reference": getattr(product, 'reference', None),
            "price_without_tax": float(getattr(product, 'price_without_tax', 0) or 0),
            "active": getattr(product, 'active', True),
            "tenant": _safe_get_tenant(kwargs),
            "updated_by": _safe_get_user_id(kwargs)
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati product updated: {e}", exc_info=True)
        return None


def extract_product_deleted_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati per evento PRODUCT_DELETED.
    
    Args:
        kwargs: Contiene 'product_id' e 'user'
    
    Returns:
        Dictionary con ID prodotto e contesto
    """
    try:
        return {
            "id_product": kwargs.get('product_id'),
            "tenant": _safe_get_tenant(kwargs),
            "deleted_by": _safe_get_user_id(kwargs)
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati product deleted: {e}", exc_info=True)
        return None


# ==================== ORDER EXTRACTORS ====================

def extract_order_created_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per evento ORDER_CREATED.
    
    Args:
        result: Order creato
        kwargs: Contiene 'user'
    
    Returns:
        Dictionary con dati completi dell'ordine
    """
    try:
        order = result
        if not order:
            return None
        
        return {
            "id_order": getattr(order, 'id_order', None),
            "id_platform": getattr(order, 'id_platform', None),
            "id_origin": getattr(order, 'id_origin', None),
            "id_address_delivery": getattr(order, 'id_address_delivery', None),
            "id_address_invoice": getattr(order, 'id_address_invoice', None),
            "id_payment": getattr(order, 'id_payment', None),
            "id_customer": getattr(order, 'id_customer', None),
            "reference": getattr(order, 'reference', None),
            "total_paid": float(getattr(order, 'total_paid', 0) or 0),
            "id_order_state": getattr(order, 'id_order_state', None),
            "is_invoice_requested": getattr(order, 'is_invoice_requested', False),
            "is_payed": getattr(order, 'is_payed', False),
            "payment_date": _safe_datetime_to_iso(getattr(order, 'payment_date', None)),
            "total_weight": float(getattr(order, 'total_weight', 0) or 0),
            "total_price_tax_excl": float(getattr(order, 'total_price_tax_excl', 0) or 0),
            "total_discounts": float(getattr(order, 'total_discounts', 0) or 0),
            "cash_on_delivery": float(getattr(order, 'cash_on_delivery', 0) or 0),
            "tenant": _safe_get_tenant(kwargs),
            "created_by": _safe_get_user_id(kwargs)
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati order created: {e}", exc_info=True)
        return None


def extract_order_updated_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati per evento ORDER_UPDATED.
    
    Args:
        result: Order aggiornato
        kwargs: Contiene 'order_id' e 'user'
    
    Returns:
        Dictionary con dati ordine aggiornato
    """
    try:
        order = result
        if not order:
            return None
        
        return {
            "id_order": getattr(order, 'id_order', None) or kwargs.get('order_id'),
            "id_order_state": getattr(order, 'id_order_state', None),
            "total_paid": float(getattr(order, 'total_paid', 0) or 0),
            "tenant": _safe_get_tenant(kwargs),
            "updated_by": _safe_get_user_id(kwargs)
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati order updated: {e}", exc_info=True)
        return None


def extract_order_deleted_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati per evento ORDER_DELETED.
    
    Args:
        kwargs: Contiene 'order_id' e 'user'
    
    Returns:
        Dictionary con ID ordine e contesto
    """
    try:
        return {
            "id_order": kwargs.get('order_id'),
            "tenant": _safe_get_tenant(kwargs),
            "deleted_by": _safe_get_user_id(kwargs)
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati order deleted: {e}", exc_info=True)
        return None


# ==================== DOCUMENT EXTRACTORS (OrderDocument + FiscalDocument unificati) ====================

def extract_document_created_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per evento DOCUMENT_CREATED.
    Gestisce sia OrderDocument (preventivo, ddt) che FiscalDocument (invoice, credit_note).
    
    Args:
        result: Documento creato (OrderDocument, FiscalDocument, o schema)
        kwargs: Contiene 'user' e opzionalmente 'document_source'
    
    Returns:
        Dictionary con dati completi del documento
        
    Example:
        {
            "id_document": 123,
            "document_number": "PRV-2024-001",
            "document_source": "order_document",  # o "fiscal_document"
            "document_type": "preventivo",  # o "invoice", "credit_note", "ddt"
            "id_customer": 456,
            "total_amount": 1250.50,
            "tenant": "default",
            "created_by": 1
        }
    """
    try:
        document = result
        if not document:
            return None
        
        # Gestisce sia oggetti che dict o schema
        if hasattr(document, 'model_dump'):
            data = document.model_dump()
        elif isinstance(document, dict):
            data = document
        else:
            # Oggetto model SQLAlchemy
            data = {}
            
        # Determina source e type del documento
        document_source = kwargs.get('document_source', 'order_document')
        
        if document_source == 'order_document' or hasattr(document, 'type_document'):
            # OrderDocument (preventivo, ddt)
            return {
                "id_document": data.get('id_order_document') or getattr(document, 'id_order_document', None),
                "document_number": data.get('document_number') or getattr(document, 'document_number', None),
                "document_source": "order_document",
                "document_type": data.get('type_document') or getattr(document, 'type_document', None),
                "id_customer": data.get('id_customer') or getattr(document, 'id_customer', None),
                "customer_name": data.get('customer_name'),
                "email": data.get('email'),
                "phone": data.get('phone'),
                "total_amount": data.get('total_price_with_tax') or float(getattr(document, 'total_price_with_tax', 0) or 0),
                "total_weight": data.get('total_weight') or float(getattr(document, 'total_weight', 0) or 0),
                "articoli_count": len(data.get('articoli', [])) if 'articoli' in data else None,
                "tenant": _safe_get_tenant(kwargs),
                "created_by": _safe_get_user_id(kwargs)
            }
        else:
            # FiscalDocument (invoice, credit_note)
            return {
                "id_document": data.get('id_fiscal_document') or getattr(document, 'id_fiscal_document', None),
                "document_number": data.get('document_number') or getattr(document, 'document_number', None),
                "document_source": "fiscal_document",
                "document_type": data.get('document_type') or getattr(document, 'document_type', None),
                "id_order": data.get('id_order') or getattr(document, 'id_order', None),
                "total_amount": float(data.get('total_amount', 0) or getattr(document, 'total_amount', 0) or 0),
                "is_electronic": data.get('is_electronic') or getattr(document, 'is_electronic', False),
                "status": data.get('status') or getattr(document, 'status', None),
                "tenant": _safe_get_tenant(kwargs),
                "created_by": _safe_get_user_id(kwargs)
            }
    except Exception as e:
        logger.error(f"Errore estrazione dati document created: {e}", exc_info=True)
        return None


def extract_document_updated_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati per evento DOCUMENT_UPDATED.
    
    Args:
        result: Documento aggiornato
        kwargs: Contiene 'id_order_document' o 'id_fiscal_document', 'document_source' e 'user'
    
    Returns:
        Dictionary con dati documento aggiornato
    """
    try:
        document_source = kwargs.get('document_source', 'order_document')
        
        if document_source == 'order_document':
            return {
                "id_document": kwargs.get('id_order_document'),
                "document_source": "order_document",
                "tenant": _safe_get_tenant(kwargs),
                "updated_by": _safe_get_user_id(kwargs)
            }
        else:
            return {
                "id_document": kwargs.get('id_fiscal_document'),
                "document_source": "fiscal_document",
                "tenant": _safe_get_tenant(kwargs),
                "updated_by": _safe_get_user_id(kwargs)
            }
    except Exception as e:
        logger.error(f"Errore estrazione dati document updated: {e}", exc_info=True)
        return None


def extract_document_deleted_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati per evento DOCUMENT_DELETED.
    
    Args:
        kwargs: Contiene 'id_order_document' o 'id_fiscal_document', 'document_source' e 'user'
    
    Returns:
        Dictionary con ID documento e contesto
    """
    try:
        document_source = kwargs.get('document_source', 'order_document')
        
        if document_source == 'order_document':
            return {
                "id_document": kwargs.get('id_order_document'),
                "document_source": "order_document",
                "tenant": _safe_get_tenant(kwargs),
                "deleted_by": _safe_get_user_id(kwargs)
            }
        else:
            return {
                "id_document": kwargs.get('id_fiscal_document'),
                "document_source": "fiscal_document",
                "tenant": _safe_get_tenant(kwargs),
                "deleted_by": _safe_get_user_id(kwargs)
            }
    except Exception as e:
        logger.error(f"Errore estrazione dati document deleted: {e}", exc_info=True)
        return None


def extract_document_converted_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati per evento DOCUMENT_CONVERTED (preventivo -> order).
    
    Args:
        result: Dict con 'id_order' dalla conversione
        kwargs: Contiene 'id_order_document' e 'user'
    
    Returns:
        Dictionary con dati conversione
    """
    try:
        if isinstance(result, dict):
            id_order = result.get('id_order')
        else:
            id_order = None
        
        return {
            "id_document": kwargs.get('id_order_document'),
            "id_order": id_order,
            "document_source": "order_document",
            "document_type": "preventivo",
            "tenant": _safe_get_tenant(kwargs),
            "converted_by": _safe_get_user_id(kwargs)
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati document converted: {e}", exc_info=True)
        return None


def extract_document_bulk_deleted_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati per evento DOCUMENT_BULK_DELETED.
    
    Args:
        result: Response con successful e failed
        kwargs: Contiene 'ids', 'document_source' e 'user'
    
    Returns:
        Dictionary con array di IDs e risultati
    """
    try:
        if hasattr(result, 'model_dump'):
            data = result.model_dump()
        elif isinstance(result, dict):
            data = result
        else:
            data = {}
        
        document_source = kwargs.get('document_source', 'order_document')
        
        return {
            "ids_requested": kwargs.get('ids', []),
            "ids_successful": data.get('successful', []),
            "ids_failed": [err.get('id_order_document') or err.get('id_fiscal_document') for err in data.get('failed', [])],
            "total_requested": len(kwargs.get('ids', [])),
            "total_successful": data.get('summary', {}).get('successful_count', 0),
            "total_failed": data.get('summary', {}).get('failed_count', 0),
            "document_source": document_source,
            "tenant": _safe_get_tenant(kwargs),
            "deleted_by": _safe_get_user_id(kwargs)
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati document bulk deleted: {e}", exc_info=True)
        return None


# ==================== WRAPPER PER COMPATIBILITÀ ====================
# Wrapper che usano gli estrattori unificati DOCUMENT_*

def extract_preventivo_created_data(*args, result=None, **kwargs):
    """Wrapper per extract_document_created_data con document_source='order_document'"""
    kwargs['document_source'] = 'order_document'
    return extract_document_created_data(*args, result=result, **kwargs)


def extract_preventivo_updated_data(*args, result=None, **kwargs):
    """Wrapper per extract_document_updated_data con document_source='order_document'"""
    kwargs['document_source'] = 'order_document'
    return extract_document_updated_data(*args, result=result, **kwargs)


def extract_preventivo_deleted_data(*args, result=None, **kwargs):
    """Wrapper per extract_document_deleted_data con document_source='order_document'"""
    kwargs['document_source'] = 'order_document'
    return extract_document_deleted_data(*args, result=result, **kwargs)


def extract_preventivo_converted_data(*args, result=None, **kwargs):
    """Wrapper per extract_document_converted_data"""
    return extract_document_converted_data(*args, result=result, **kwargs)


def extract_bulk_preventivo_deleted_data(*args, result=None, **kwargs):
    """Wrapper per extract_document_bulk_deleted_data con document_source='order_document'"""
    kwargs['document_source'] = 'order_document'
    return extract_document_bulk_deleted_data(*args, result=result, **kwargs)


def extract_ddt_created_data(*args, result=None, **kwargs):
    """Wrapper per extract_document_created_data per DDT"""
    kwargs['document_source'] = 'order_document'
    return extract_document_created_data(*args, result=result, **kwargs)


def extract_ddt_updated_data(*args, result=None, **kwargs):
    """Wrapper per extract_document_updated_data per DDT"""
    kwargs['document_source'] = 'order_document'
    return extract_document_updated_data(*args, result=result, **kwargs)


def extract_ddt_deleted_data(*args, result=None, **kwargs):
    """Wrapper per extract_document_deleted_data per DDT"""
    kwargs['document_source'] = 'order_document'
    return extract_document_deleted_data(*args, result=result, **kwargs)


def extract_invoice_created_data(*args, result=None, **kwargs):
    """Wrapper per extract_document_created_data per Invoice"""
    kwargs['document_source'] = 'fiscal_document'
    return extract_document_created_data(*args, result=result, **kwargs)


def extract_credit_note_created_data(*args, result=None, **kwargs):
    """Wrapper per extract_document_created_data per Credit Note"""
    kwargs['document_source'] = 'fiscal_document'
    return extract_document_created_data(*args, result=result, **kwargs)


# ==================== ADDRESS EXTRACTORS ====================

def extract_address_created_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati per evento ADDRESS_CREATED.
    
    Args:
        result: Address creato
        kwargs: Contiene 'user'
    
    Returns:
        Dictionary con dati indirizzo creato
    """
    try:
        address = result
        if not address:
            return None
        
        return {
            "id_address": getattr(address, 'id_address', None),
            "id_platform": getattr(address, 'id_platform', None),
            "id_origin": getattr(address, 'id_origin', None),
            "id_customer": getattr(address, 'id_customer', None),
            "id_country": getattr(address, 'id_country', None),
            "company": getattr(address, 'company', None),
            "firstname": getattr(address, 'firstname', None),
            "lastname": getattr(address, 'lastname', None),
            "address1": getattr(address, 'address1', None),
            "state": getattr(address, 'state', None),
            "phone": getattr(address, 'phone', None),
            "city": getattr(address, 'city', None),
            "postcode": getattr(address, 'postcode', None),
            "tenant": _safe_get_tenant(kwargs),
            "created_by": _safe_get_user_id(kwargs)
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati address created: {e}", exc_info=True)
        return None
