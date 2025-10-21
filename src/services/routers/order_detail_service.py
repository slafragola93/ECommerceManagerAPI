"""
Order Detail Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any
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

class OrderDetailService(IOrderDetailService):
    """Order Detail Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""
    
    def __init__(self, order_detail_repository: IOrderDetailRepository):
        self._order_detail_repository = order_detail_repository
    
    async def create_order_detail(self, order_detail_data: OrderDetailSchema) -> OrderDetail:
        """Crea un nuovo order detail con validazioni business"""
        
        # Business Rule 1: Validazione quantità
        await self._validate_quantity(order_detail_data.product_qty)
        
        # Business Rule 2: Validazione prezzo
        await self._validate_price(order_detail_data.product_price)
        
        # Business Rule 3: Validazione peso
        await self._validate_weight(order_detail_data.product_weight)
        
        # Business Rule 4: Validazione riduzioni
        await self._validate_reductions(order_detail_data.reduction_percent, order_detail_data.reduction_amount)
        
        # Crea l'order detail
        try:
            order_detail = OrderDetail(**order_detail_data.dict())
            order_detail = self._order_detail_repository.create(order_detail)
            return order_detail
        except Exception as e:
            raise ValidationException(f"Error creating order detail: {str(e)}")
    
    async def update_order_detail(self, order_detail_id: int, order_detail_data: OrderDetailSchema) -> OrderDetail:
        """Aggiorna un order detail esistente"""
        
        # Verifica esistenza
        order_detail = self._order_detail_repository.get_by_id_or_raise(order_detail_id)
        
        # Business Rule: Validazione quantità se fornita
        if order_detail_data.product_qty is not None:
            await self._validate_quantity(order_detail_data.product_qty)
        
        # Business Rule: Validazione prezzo se fornito
        if order_detail_data.product_price is not None:
            await self._validate_price(order_detail_data.product_price)
        
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
            for field_name, value in order_detail_data.dict(exclude_unset=True).items():
                if hasattr(order_detail, field_name) and value is not None:
                    setattr(order_detail, field_name, value)
            
            updated_order_detail = self._order_detail_repository.update(order_detail)
            return updated_order_detail
        except Exception as e:
            raise ValidationException(f"Error updating order detail: {str(e)}")
    
    async def get_order_detail(self, order_detail_id: int) -> OrderDetail:
        """Ottiene un order detail per ID"""
        order_detail = self._order_detail_repository.get_by_id_or_raise(order_detail_id)
        return order_detail
    
    async def get_order_details(self, page: int = 1, limit: int = 10, **filters) -> List[OrderDetail]:
        """Ottiene la lista degli order details con filtri"""
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
            
            return order_details
        except Exception as e:
            raise ValidationException(f"Error retrieving order details: {str(e)}")
    
    async def delete_order_detail(self, order_detail_id: int) -> bool:
        """Elimina un order detail"""
        # Verifica esistenza
        self._order_detail_repository.get_by_id_or_raise(order_detail_id)
        
        try:
            return self._order_detail_repository.delete(order_detail_id)
        except Exception as e:
            raise ValidationException(f"Error deleting order detail: {str(e)}")
    
    async def get_order_details_count(self, **filters) -> int:
        """Ottiene il numero totale di order details con filtri"""
        try:
            return self._order_detail_repository.get_count(**filters)
        except Exception as e:
            raise ValidationException(f"Error counting order details: {str(e)}")
    
    async def get_order_details_by_order_id(self, order_id: int) -> List[OrderDetail]:
        """Ottiene tutti i dettagli per un ordine specifico"""
        try:
            order_details = self._order_detail_repository.get_by_order_id(order_id)
            return order_details
        except Exception as e:
            raise ValidationException(f"Error retrieving order details by order ID: {str(e)}")
    
    async def get_order_details_by_order_document_id(self, order_document_id: int) -> List[OrderDetail]:
        """Ottiene tutti i dettagli per un documento ordine specifico"""
        try:
            order_details = self._order_detail_repository.get_by_order_document_id(order_document_id)
            return order_details
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
        if hasattr(data, 'product_price'):
            await self._validate_price(data.product_price)
        if hasattr(data, 'product_weight'):
            await self._validate_weight(data.product_weight)
