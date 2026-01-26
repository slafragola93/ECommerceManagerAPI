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
            "id_store": product.id_store,
            "name": product.name,
            "sku": product.sku,
            "reference": product.reference,
            "type": product.type,
            "price": float(product.price or 0),  # Campo price (rinominato da price_without_tax)
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
            "id_store": product.id_store,
            "name": product.name,
            "sku": product.sku,
            "reference": product.reference,
            "type": product.type,
            "price": float(product.price or 0),  # Campo price (rinominato da price_without_tax)
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
        result: DDTGenerateResponseSchema o OrderDocument creato dal service
        kwargs: Contiene 'user' per contesto
    
    Returns:
        Dictionary con dati completi del DDT
    """
    try:
        if not result:
            return None
        
        # Gestisce DDTGenerateResponseSchema (risultato del metodo generate_ddt_from_order)
        if hasattr(result, 'ddt') and hasattr(result, 'success'):
            # Se success=False o ddt è None, non emettere evento
            if not result.success or not result.ddt:
                return None
            document = result.ddt
        else:
            # Gestisce OrderDocument diretto
            document = result
        
        # Estrae id_customer dal documento o dal customer nested
        id_customer = None
        if hasattr(document, 'id_customer'):
            id_customer = document.id_customer
        elif hasattr(document, 'customer') and document.customer:
            id_customer = document.customer.get('id_customer') if isinstance(document.customer, dict) else getattr(document.customer, 'id_customer', None)
        
        return {
            "id_order_document": document.id_order_document,
            "document_type": "ddt",
            "document_source": "order_document",
            "number": getattr(document, 'document_number', None),
            "id_customer": id_customer,
            "total": float(getattr(document, 'total_price_with_tax', 0) or 0),
            "created_by": kwargs.get('user', {}).get('id')
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati ddt created: {e}")
        return None


def extract_ddt_updated_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per evento DOCUMENT_UPDATED (ddt).
    
    Args:
        result: DDTDetailSchema aggiornato dal service
        args: Contiene id_order_detail come primo argomento
        kwargs: Contiene 'user' per contesto
    
    Returns:
        Dictionary con dati completi del DDT
    """
    try:
        if not result:
            return None
        
        # Recupera id_order_detail dagli argomenti
        id_order_detail = args[0] if args else None
        if not id_order_detail:
            return None
        
        # Recupera id_order_document dal database
        from src.database import get_db
        from sqlalchemy import text
        
        db = next(get_db())
        
        try:
            stmt = text("""
                SELECT id_order_document 
                FROM order_details 
                WHERE id_order_detail = :id_order_detail
            """)
            result_query = db.execute(stmt, {"id_order_detail": id_order_detail})
            row = result_query.fetchone()
            
            if not row:
                return None
            
            id_order_document = row[0]
            
            # Recupera dati DDT
            stmt_ddt = text("""
                SELECT id_order_document, document_number, id_customer, total_price_with_tax
                FROM orders_document
                WHERE id_order_document = :id_order_document
            """)
            result_ddt = db.execute(stmt_ddt, {"id_order_document": id_order_document})
            ddt_row = result_ddt.fetchone()
            
            if not ddt_row:
                return None
            
            return {
                "id_order_document": ddt_row[0],
                "document_type": "ddt",
                "document_source": "order_document",
                "number": ddt_row[1],
                "id_customer": ddt_row[2],
                "total": float(ddt_row[3] or 0),
                "updated_by": kwargs.get('user', {}).get('id')
            }
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Errore estrazione dati ddt updated: {e}")
        return None


