"""
Order Service per gestione logica business ordini seguendo principi SOLID
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from src.services.core.tool import format_datetime_ddmmyyyy_hhmmss
from src.services.interfaces.order_service_interface import IOrderService
from src.repository.order_repository import OrderRepository
from src.models.order_detail import OrderDetail
from src.models.order_state import OrderState
from src.models.shipping import Shipping
from src.models.tax import Tax
from src.models.relations.relations import orders_history
from src.schemas.order_schema import (
    OrderUpdateSchema,
    OrderStatusUpdateItem,
    BulkOrderStatusUpdateResponseSchema,
    OrderStatusUpdateResult,
    OrderStatusUpdateError
)
from src.events.decorators import emit_event_on_success
from src.events.core.event import EventType
from src.events.extractors import extract_order_created_data
from src.services.core.tool import calculate_order_totals, calculate_price_without_tax,calculate_amount_with_percentage
from src.repository.tax_repository import TaxRepository
from src.services.routers.order_document_service import OrderDocumentService
from src.schemas.order_detail_schema import OrderDetailCreateSchema, OrderDetailUpdateSchema
import logging

from src.models.order_document import OrderDocument

logger = logging.getLogger(__name__)


# Funzioni helper per estrazione dati eventi
def _extract_order_status_data(*args, result=None, **kwargs):
    """Estrae i dati dell'evento di cambio stato ordine con id_platform."""
    if not isinstance(result, dict) or result.get("old_state_id") is None:
        return None
    
    # Prendi order_id da result o kwargs
    order_id = result.get("order_id") or kwargs.get("order_id")
    
    # Prendi new_state_id da result (può essere "new_status_id" o "new_state_id")
    new_state_id = result.get("new_state_id") or result.get("new_status_id") or kwargs.get("new_status_id")
    
    if not order_id:
        return None
    
    # Query SQL ottimizzata: SOLO id_platform
    from src.database import get_db
    from sqlalchemy import text
    
    db = next(get_db())
    try:
        stmt = text("""
            SELECT id_platform
            FROM orders
            WHERE id_order = :order_id
            LIMIT 1
        """)
        result_order = db.execute(stmt, {"order_id": order_id}).first()
        
        if not result_order:
            return None
        
        id_platform = result_order.id_platform
    finally:
        db.close()
    
    return {
        "order_id": order_id,
        "old_state_id": result.get("old_state_id"),
        "new_state_id": new_state_id,
        "id_platform": id_platform,
    }


def _should_emit_order_status_event(*args, result=None, **kwargs):
    """Verifica se l'evento di cambio stato deve essere emesso."""
    return isinstance(result, dict) and result.get("old_state_id") is not None


def _extract_order_update_status_data(*args, result=None, **kwargs):
    """Estrae i dati dell'evento di cambio stato da update_order con id_platform."""
    if not isinstance(result, dict):
        return None
    
    old_state_id = result.get("old_state_id")
    new_state_id = result.get("new_state_id")
    order_id = result.get("order_id") or kwargs.get("order_id")
    
    if old_state_id is None or new_state_id is None or order_id is None:
        return None
    
    # Query SQL ottimizzata: SOLO id_platform
    from src.database import get_db
    from sqlalchemy import text
    
    db = next(get_db())
    try:
        stmt = text("""
            SELECT id_platform
            FROM orders
            WHERE id_order = :order_id
            LIMIT 1
        """)
        result_order = db.execute(stmt, {"order_id": order_id}).first()
        
        if not result_order:
            return None
        
        id_platform = result_order.id_platform
    finally:
        db.close()
        
    return {
        "order_id": order_id,
        "old_state_id": old_state_id,
        "new_state_id": new_state_id,
        "id_platform": id_platform,
    }


def _should_emit_order_update_status_event(*args, result=None, **kwargs):
    """Verifica se l'evento di cambio stato deve essere emesso da update_order."""
    if not isinstance(result, dict):
        return False
    
    old_state_id = result.get("old_state_id")
    new_state_id = result.get("new_state_id")
    
    return (
        old_state_id is not None 
        and new_state_id is not None 
        and old_state_id != new_state_id
    )


