"""
Payment Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any
from src.services.interfaces.payment_service_interface import IPaymentService
from src.repository.interfaces.payment_repository_interface import IPaymentRepository
from src.schemas.payment_schema import PaymentSchema
from src.models.payment import Payment
from src.core.exceptions import (
    ValidationException, 
    NotFoundException, 
    BusinessRuleException,
    ExceptionFactory,
    ErrorCode
)

class PaymentService(IPaymentService):
    """Payment Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""
    
    def __init__(self, payment_repository: IPaymentRepository):
        self._payment_repository = payment_repository
    
    async def create_payment(self, payment_data: PaymentSchema) -> Payment:
        """Crea un nuovo payment con validazioni business"""
        
        # Business Rule 1: Nome deve essere unico
        if hasattr(payment_data, 'name') and payment_data.name:
            existing_payment = self._payment_repository.get_by_name(payment_data.name)
            if existing_payment:
                raise BusinessRuleException(
                    f"Metodo di pagamento '{payment_data.name}' già esistente",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": payment_data.name}
                )
        
        # Crea il payment
        try:
            payment = Payment(**payment_data.model_dump())
            payment = self._payment_repository.create(payment)
            return payment
        except Exception as e:
            raise ValidationException(f"Error creating payment: {str(e)}")
    
    async def update_payment(self, payment_id: int, payment_data: PaymentSchema) -> Payment:
        """Aggiorna un payment esistente"""
        
        # Verifica esistenza
        payment = self._payment_repository.get_by_id_or_raise(payment_id)
        
        # Business Rule: Se nome cambia, deve essere unico
        if hasattr(payment_data, 'name') and payment_data.name != payment.name:
            existing = self._payment_repository.get_by_name(payment_data.name)
            if existing and existing.id_payment != payment_id:
                raise BusinessRuleException(
                    f"Metodo di pagamento '{payment_data.name}' già esistente",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": payment_data.name}
                )
        
        # Aggiorna il payment
        try:
            # Aggiorna i campi
            for field_name, value in payment_data.model_dump(exclude_unset=True).items():
                if hasattr(payment, field_name) and value is not None:
                    setattr(payment, field_name, value)
            
            updated_payment = self._payment_repository.update(payment)
            return updated_payment
        except Exception as e:
            raise ValidationException(f"Error updating payment: {str(e)}")
    
    async def get_payment(self, payment_id: int) -> Payment:
        """Ottiene un payment per ID"""
        payment = self._payment_repository.get_by_id_or_raise(payment_id)
        return payment
    
    async def get_payments(self, page: int = 1, limit: int = 10, **filters) -> List[Payment]:
        """Ottiene la lista dei payment con filtri"""
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
            payments = self._payment_repository.get_all(**filters)
            
            return payments
        except Exception as e:
            raise ValidationException(f"Error retrieving payments: {str(e)}")
    
    async def delete_payment(self, payment_id: int) -> bool:
        """Elimina un payment"""
        # Verifica esistenza
        self._payment_repository.get_by_id_or_raise(payment_id)
        
        try:
            return self._payment_repository.delete(payment_id)
        except Exception as e:
            raise ValidationException(f"Error deleting payment: {str(e)}")
    
    async def get_payments_count(self, **filters) -> int:
        """Ottiene il numero totale di payment con filtri"""
        try:
            # Usa il repository con i filtri
            return self._payment_repository.get_count(**filters)
        except Exception as e:
            raise ValidationException(f"Error counting payments: {str(e)}")
    
    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business per Payment"""
        # Validazioni specifiche per Payment se necessarie
        pass