def extract_ddt_deleted_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per evento DOCUMENT_DELETED (ddt).
    
    Args:
        result: bool (True se eliminato con successo)
        args: Contiene id_order_detail come primo argomento
        kwargs: Contiene 'user' per contesto
    
    Returns:
        Dictionary con dati del DDT eliminato
    """
    try:
        # result è un bool, quindi recuperiamo id_order_detail da args
        id_order_detail = args[0] if args else None
        if not id_order_detail:
            return None
        
        # Recupera id_order_document dal database (il dettaglio potrebbe essere già eliminato)
        from src.database import get_db
        from sqlalchemy import text
        
        db = next(get_db())
        
        try:
            # Prova a recuperare id_order_document dal dettaglio (potrebbe essere già eliminato)
            stmt = text("""
                SELECT id_order_document 
                FROM order_details 
                WHERE id_order_detail = :id_order_detail
            """)
            result_query = db.execute(stmt, {"id_order_detail": id_order_detail})
            row = result_query.fetchone()
            
            id_order_document = row[0] if row else None
            
            # Se il dettaglio è già stato eliminato, non possiamo recuperare id_order_document
            # In questo caso, restituiamo solo id_order_detail
            if not id_order_document:
                return {
                    "id_order_detail": id_order_detail,
                    "document_type": "ddt",
                    "document_source": "order_document",
                    "deleted_by": kwargs.get('user', {}).get('id')
                }
            
            # Recupera dati DDT
            stmt_ddt = text("""
                SELECT id_order_document, document_number, id_customer
                FROM orders_document
                WHERE id_order_document = :id_order_document
            """)
            result_ddt = db.execute(stmt_ddt, {"id_order_document": id_order_document})
            ddt_row = result_ddt.fetchone()
            
            if not ddt_row:
                return {
                    "id_order_detail": id_order_detail,
                    "id_order_document": id_order_document,
                    "document_type": "ddt",
                    "document_source": "order_document",
                    "deleted_by": kwargs.get('user', {}).get('id')
                }
            
            return {
                "id_order_document": ddt_row[0],
                "document_type": "ddt",
                "document_source": "order_document",
                "number": ddt_row[1],
                "id_customer": ddt_row[2],
                "deleted_by": kwargs.get('user', {}).get('id')
            }
        finally:
            db.close()
            
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
        result: OrderDocument aggiornato dal service, dict o PreventivoDetailResponseSchema
        kwargs: Contiene 'user' per contesto
    
    Returns:
        Dictionary con dati completi del preventivo
    """
    try:
        if not result:
            return None
        
        # Gestisce dict (PreventivoDetailResponseSchema serializzato)
        if isinstance(result, dict):
            return {
                "id_order_document": result.get('id_order_document'),
                "document_type": "preventivo",
                "document_source": "order_document",
                "number": result.get('document_number'),
                "id_customer": result.get('customer', {}).get('id_customer') if isinstance(result.get('customer'), dict) else None,
                "total": float(result.get('total_finale', result.get('total_price_with_tax', 0)) or 0),
                "updated_by": kwargs.get('user', {}).get('id')
            }
        
        # Gestisce PreventivoDetailResponseSchema (oggetto Pydantic)
        if hasattr(result, 'customer') and hasattr(result, 'id_order_document'):
            customer_id = None
            if result.customer:
                # customer può essere un oggetto CustomerResponseSchema o None
                if hasattr(result.customer, 'id_customer'):
                    customer_id = result.customer.id_customer
                elif isinstance(result.customer, dict):
                    customer_id = result.customer.get('id_customer')
            
            return {
                "id_order_document": result.id_order_document,
                "document_type": "preventivo",
                "document_source": "order_document",
                "number": getattr(result, 'document_number', None),
                "id_customer": customer_id,
                "total": float(getattr(result, 'total_finale', getattr(result, 'total_price_with_tax', 0)) or 0),
                "updated_by": kwargs.get('user', {}).get('id')
            }
        
        # Gestisce OrderDocument (oggetto SQLAlchemy)
        if hasattr(result, 'id_order_document') and hasattr(result, 'id_customer'):
            document = result
            return {
                "id_order_document": document.id_order_document,
                "document_type": "preventivo",
                "document_source": "order_document",
                "number": getattr(document, 'number', None),
                "id_customer": document.id_customer,
                "total": float(getattr(document, 'total_price_with_tax', getattr(document, 'total', 0)) or 0),
                "updated_by": kwargs.get('user', {}).get('id')
            }
        
        # Fallback: cerca di estrarre i dati in modo generico
        return {
            "id_order_document": getattr(result, 'id_order_document', None),
            "document_type": "preventivo",
            "document_source": "order_document",
            "number": getattr(result, 'document_number', getattr(result, 'number', None)),
            "id_customer": getattr(result, 'id_customer', None),
            "total": 0.0,
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


def extract_order_created_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per ORDER_CREATED.
    
    Include order_details per plugin stock e altri futuri plugin.
    Query ottimizzata per performance - solo campi necessari.
    
    Args:
        result: Order dal service
        kwargs: user context
    
    Returns:
        Dict con dati ordine + details
    """
    try:
        if not result:
            return None
        
        order = result
        
        # Query SQL ottimizzata: SOLO campi necessari da order_details
        from src.database import get_db
        from sqlalchemy import text
        
        db = next(get_db())
        
        try:
            stmt = text("""
                SELECT id_order_detail, id_product, product_name, 
                       product_qty, unit_price_net, unit_price_with_tax,
                       total_price_net, total_price_with_tax, id_tax
                FROM order_details 
                WHERE id_order = :id_order
            """)
            result_details = db.execute(stmt, {"id_order": order.id_order})
            order_details_data = [
                {
                    'id_order_detail': row.id_order_detail,
                    'id_product': row.id_product,
                    'product_name': row.product_name,
                    'product_qty': row.product_qty,
                    'unit_price_net': float(row.unit_price_net or 0),
                    'unit_price_with_tax': float(row.unit_price_with_tax or 0),
                    'total_price_net': float(row.total_price_net or 0),
                    'total_price_with_tax': float(row.total_price_with_tax or 0),
                    'id_tax': row.id_tax
                }
                for row in result_details
            ]
        finally:
            db.close()
        
        return {
            "id_order": order.id_order,
            "id_origin": order.id_origin,
            "id_customer": order.id_customer,
            "id_address_delivery": order.id_address_delivery    ,
            "id_address_invoice": order.id_address_invoice,
            "id_payment": order.id_payment,
            "id_carrier": order.id_carrier,
            "id_order_state": order.id_order_state,
            "ecommerce_reference": order.reference,
            "total_price_with_tax": order.total_price_with_tax,  # ex total_with_tax, ex total_paid
            "total_weight": order.total_weight,
            "order_details": order_details_data,
            "created_by": kwargs.get('user', {}).get('id')
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati order created: {e}")
        return None


def extract_shipping_status_changed_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per evento SHIPPING_STATUS_CHANGED.
    
    Query ottimizzata per recuperare solo id_order e id_store necessari.
    
    Args:
        result: Shipping aggiornato o dict con old_state_id, new_state_id, id_shipping
        kwargs: Contiene 'user' per contesto
    
    Returns:
        Dict con id_shipping, id_order, old_state_id, new_state_id, id_store
    """
    try:
        if not result:
            return None
        
        # Gestisce sia Shipping object che dict
        if isinstance(result, dict):
            id_shipping = result.get("id_shipping")
            old_state_id = result.get("old_state_id")
            new_state_id = result.get("new_state_id")
        else:
            # Shipping object
            shipping = result
            id_shipping = shipping.id_shipping
            old_state_id = kwargs.get("old_state_id")
            new_state_id = shipping.id_shipping_state
        
        if not id_shipping or not old_state_id or not new_state_id:
            return None
        
        # Query SQL ottimizzata: SOLO id_order e id_store
        from src.database import get_db
        from sqlalchemy import text
        
        db = next(get_db())
        
        try:
            stmt = text("""
                SELECT o.id_order, o.id_store
                FROM orders o
                WHERE o.id_shipping = :id_shipping
                LIMIT 1
            """)
            result_order = db.execute(stmt, {"id_shipping": id_shipping}).first()
            
            if not result_order:
                logger.warning(f"Nessun ordine trovato per shipping {id_shipping}")
                return None
            
            id_order = result_order.id_order
            id_store = result_order.id_store
        finally:
            db.close()
        
        return {
            "id_shipping": id_shipping,
            "id_order": id_order,
            "old_state_id": old_state_id,
            "new_state_id": new_state_id,
            "id_store": id_store,
            "updated_by": kwargs.get('user', {}).get('id')
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati shipping status changed: {e}")
        return None


def extract_shipping_status_from_order_update(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati per SHIPPING_STATUS_CHANGED quando shipping viene modificato tramite order update.
    
    Verifica se id_shipping è presente nell'order update e se lo shipping ha cambiato stato.
    
    Args:
        result: Dict da update_order con order_id
        kwargs: Contiene order_schema, old_shipping_state
    
    Returns:
        Dict per evento SHIPPING_STATUS_CHANGED o None se non applicabile
    """
    try:
        if not isinstance(result, dict):
            return None
        
        order_id = result.get("order_id")
        if not order_id:
            return None
        
        # Verifica se shipping è stato modificato
        order_schema = kwargs.get("order_schema")
        if not order_schema or not hasattr(order_schema, 'id_shipping'):
            return None
        
        id_shipping = getattr(order_schema, 'id_shipping', None)
        if not id_shipping:
            return None
        
        # Recupera shipping e verifica cambio stato
        from src.database import get_db
        from sqlalchemy import text
        
        db = next(get_db())
        
        try:
            # Recupera shipping con stato attuale
            stmt = text("""
                SELECT s.id_shipping_state, o.id_order, o.id_store
                FROM shipments s
                INNER JOIN orders o ON o.id_shipping = s.id_shipping
                WHERE s.id_shipping = :id_shipping AND o.id_order = :order_id
                LIMIT 1
            """)
            result_shipping = db.execute(stmt, {"id_shipping": id_shipping, "order_id": order_id}).first()
            
            if not result_shipping:
                return None
            
            new_state_id = result_shipping.id_shipping_state
            old_state_id = kwargs.get("old_shipping_state_id")
            
            # Se stato non è cambiato, non emettere evento
            if not old_state_id or old_state_id == new_state_id:
                return None
            
            return {
                "id_shipping": id_shipping,
                "id_order": result_shipping.id_order,
                "old_state_id": old_state_id,
                "new_state_id": new_state_id,
                "updated_by": kwargs.get('user', {}).get('id')
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Errore estrazione dati shipping status from order update: {e}")
        return None


def extract_order_deleted_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per evento ORDER_DELETED.
    
    Args:
        result: Order eliminato o order_id (int)
        kwargs: Contiene 'user' per contesto
    
    Returns:
        Dictionary con dati dell'ordine eliminato
    """
    try:
        order_id = None
        order_data = {}
        
        if result:
            if isinstance(result, int):
                order_id = result
            elif hasattr(result, 'id_order'):
                order_id = result.id_order
                # Estrai dati rilevanti dall'ordine prima dell'eliminazione
                order_data = {
                    "id_origin": getattr(result, 'id_origin', None),
                    "id_customer": getattr(result, 'id_customer', None),
                    "id_order_state": getattr(result, 'id_order_state', None),
                    "ecommerce_reference": getattr(result, 'reference', None),
                    "internal_reference": getattr(result, 'internal_reference', None),
                    "total_price_with_tax": float(getattr(result, 'total_price_with_tax', 0) or 0),
                }
        
        if order_id is None:
            # Prova a estrarre da args o kwargs
            order_id = kwargs.get('order_id') or (args[0] if args else None)
        
        if not order_id:
            return None
        
        return {
            "id_order": order_id,
            **order_data,
            "deleted_by": kwargs.get('user', {}).get('id')
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati order deleted: {e}")
        return None