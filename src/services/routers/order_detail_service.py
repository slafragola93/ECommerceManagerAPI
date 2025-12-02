"""
Order Detail Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any, Dict
from sqlalchemy.orm import Session
from src.services.interfaces.order_detail_service_interface import IOrderDetailService
from src.repository.interfaces.order_detail_repository_interface import IOrderDetailRepository
from src.schemas.order_detail_schema import OrderDetailSchema
from src.models.order_detail import OrderDetail
from src.core.exceptions import (
    ValidationException, 
    NotFoundException, 
    BusinessRuleException,
    ExceptionFactory,
    ErrorCode
)
from src.services.interfaces.order_service_interface import IOrderService
from src.services.routers.product_service import ProductService
from src.repository.product_repository import ProductRepository
from src.services.core.tool import calculate_price_with_tax, calculate_price_without_tax
from src.models.tax import Tax


def _collect_tracked_values(order_detail: OrderDetail) -> Dict[str, Any]:
    """Raccoglie i valori di confronto per capire se serve ricalcolare l'ordine."""
    return {
        "id_tax": getattr(order_detail, "id_tax", None),
        "unit_price_net": getattr(order_detail, "unit_price_net", None),
        "unit_price_with_tax": getattr(order_detail, "unit_price_with_tax", None),
        "product_weight": getattr(order_detail, "product_weight", None),
        "product_qty": getattr(order_detail, "product_qty", None),
        "reduction_percent": getattr(order_detail, "reduction_percent", None),
        "reduction_amount": getattr(order_detail, "reduction_amount", None),
    }

def _calculate_price_fields(order_detail_data: OrderDetailSchema, db: Session) -> Dict[str, float]:
    """
    Calcola i campi prezzo mancanti basandosi sui campi forniti e id_tax.
    Restituisce un dizionario con tutti i campi prezzo calcolati.
    """
    unit_price_net = order_detail_data.unit_price_net
    unit_price_with_tax = order_detail_data.unit_price_with_tax
    quantity = order_detail_data.product_qty or 1
    id_tax = order_detail_data.id_tax
    
    # Recupera tax_percentage se id_tax è fornito
    tax_percentage = 0.0
    if id_tax:
        tax = db.query(Tax).filter(Tax.id_tax == id_tax).first()
        if tax and tax.percentage is not None:
            tax_percentage = float(tax.percentage)
    
    # Se unit_price_with_tax è fornito ma unit_price_net no, calcola unit_price_net
    if unit_price_with_tax is not None and unit_price_with_tax > 0 and (unit_price_net is None or unit_price_net == 0):
        unit_price_net = calculate_price_without_tax(unit_price_with_tax, tax_percentage)
    
    # Se unit_price_net è fornito ma unit_price_with_tax no, calcola unit_price_with_tax
    if unit_price_net is not None and unit_price_net > 0 and (unit_price_with_tax is None or unit_price_with_tax == 0):
        unit_price_with_tax = calculate_price_with_tax(unit_price_net, tax_percentage, quantity=1)
    
    # Calcola totali base (prima degli sconti)
    total_base_net = (unit_price_net or 0.0) * quantity
    total_base_with_tax = (unit_price_with_tax or 0.0) * quantity
    
    # Applica sconti
    reduction_percent = order_detail_data.reduction_percent or 0.0
    reduction_amount = order_detail_data.reduction_amount or 0.0
    
    if reduction_percent > 0:
        from src.services.core.tool import calculate_amount_with_percentage
        discount = calculate_amount_with_percentage(total_base_net, reduction_percent)
        total_price_net = total_base_net - discount
    elif reduction_amount > 0:
        total_price_net = total_base_net - reduction_amount
    else:
        total_price_net = total_base_net
    
    # Calcola total_price_with_tax dopo gli sconti
    if total_price_net > 0 and tax_percentage > 0:
        total_price_with_tax = calculate_price_with_tax(total_price_net, tax_percentage, quantity=1)
    else:
        total_price_with_tax = total_base_with_tax
    
    return {
        'unit_price_net': unit_price_net or 0.0,
        'unit_price_with_tax': unit_price_with_tax or 0.0,
        'total_price_net': total_price_net,
        'total_price_with_tax': total_price_with_tax
    }

