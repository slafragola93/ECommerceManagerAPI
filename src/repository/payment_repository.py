"""
Payment Repository rifattorizzato seguendo SOLID
"""
from typing import Optional, List
from sqlalchemy.orm import Session, noload
from sqlalchemy import func, desc
from src.models.payment import Payment
from src.repository.interfaces.payment_repository_interface import IPaymentRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException
from src.services import QueryUtils
from src.schemas.payment_schema import PaymentSchema

class PaymentRepository(BaseRepository[Payment, int], IPaymentRepository):
    """Payment Repository rifattorizzato seguendo SOLID"""
    
    def __init__(self, session: Session):
        super().__init__(session, Payment)
    
    def get_all(self, **filters) -> List[Payment]:
        """Ottiene tutte le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class).order_by(desc(Payment.id_payment))
            
            # Paginazione
            page = filters.get('page', 1)
            limit = filters.get('limit', 100)
            offset = self.get_offset(limit, page)
            
            return query.offset(offset).limit(limit).all()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving {self._model_class.__name__} list: {str(e)}")
    
    def get_count(self, **filters) -> int:
        """Conta le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class)
            return query.count()
        except Exception as e:
            raise InfrastructureException(f"Database error counting {self._model_class.__name__}: {str(e)}")
    
    def get_by_name(self, name: str) -> Optional[Payment]:
        """Ottiene un payment per nome (case insensitive)"""
        try:
            return self._session.query(Payment).filter(
                func.lower(Payment.name) == func.lower(name)
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving payment by name: {str(e)}")
    
    def is_complete_payment(self, id_payment: int) -> Optional[bool]:
        """
        Query idratata: recupera solo is_complete_payment per un payment.
        
        Args:
            id_payment: ID del payment
            
        Returns:
            True se is_complete_payment=True, False se is_complete_payment=False, None se payment non esiste
        """
        try:
            from sqlalchemy import text
            result = self._session.execute(
                text("SELECT is_complete_payment FROM payments WHERE id_payment = :id_payment"),
                {"id_payment": id_payment}
            ).first()
            if result:
                return bool(result[0])
            return None
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving is_complete_payment for payment {id_payment}: {str(e)}")
    
    def bulk_create_csv_import(self, data_list: List[PaymentSchema], batch_size: int = 1000) -> int:
        """
        Bulk insert payments da CSV import.
        
        Payments non hanno id_origin, usa name come unique key.
        
        Args:
            data_list: Lista PaymentSchema da inserire
            batch_size: Dimensione batch (default: 1000)
            
        Returns:
            Numero payments inseriti
        """
        if not data_list:
            return 0
        
        try:
            # Get existing names to avoid duplicates
            names = [data.name.lower() for data in data_list if data.name]
            existing_payments = self._session.query(func.lower(Payment.name)).filter(
                func.lower(Payment.name).in_(names)
            ).all()
            existing_names = {p[0] for p in existing_payments}
            
            # Filter new payments
            new_payments_data = [data for data in data_list if data.name.lower() not in existing_names]
            
            if not new_payments_data:
                return 0
            
            # Batch insert
            total_inserted = 0
            for i in range(0, len(new_payments_data), batch_size):
                batch = new_payments_data[i:i + batch_size]
                payments = [Payment(**p.model_dump()) for p in batch]
                self._session.bulk_save_objects(payments)
                total_inserted += len(payments)
            
            self._session.commit()
            return total_inserted
            
        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(f"Database error bulk creating payments: {str(e)}")