def _extract_bulk_order_status_data(*args, result=None, **kwargs):
    """Estrae i dati dell'evento di cambio stato da bulk update con id_platform."""
    if not isinstance(result, dict):
        return None
    
    old_state_id = result.get("old_state_id")
    new_state_id = result.get("new_state_id")
    order_id = result.get("order_id")
    
    if old_state_id is None or new_state_id is None or order_id is None:
        return None
    
    # Query SQL ottimizzata: SOLO id_platform
    from src.database import get_db
    from sqlalchemy import text
    
    db = next(get_db())
    try:
        stmt = text("""
            SELECT id_platform
            FROM orders
            WHERE id_order = :order_id
            LIMIT 1
        """)
        result_order = db.execute(stmt, {"order_id": order_id}).first()
        
        if not result_order:
            return None
        
        id_platform = result_order.id_platform
    finally:
        db.close()
        
    return {
        "order_id": order_id,
        "old_state_id": old_state_id,
        "new_state_id": new_state_id,
        "id_platform": id_platform,
    }


def _should_emit_bulk_order_status_event(*args, result=None, **kwargs):
    """Verifica se l'evento di cambio stato deve essere emesso da bulk update."""
    if not isinstance(result, dict):
        return False
    
    old_state_id = result.get("old_state_id")
    new_state_id = result.get("new_state_id")
    
    return (
        old_state_id is not None 
        and new_state_id is not None 
        and old_state_id != new_state_id
    )


@emit_event_on_success(
    event_type=EventType.ORDER_STATUS_CHANGED,
    data_extractor=_extract_bulk_order_status_data,
    condition=_should_emit_bulk_order_status_event,
    source="order_service.update_single_order_status_in_bulk",
)
async def _update_single_order_status_in_bulk(
    order_id: int,
    new_state_id: int,
    or_repo: OrderRepository
) -> Dict[str, Any]:
    """
    Helper function per aggiornare lo stato di un singolo ordine nel contesto bulk.
    Usata dal bulk update per ogni ordine.
    
    Args:
        order_id: ID dell'ordine
        new_state_id: Nuovo stato dell'ordine
        or_repo: Repository ordini
        
    Returns:
        Dict con order_id, old_state_id, new_state_id per emissione evento
        
    Raises:
        ValueError: Se l'ordine non esiste, se lo stato non esiste, o se lo stato è già impostato
    """
    order = or_repo.get_by_id(_id=order_id)
    if order is None:
        raise ValueError(f"Ordine {order_id} non trovato")
    
    # Valida che l'id_order_state esista
    order_state = or_repo.session.query(OrderState).filter(
        OrderState.id_order_state == new_state_id
    ).first()
    if not order_state:
        raise ValueError(f"Stato ordine {new_state_id} non esiste nella tabella order_states")
    
    old_state_id = order.id_order_state
    if old_state_id == new_state_id:
        raise ValueError(f"Ordine {order_id} è già nello stato {new_state_id}")
    
    # Aggiornare stato
    order.id_order_state = new_state_id
    or_repo.session.add(order)
    
    # Creare record in orders_history
    order_history_insert = orders_history.insert().values(
        id_order=order_id,
        id_order_state=new_state_id,
        date_add=datetime.now()
    )
    or_repo.session.execute(order_history_insert)
    
    # Commit per questo ordine
    or_repo.session.commit()
    
    # Return result con dati per emissione evento
    return {
        "order_id": order_id,
        "old_state_id": old_state_id,
        "new_state_id": new_state_id,
    }