class OrderDetailService(IOrderDetailService):
    """Order Detail Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""
    
    def __init__(
        self,
        order_detail_repository: IOrderDetailRepository,
        db: Session,
        order_service: Optional[IOrderService] = None,
        product_service: Optional[ProductService] = None,
        order_document_service: Optional[Any] = None
    ):
        self._order_detail_repository = order_detail_repository
        self._order_service = order_service
        self._db = db
        self._order_document_service = order_document_service
        # Inizializza ProductService se non fornito (DIP - Dependency Inversion)
        self._product_service = product_service or ProductService(ProductRepository(db))

    def _recalculate_order_totals(self, order_id: Optional[int], order_detail: Optional[OrderDetail] = None) -> None:
        """
        Ricalcola i totali dell'ordine o dell'order document in base ai collegamenti.
        
        Logica:
        - Se id_order > 0 e (id_order_document IS NULL o = 0): ricalcola Order
        - Se (id_order IS NULL o = 0) e id_order_document > 0: 
          - Se OrderDocument ha id_order collegato: ricalcola Order (che gestirà anche OrderDocument)
          - Altrimenti: ricalcola solo OrderDocument standalone
        """
        if order_detail is None:
            # Fallback: usa order_id se disponibile
            if order_id and order_id > 0 and self._order_service:
                self._order_service.recalculate_totals_for_order(order_id)
            return
        
        id_order = getattr(order_detail, 'id_order', None)
        id_order_document = getattr(order_detail, 'id_order_document', None)
        
        # Caso 1: OrderDetail collegato a Order (id_order > 0 e id_order_document = 0 o NULL)
        if id_order and id_order > 0 and (id_order_document is None or id_order_document == 0):
            if self._order_service:
                self._order_service.recalculate_totals_for_order(id_order)
            return
        
        # Caso 2: OrderDetail collegato a OrderDocument (id_order = 0 o NULL e id_order_document > 0)
        if (id_order is None or id_order == 0) and id_order_document and id_order_document > 0:
            # Verifica se OrderDocument ha un Order collegato
            from src.models.order_document import OrderDocument
            order_document = self._db.query(OrderDocument).filter(
                OrderDocument.id_order_document == id_order_document
            ).first()
            
            if order_document and order_document.id_order and order_document.id_order > 0:
                # OrderDocument ha Order collegato: ricalcola Order (che gestirà anche OrderDocument)
                if self._order_service:
                    self._order_service.recalculate_totals_for_order(order_document.id_order)
            else:
                # OrderDocument standalone: ricalcola solo OrderDocument
                if self._order_document_service:
                    self._order_document_service.recalculate_products_totals_for_order_document_standalone(id_order_document)
    
    async def create_order_detail(self, order_detail_data: OrderDetailSchema) -> OrderDetail:
        """Crea un nuovo order detail con validazioni business"""
        
        # Business Rule 1: Validazione quantità
        await self._validate_quantity(order_detail_data.product_qty)
        
        # Business Rule 2: Validazione prezzi
        if order_detail_data.unit_price_with_tax is not None:
            await self._validate_price(order_detail_data.unit_price_with_tax)
        if order_detail_data.unit_price_net is not None:
            await self._validate_price(order_detail_data.unit_price_net)
        
        # Business Rule 3: Validazione peso
        await self._validate_weight(order_detail_data.product_weight)
        
        # Business Rule 4: Validazione riduzioni
        await self._validate_reductions(order_detail_data.reduction_percent, order_detail_data.reduction_amount)
        
        # Calcola i campi prezzo mancanti
        price_fields = _calculate_price_fields(order_detail_data, self._db)
        
        # Crea l'order detail
        try:
            order_detail_dict = order_detail_data.model_dump()
            order_detail_dict.update(price_fields)
            order_detail = OrderDetail(**order_detail_dict)
            order_detail = self._order_detail_repository.create(order_detail)
            self._recalculate_order_totals(order_detail.id_order, order_detail)
            return order_detail
        except Exception as e:
            raise ValidationException(f"Error creating order detail: {str(e)}")
    
    async def update_order_detail(self, order_detail_id: int, order_detail_data: OrderDetailSchema) -> OrderDetail:
        """Aggiorna un order detail esistente"""
        
        # Verifica esistenza
        order_detail = self._order_detail_repository.get_by_id_or_raise(order_detail_id)
        previous_values = _collect_tracked_values(order_detail)
        
        # Business Rule: Validazione quantità se fornita
        if order_detail_data.product_qty is not None:
            await self._validate_quantity(order_detail_data.product_qty)
        
        # Business Rule: Validazione prezzi se forniti
        if order_detail_data.unit_price_with_tax is not None:
            await self._validate_price(order_detail_data.unit_price_with_tax)
        if order_detail_data.unit_price_net is not None:
            await self._validate_price(order_detail_data.unit_price_net)
        
        # Business Rule: Validazione peso se fornito
        if order_detail_data.product_weight is not None:
            await self._validate_weight(order_detail_data.product_weight)
        
        # Business Rule: Validazione riduzioni se fornite
        if order_detail_data.reduction_percent is not None or order_detail_data.reduction_amount is not None:
            await self._validate_reductions(
                order_detail_data.reduction_percent or order_detail.reduction_percent,
                order_detail_data.reduction_amount or order_detail.reduction_amount
            )
        
        # Aggiorna l'order detail
        try:
            # Aggiorna i campi
            update_payload = order_detail_data.model_dump(exclude_unset=True)
            
            # Calcola i campi prezzo mancanti se necessario
            if 'unit_price_net' in update_payload or 'unit_price_with_tax' in update_payload or 'id_tax' in update_payload:
                # Crea un OrderDetailSchema temporaneo con i valori aggiornati
                temp_data = OrderDetailSchema(**{**order_detail.model_dump(), **update_payload})
                price_fields = _calculate_price_fields(temp_data, self._db)
                update_payload.update(price_fields)
            
            for field_name, value in update_payload.items():
                if hasattr(order_detail, field_name) and value is not None:
                    setattr(order_detail, field_name, value)
            
            updated_order_detail = self._order_detail_repository.update(order_detail)
            if update_payload and updated_order_detail.id_order and updated_order_detail.id_order > 0:
                tracked_fields = (
                    "id_tax",
                    "unit_price_net",
                    "unit_price_with_tax",
                    "product_weight",
                    "product_qty",  
                    "reduction_percent",
                    "reduction_amount",
                )
                tracked_changed = any(
                    field in update_payload and previous_values.get(field) != getattr(updated_order_detail, field)
                    for field in tracked_fields
                )
                if tracked_changed:
                    self._recalculate_order_totals(updated_order_detail.id_order, updated_order_detail)
            return updated_order_detail
        except Exception as e:
            raise ValidationException(f"Error updating order detail: {str(e)}")
    
    async def get_order_detail(self, order_detail_id: int) -> dict:
        """
        Ottiene un order detail per ID, arricchito con img_url.
        Segue SRP: responsabilità singola di recuperare e arricchire un order detail.
        Segue DIP: usa ProductService per gestire le immagini.
        """
        order_detail = self._order_detail_repository.get_by_id_or_raise(order_detail_id)
        
        # Recupera img_url del prodotto usando ProductService (DIP)
        if order_detail.id_product:
            images_map = self._product_service.get_product_images_map([order_detail.id_product], self._db)
            img_url = images_map.get(order_detail.id_product)
        else:
            img_url = None
        
        return self._order_detail_repository.formatted_output(order_detail, img_url=img_url)
    
    async def get_order_details(self, page: int = 1, limit: int = 10, **filters) -> List[dict]:
        """
        Ottiene la lista degli order details con filtri, arricchita con img_url.
        Segue SRP: orchestrazione del recupero dati con enrichment delle immagini.
        Performance: usa batch query per recuperare tutte le immagini in una sola query.
        """
        try:
            # Validazione parametri
            if page < 1:
                page = 1
            if limit < 1:
                limit = 10
            
            # Aggiungi page e limit ai filtri
            filters['page'] = page
            filters['limit'] = limit
            
            # Usa il repository con i filtri
            order_details = self._order_detail_repository.get_all(**filters)
            
            if not order_details:
                return []
            
            # PERFORMANCE OPTIMIZATION: Recupera tutte le immagini in batch (1 query invece di N)
            # Usa ProductService per gestire le immagini (DIP - Dependency Inversion)
            product_ids = [od.id_product for od in order_details if od.id_product]
            images_map = self._product_service.get_product_images_map(product_ids, self._db)
            
            # Formatta output con img_url
            return [
                self._order_detail_repository.formatted_output(
                    od, 
                    img_url=images_map.get(od.id_product)
                )
                for od in order_details
            ]
        except Exception as e:
            raise ValidationException(f"Error retrieving order details: {str(e)}")
    
    async def delete_order_detail(self, order_detail_id: int) -> bool:
        """Elimina un order detail"""
        # Verifica esistenza
        order_detail = self._order_detail_repository.get_by_id_or_raise(order_detail_id)
        order_id = getattr(order_detail, "id_order", None)
        
        try:
            # Salva i dati prima della cancellazione per il ricalcolo
            id_order = getattr(order_detail, 'id_order', None)
            id_order_document = getattr(order_detail, 'id_order_document', None)
            
            result = self._order_detail_repository.delete(order_detail_id)
            if result:
                # Crea un OrderDetail temporaneo con i dati salvati per il ricalcolo
                temp_order_detail = OrderDetail()
                temp_order_detail.id_order = id_order
                temp_order_detail.id_order_document = id_order_document
                self._recalculate_order_totals(id_order, temp_order_detail)
            return result
        except Exception as e:
            raise ValidationException(f"Error deleting order detail: {str(e)}")
    
    async def get_order_details_count(self, **filters) -> int:
        """Ottiene il numero totale di order details con filtri"""
        try:
            return self._order_detail_repository.get_count(**filters)
        except Exception as e:
            raise ValidationException(f"Error counting order details: {str(e)}")
    
    async def get_order_details_by_order_id(self, order_id: int) -> List[dict]:
        """
        Ottiene tutti i dettagli per un ordine specifico, arricchiti con img_url.
        Performance: usa batch query per recuperare tutte le immagini in una sola query.
        Segue DIP: usa ProductService per gestire le immagini.
        """
        try:
            order_details = self._order_detail_repository.get_by_order_id(order_id)
            
            if not order_details:
                return []
            
            # PERFORMANCE: Batch recupero immagini
            product_ids = [od.id_product for od in order_details if od.id_product]
            images_map = self._product_service.get_product_images_map(product_ids, self._db)
            
            return [
                self._order_detail_repository.formatted_output(od, img_url=images_map.get(od.id_product))
                for od in order_details
            ]
        except Exception as e:
            raise ValidationException(f"Error retrieving order details by order ID: {str(e)}")
    
    async def get_order_details_by_order_document_id(self, order_document_id: int) -> List[dict]:
        """
        Ottiene tutti i dettagli per un documento ordine specifico, arricchiti con img_url.
        Performance: usa batch query per recuperare tutte le immagini in una sola query.
        Segue DIP: usa ProductService per gestire le immagini.
        """
        try:
            order_details = self._order_detail_repository.get_by_order_document_id(order_document_id)
            
            if not order_details:
                return []
            
            # PERFORMANCE: Batch recupero immagini usando ProductService
            product_ids = [od.id_product for od in order_details if od.id_product]
            images_map = self._product_service.get_product_images_map(product_ids, self._db)
            
            return [
                self._order_detail_repository.formatted_output(od, img_url=images_map.get(od.id_product))
                for od in order_details
            ]
        except Exception as e:
            raise ValidationException(f"Error retrieving order details by order document ID: {str(e)}")
    
    async def _validate_quantity(self, quantity: int) -> None:
        """Valida la quantità del prodotto"""
        if quantity is None or quantity < 0:
            raise ValidationException("Quantity must be a positive number")
        
        if quantity > 10000:  # Limite business ragionevole
            raise ValidationException("Quantity cannot exceed 10000 units")
    
    async def _validate_price(self, price: float) -> None:
        """Valida il prezzo del prodotto"""
        if price is None or price < 0:
            raise ValidationException("Price must be a positive number")
        
        if price > 1000000:  # Limite business ragionevole
            raise ValidationException("Price cannot exceed 1,000,000")
    
    async def _validate_weight(self, weight: float) -> None:
        """Valida il peso del prodotto"""
        if weight is not None and weight < 0:
            raise ValidationException("Weight must be a positive number")
        
        if weight is not None and weight > 1000:  # Limite business ragionevole (kg)
            raise ValidationException("Weight cannot exceed 1000 kg")
    
    async def _validate_reductions(self, reduction_percent: float, reduction_amount: float) -> None:
        """Valida le riduzioni"""
        if reduction_percent is not None and (reduction_percent < 0 or reduction_percent > 100):
            raise ValidationException("Reduction percentage must be between 0 and 100")
        
        if reduction_amount is not None and reduction_amount < 0:
            raise ValidationException("Reduction amount must be a positive number")
        
        if reduction_percent is not None and reduction_amount is not None and reduction_percent > 0 and reduction_amount > 0:
            raise BusinessRuleException(
                "Cannot apply both percentage and amount reduction simultaneously",
                ErrorCode.BUSINESS_RULE_VIOLATION,
                {"reduction_percent": reduction_percent, "reduction_amount": reduction_amount}
            )
    
    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business per Order Detail"""
        if hasattr(data, 'product_qty'):
            await self._validate_quantity(data.product_qty)
        if hasattr(data, 'unit_price_with_tax'):
            await self._validate_price(data.unit_price_with_tax)
        if hasattr(data, 'unit_price_net'):
            await self._validate_price(data.unit_price_net)
        if hasattr(data, 'product_weight'):
            await self._validate_weight(data.product_weight)