class OrderService(IOrderService):
    """Order Service per gestione logica business ordini"""
    
    def __init__(self, order_repository: OrderRepository):
        self._order_repository = order_repository
    
    @emit_event_on_success(
        event_type=EventType.ORDER_CREATED,
        data_extractor=extract_order_created_data,
        source="order_service.create_order"
    )
    async def create_order(self, order_data, user: dict = None):
        """
        Crea un nuovo ordine ed emette evento ORDER_CREATED.
        
        Args:
            order_data: OrderSchema con dati ordine
            user: Contesto utente per eventi
            
        Returns:
            Order creato
        """
        # Delega al repository per creazione (restituisce id_order)
        order_id = self._order_repository.create(order_data)
        
        # Ricalcola totali
        self.recalculate_totals_for_order(order_id)
        
        # Recupera l'ordine completo per return ed evento
        order = self._order_repository.get_by_id(order_id)
        
        return order

    def recalculate_totals_for_order(self, order_id: int) -> None:
        """Ricalcola e salva peso, imponibile e totale ivato dell'ordine."""
        order = self._order_repository.get_by_id(_id=order_id)
        if not order:
            return

        session = self._order_repository.session

        order_details: List[OrderDetail] = session.query(OrderDetail).filter(
            OrderDetail.id_order == order_id
        ).all()

        if not order_details:
            order.total_weight = 0.0
            order.total_price_with_tax = 0.0
            order.total_price_net = 0.0
            order.products_total_price_net = 0.0
            order.products_total_price_with_tax = 0.0

            shipping: Optional[Shipping] = None
            if order.id_shipping:
                shipping = session.query(Shipping).filter(Shipping.id_shipping == order.id_shipping).first()
            if shipping:
                shipping.weight = 0.0

            # Aggiorna updated_at con formato DD-MM-YYYY hh:mm:ss
            order.updated_at = format_datetime_ddmmyyyy_hhmmss(datetime.now())

            session.commit()
            return

        tax_ids = {
            od.id_tax for od in order_details if getattr(od, "id_tax", None)
        }

        tax_percentages: Dict[int, float] = {}
        if tax_ids:
            taxes = session.query(Tax).filter(Tax.id_tax.in_(tax_ids)).all()
            tax_percentages = {tax.id_tax: tax.percentage for tax in taxes}

        totals = calculate_order_totals(order_details, tax_percentages)

        order.total_weight = sum(
            (float(od.product_weight) if od.product_weight is not None else 0.0) * (od.product_qty or 0) for od in order_details
        )

        shipping: Optional[Shipping] = None
        shipping_cost_incl = 0.0
        shipping_cost_excl = 0.0
        if order.id_shipping:
            shipping = session.query(Shipping).filter(Shipping.id_shipping == order.id_shipping).first()
            if shipping:
                shipping_cost_incl = float(getattr(shipping, "price_tax_incl", 0.0) or 0.0)
                shipping_cost_excl = float(getattr(shipping, "price_tax_excl", 0.0) or 0.0)

        discount = float(getattr(order, "total_discounts", 0.0) or 0.0)

        order.total_price_with_tax = totals["total_price_with_tax"] + shipping_cost_incl - discount
        
        # Calcola total_price_net sommando i total_price_net degli order_detail
        total_price_net = sum(
            float(od.total_price_net) if hasattr(od, 'total_price_net') and od.total_price_net is not None else 0.0
            for od in order_details
        )
        # Aggiungi il costo della spedizione senza IVA
        order.total_price_net = total_price_net + shipping_cost_excl - discount
        
        # Calcola products_total_price_net e products_total_price_with_tax per Order
        # Solo OrderDetail collegati direttamente all'Order (id_order_document IS NULL o = 0)
        order_details_for_products = [
            od for od in order_details 
            if od.id_order_document is None or od.id_order_document == 0
        ]
        
        order.products_total_price_net = sum(
            float(od.total_price_net) if hasattr(od, 'total_price_net') and od.total_price_net is not None else 0.0
            for od in order_details_for_products
        )
        order.products_total_price_with_tax = sum(
            float(od.total_price_with_tax) if hasattr(od, 'total_price_with_tax') and od.total_price_with_tax is not None else 0.0
            for od in order_details_for_products
        )

        # Aggiorna updated_at con formato DD-MM-YYYY hh:mm:ss
        order.updated_at = format_datetime_ddmmyyyy_hhmmss(datetime.now())

        session.commit()
    
    async def add_order_detail(self, order_id: int, order_detail_data: OrderDetailCreateSchema) -> OrderDetail:
        """
        Aggiunge un nuovo order_detail all'ordine.
        
        Calcola automaticamente unit_price_net e total_price_net da unit_price_with_tax e total_price_with_tax
        usando la percentuale IVA di id_tax. Ricalcola i totali dell'ordine e aggiorna il peso della spedizione.
        
        Args:
            order_id: ID dell'ordine
            order_detail_data: Dati del nuovo order_detail
            
        Returns:
            OrderDetail creato
        """
        # Verifica che l'ordine esista
        order = self._order_repository.get_by_id(_id=order_id)
        if not order:
            raise ValueError(f"Ordine {order_id} non trovato")
        
        session = self._order_repository.session
        
        # Recupera la percentuale IVA
        tax_repo = TaxRepository(session)
        tax_percentage = tax_repo.get_percentage_by_id(order_detail_data.id_tax)
        
        # Calcola unit_price_net da unit_price_with_tax
        unit_price_net = calculate_price_without_tax(order_detail_data.unit_price_with_tax, tax_percentage)
        
        # Calcola total_price_net_base da total_price_with_tax (assumendo che total_price_with_tax sia già il totale finale)
        total_price_net_base = calculate_price_without_tax(order_detail_data.total_price_with_tax, tax_percentage)
        
        # Applica sconti se presenti (gli sconti vengono applicati al totale netto)
        total_price_net = total_price_net_base
        if order_detail_data.reduction_percent and order_detail_data.reduction_percent > 0:
            discount = calculate_amount_with_percentage(total_price_net_base, order_detail_data.reduction_percent)
            total_price_net = total_price_net_base - discount
        elif order_detail_data.reduction_amount and order_detail_data.reduction_amount > 0:
            total_price_net = total_price_net_base - order_detail_data.reduction_amount
        
        # Ricalcola total_price_with_tax dal total_price_net finale (dopo sconti)
        from src.services.core.tool import calculate_price_with_tax
        total_price_with_tax = calculate_price_with_tax(total_price_net, tax_percentage, quantity=1)
        
        # Crea l'order_detail
        order_detail = OrderDetail(
            id_order=order_id,
            id_order_document=0,
            id_origin=0,
            id_tax=order_detail_data.id_tax,
            id_product=order_detail_data.id_product,
            product_name=order_detail_data.product_name,
            product_reference=order_detail_data.product_reference or "",
            product_qty=order_detail_data.product_qty,
            unit_price_net=unit_price_net,
            unit_price_with_tax=order_detail_data.unit_price_with_tax,
            total_price_net=total_price_net,
            total_price_with_tax=total_price_with_tax,
            product_weight=order_detail_data.product_weight,
            reduction_percent=order_detail_data.reduction_percent or 0.0,
            reduction_amount=order_detail_data.reduction_amount or 0.0,
            rda=order_detail_data.rda,
            rda_quantity=order_detail_data.rda_quantity,
            note=order_detail_data.note
        )
        
        session.add(order_detail)
        session.commit()
        session.refresh(order_detail)
        
        # Ricalcola i totali dell'ordine
        self.recalculate_totals_for_order(order_id)
        
        # Aggiorna il peso della spedizione
        order_doc_service = OrderDocumentService(session)
        order_doc_service.update_shipping_weight_from_articles(id_order=order_id, check_order_state=True)
        
        return order_detail
    
    async def update_order_detail(
        self, 
        order_id: int, 
        order_detail_id: int, 
        order_detail_data: OrderDetailUpdateSchema
    ) -> OrderDetail:
        """
        Aggiorna un order_detail esistente con aggiornamenti parziali.
        
        Ricalcola i totali dell'ordine se vengono modificati campi tracciati:
        id_tax, product_qty, product_weight, unit_price_net, unit_price_with_tax,
        reduction_percent, reduction_amount, total_price_net, total_price_with_tax.
        
        Aggiorna il peso della spedizione se viene modificato product_weight o product_qty.
        
        Args:
            order_id: ID dell'ordine
            order_detail_id: ID dell'order_detail da aggiornare
            order_detail_data: Dati aggiornati (solo campi da modificare)
            
        Returns:
            OrderDetail aggiornato
        """
        # Verifica che l'ordine esista
        order = self._order_repository.get_by_id(_id=order_id)
        if not order:
            raise ValueError(f"Ordine {order_id} non trovato")
        
        session = self._order_repository.session
        
        # Verifica che l'order_detail esista e appartenga all'ordine
        order_detail = session.query(OrderDetail).filter(
            OrderDetail.id_order_detail == order_detail_id,
            OrderDetail.id_order == order_id
        ).first()
        
        if not order_detail:
            raise ValueError(f"OrderDetail {order_detail_id} non trovato per l'ordine {order_id}")
        
        # Salva i valori precedenti per verificare se serve ricalcolare
        previous_values = {
            "id_tax": order_detail.id_tax,
            "product_qty": order_detail.product_qty,
            "product_weight": order_detail.product_weight,
            "unit_price_net": order_detail.unit_price_net,
            "unit_price_with_tax": order_detail.unit_price_with_tax,
            "reduction_percent": order_detail.reduction_percent,
            "reduction_amount": order_detail.reduction_amount,
            "total_price_net": order_detail.total_price_net,
            "total_price_with_tax": order_detail.total_price_with_tax,
        }
        
        # Prepara i dati da aggiornare (solo campi forniti)
        update_data = order_detail_data.model_dump(exclude_unset=True)
        
        # Se viene modificato id_tax, unit_price_with_tax o total_price_with_tax, 
        # calcola i prezzi netti se necessario
        if 'id_tax' in update_data or 'unit_price_with_tax' in update_data or 'total_price_with_tax' in update_data:
            # Usa id_tax aggiornato o quello esistente
            id_tax = update_data.get('id_tax') or order_detail.id_tax
            if not id_tax:
                raise ValueError("id_tax è obbligatorio per calcolare i prezzi netti")
            
            tax_repo = TaxRepository(session)
            tax_percentage = tax_repo.get_percentage_by_id(id_tax)
            
            # Se unit_price_with_tax è fornito ma unit_price_net no, calcola unit_price_net
            if 'unit_price_with_tax' in update_data and 'unit_price_net' not in update_data:
                update_data['unit_price_net'] = calculate_price_without_tax(
                    update_data['unit_price_with_tax'], 
                    tax_percentage
                )
            
            # Se total_price_with_tax è fornito ma total_price_net no, calcola total_price_net
            if 'total_price_with_tax' in update_data and 'total_price_net' not in update_data:
                update_data['total_price_net'] = calculate_price_without_tax(
                    update_data['total_price_with_tax'], 
                    tax_percentage
                )
        
        # Se vengono modificati reduction_percent o reduction_amount, ricalcola i totali
        if 'reduction_percent' in update_data or 'reduction_amount' in update_data:
            # Usa i valori aggiornati o quelli esistenti
            id_tax = update_data.get('id_tax') or order_detail.id_tax
            unit_price_net = update_data.get('unit_price_net') or order_detail.unit_price_net
            product_qty = update_data.get('product_qty') or order_detail.product_qty
            
            if not id_tax or not unit_price_net or not product_qty:
                raise ValueError("id_tax, unit_price_net e product_qty sono necessari per applicare gli sconti")
            
            # Calcola il totale base (prima degli sconti)
            total_base_net = unit_price_net * product_qty
            
            # Applica gli sconti
            reduction_percent = update_data.get('reduction_percent') or order_detail.reduction_percent or 0.0
            reduction_amount = update_data.get('reduction_amount') or order_detail.reduction_amount or 0.0
            
            if reduction_percent > 0:
                discount = calculate_amount_with_percentage(total_base_net, reduction_percent)
                total_price_net = total_base_net - discount
            elif reduction_amount > 0:
                total_price_net = total_base_net - reduction_amount
            else:
                total_price_net = total_base_net
            
            # Calcola total_price_with_tax dal total_price_net finale
            tax_repo = TaxRepository(session)
            tax_percentage = tax_repo.get_percentage_by_id(id_tax)
            from src.services.core.tool import calculate_price_with_tax
            total_price_with_tax = calculate_price_with_tax(total_price_net, tax_percentage, quantity=1)
            
            # Aggiorna i totali
            update_data['total_price_net'] = total_price_net
            update_data['total_price_with_tax'] = total_price_with_tax
        
        # Applica gli aggiornamenti
        for field_name, value in update_data.items():
            if hasattr(order_detail, field_name) and value is not None:
                setattr(order_detail, field_name, value)
        
        session.commit()
        session.refresh(order_detail)
        
        # Verifica se serve ricalcolare i totali
        tracked_fields = (
            "id_tax", "product_qty", "product_weight", "unit_price_net", 
            "unit_price_with_tax", "reduction_percent", "reduction_amount",
            "total_price_net", "total_price_with_tax"
        )
        
        needs_recalculation = any(
            field in update_data and previous_values.get(field) != getattr(order_detail, field)
            for field in tracked_fields
        )
        
        if needs_recalculation:
            self.recalculate_totals_for_order(order_id)
        
        # Aggiorna il peso della spedizione se product_weight o product_qty sono stati modificati
        if 'product_weight' in update_data or 'product_qty' in update_data:
            order_doc_service = OrderDocumentService(session)
            order_doc_service.update_shipping_weight_from_articles(id_order=order_id, check_order_state=True)
        
        return order_detail
    
    async def remove_order_detail(self, order_id: int, order_detail_id: int) -> bool:
        """
        Rimuove un order_detail dall'ordine.
        
        Ricalcola i totali dell'ordine e aggiorna il peso della spedizione dopo la rimozione.
        
        Args:
            order_id: ID dell'ordine
            order_detail_id: ID dell'order_detail da rimuovere
            
        Returns:
            True se rimosso con successo
        """
        # Verifica che l'ordine esista
        order = self._order_repository.get_by_id(_id=order_id)
        if not order:
            raise ValueError(f"Ordine {order_id} non trovato")
        
        session = self._order_repository.session
        
        # Verifica che l'order_detail esista e appartenga all'ordine
        order_detail = session.query(OrderDetail).filter(
            OrderDetail.id_order_detail == order_detail_id,
            OrderDetail.id_order == order_id
        ).first()
        
        if not order_detail:
            raise ValueError(f"OrderDetail {order_detail_id} non trovato per l'ordine {order_id}")
        
        # Elimina l'order_detail
        session.delete(order_detail)
        session.commit()
        
        # Ricalcola i totali dell'ordine
        self.recalculate_totals_for_order(order_id)
        
        # Aggiorna il peso della spedizione
        order_doc_service = OrderDocumentService(session)
        order_doc_service.update_shipping_weight_from_articles(id_order=order_id, check_order_state=True)
        
        return True
    
    async def validate_business_rules(self, data: Any) -> None:
        """
        Valida le regole business per gli ordini.
        Questo metodo è richiesto dall'interfaccia IBaseService.
        
        Args:
            data: Dati da validare (può essere qualsiasi tipo)
        """
        # Per ora non ci sono regole business specifiche da validare
        # Questo metodo può essere esteso in futuro se necessario
        pass
    
    @emit_event_on_success(
        event_type=EventType.ORDER_STATUS_CHANGED,
        data_extractor=_extract_order_status_data,
        condition=_should_emit_order_status_event,
        source="order_service.update_order_status",
    )
    async def update_order_status(
        self, 
        order_id: int,
        new_status_id: int
    ) -> Dict[str, Any]:
        """
        Aggiorna lo stato di un ordine e crea record in orders_history.
        Gestisce le eccezioni internamente per non bloccare il flusso.
        
        Args:
            order_id: ID dell'ordine
            new_status_id: Nuovo stato dell'ordine
            
        Returns:
            Dict con message, order_id, new_status_id, old_state_id se successo,
            None se errore (gestito silenziosamente)
        """
        order = self._order_repository.get_by_id(_id=order_id)
        if order is None:
            logger.warning(f"Ordine {order_id} non trovato durante aggiornamento stato")
            return None

        # Valida che l'id_order_state esista
        order_state = self._order_repository.session.query(OrderState).filter(
            OrderState.id_order_state == new_status_id
        ).first()
        if not order_state:
            logger.warning(f"Stato ordine {new_status_id} non esiste nella tabella order_states")
            return None

        old_state_id = order.id_order_state
        if old_state_id == new_status_id:
            return {
                "message": "Stato ordine aggiornato con successo",
                "order_id": order_id,
                "new_status_id": new_status_id,
            }

        order.id_order_state = new_status_id
        
        # Aggiorna updated_at con formato DD-MM-YYYY hh:mm:ss
        order.updated_at = format_datetime_ddmmyyyy_hhmmss(datetime.now())
        
        self._order_repository.session.add(order)

        order_history_insert = orders_history.insert().values(
            id_order=order_id,
            id_order_state=new_status_id,
            date_add=datetime.now()
        )
        self._order_repository.session.execute(order_history_insert)
        self._order_repository.session.commit()

        return {
            "message": "Stato ordine aggiornato con successo",
            "order_id": order_id,
            "new_status_id": new_status_id,
            "old_state_id": old_state_id,
        }

    
    @emit_event_on_success(
        event_type=EventType.ORDER_STATUS_CHANGED,
        data_extractor=_extract_order_update_status_data,
        condition=_should_emit_order_update_status_event,
        source="order_service.update_order",
    )
    async def update_order(
        self,
        order_id: int,
        order_schema: OrderUpdateSchema
    ) -> Dict[str, Any]:
        """
        Aggiorna un ordine esistente.
        
        Args:
            order_id: ID dell'ordine
            order_schema: Schema con i campi da aggiornare
            
        Returns:
            Dict con message, order_id, e opzionalmente old_state_id, new_state_id
        """
        order = self._order_repository.get_by_id(_id=order_id)
        if order is None:
            raise ValueError(f"Ordine {order_id} non trovato")

        # Salvare vecchio stato prima dell'aggiornamento
        old_state_id = order.id_order_state
        old_total_discounts = getattr(order, "total_discounts", None)
        
        # Verificare se id_order_state viene aggiornato
        new_state_id = None
        if hasattr(order_schema, 'id_order_state') and order_schema.id_order_state is not None:
            new_state_id = order_schema.id_order_state
        
        updated_order = self._order_repository.update(edited_order=order, data=order_schema)
        if getattr(updated_order, "total_discounts", None) != old_total_discounts:
            self.recalculate_totals_for_order(order_id)
        
        # Restituire risultato con old_state_id se lo stato è cambiato
        if new_state_id is not None and new_state_id != old_state_id:
            return {
                "message": "Ordine aggiornato con successo",
                "order_id": order_id,
                "old_state_id": old_state_id,
                "new_state_id": new_state_id,
            }
        
        return {
            "message": "Ordine aggiornato con successo",
            "order_id": order_id
        }
    
    async def bulk_update_order_status(
        self, 
        updates: List[OrderStatusUpdateItem]
    ) -> BulkOrderStatusUpdateResponseSchema:
        """
        Aggiorna gli stati di più ordini in modo massivo.
        
        La logica business include:
        - Validazione stati nella tabella order_states
        - Verifica esistenza ordini
        - Verifica che lo stato sia diverso da quello corrente
        - Aggiornamento stato e creazione record in orders_history
        - Emissione eventi ORDER_STATUS_CHANGED per ogni cambio valido
        
        Args:
            updates: Lista di aggiornamenti stato ordine
            
        Returns:
            Risposta con successi, fallimenti e summary
        """
        successful: List[OrderStatusUpdateResult] = []
        failed: List[OrderStatusUpdateError] = []
        db = self._order_repository.session
        
        # 1. Validare stati: raccogliere tutti gli stati unici e verificare esistenza
        unique_state_ids = list(set(item.id_order_state for item in updates))
        valid_states = {
            state.id_order_state 
            for state in db.query(OrderState)
                .filter(OrderState.id_order_state.in_(unique_state_ids))
                .all()
        }
        
        # Aggiungere errori per stati non validi
        invalid_states = set(unique_state_ids) - valid_states
        if invalid_states:
            for item in updates:
                if item.id_order_state in invalid_states:
                    failed.append(OrderStatusUpdateError(
                        id_order=item.id_order,
                        error="INVALID_STATE",
                        reason=f"Stato {item.id_order_state} non esiste nella tabella order_states"
                    ))
        
        # 2. Processare ogni ordine
        for item in updates:
            # Skip se già fallito per stato non valido
            if item.id_order_state in invalid_states:
                continue
                
            try:
                # Usare funzione helper con decorator per aggiornare ordine ed emettere evento
                result = await _update_single_order_status_in_bulk(
                    order_id=item.id_order,
                    new_state_id=item.id_order_state,
                    or_repo=self._order_repository
                )
                
                # Aggiungere a successi
                successful.append(OrderStatusUpdateResult(
                    id_order=result["order_id"],
                    old_state_id=result["old_state_id"],
                    new_state_id=result["new_state_id"]
                ))
                
            except ValueError as e:
                # Errore di validazione (ordine non trovato o stato già impostato)
                error_msg = str(e)
                if "non trovato" in error_msg:
                    error_type = "ORDER_NOT_FOUND"
                elif "è già nello stato" in error_msg:
                    error_type = "STATE_ALREADY_SET"
                else:
                    error_type = "VALIDATION_ERROR"
                
                failed.append(OrderStatusUpdateError(
                    id_order=item.id_order,
                    error=error_type,
                    reason=error_msg
                ))
                
            except Exception as e:
                # Rollback in caso di errore
                self._order_repository.session.rollback()
                logger.error(
                    f"Errore durante aggiornamento stato ordine {item.id_order}: {e}",
                    exc_info=True
                )
                failed.append(OrderStatusUpdateError(
                    id_order=item.id_order,
                    error="UPDATE_ERROR",
                    reason=f"Errore durante aggiornamento: {str(e)}"
                ))
        
        # 3. Preparare risposta
        total = len(updates)
        successful_count = len(successful)
        failed_count = len(failed)
        
        return BulkOrderStatusUpdateResponseSchema(
            successful=successful,
            failed=failed,
            summary={
                "total": total,
                "successful_count": successful_count,
                "failed_count": failed_count
            }
        )
