"""
Interfacce base per il sistema seguendo ISP (Interface Segregation Principle)
"""
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List, Dict, Any
from sqlalchemy.orm import Session

T = TypeVar('T')
K = TypeVar('K')

class IRepository(Generic[T, K], ABC):
    """Interface base per repository seguendo ISP"""
    
    @abstractmethod
    def get_by_id(self, id: K) -> Optional[T]:
        """Ottiene un'entità per ID"""
        pass
    
    @abstractmethod
    def get_all(self, **filters) -> List[T]:
        """Ottiene tutte le entità con filtri opzionali"""
        pass
    
    @abstractmethod
    def create(self, entity: T) -> T:
        """Crea una nuova entità"""
        pass
    
    @abstractmethod
    def update(self, entity: T) -> T:
        """Aggiorna un'entità esistente"""
        pass
    
    @abstractmethod
    def delete(self, id: K) -> bool:
        """Elimina un'entità per ID"""
        pass
    
    @abstractmethod
    def bulk_create(self, entities: List[T], batch_size: int = 1000) -> int:
        """Crea multiple entità in batch per migliori prestazioni"""
        pass

class IUnitOfWork(ABC):
    """Interface per Unit of Work pattern"""
    
    @abstractmethod
    def commit(self):
        """Commit della transazione"""
        pass
    
    @abstractmethod
    def rollback(self):
        """Rollback della transazione"""
        pass
    
    @abstractmethod
    def __enter__(self):
        pass
    
    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

class IBaseService(ABC):
    """Interface base per i servizi"""
    
    @abstractmethod
    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business"""
        pass

class IQueryBuilder(ABC):
    """Interface per query builder"""
    
    @abstractmethod
    def build_query(self, base_query, filters: Dict[str, Any]):
        """Costruisce una query con filtri"""
        pass

class IValidationService(ABC):
    """Interface per servizi di validazione"""
    
    @abstractmethod
    def validate_email(self, email: str) -> bool:
        """Valida formato email"""
        pass
    
    @abstractmethod
    def validate_phone(self, phone: str) -> bool:
        """Valida formato telefono"""
        pass

class ILogger(ABC):
    """Interface per logging"""
    
    @abstractmethod
    def info(self, message: str, **kwargs):
        """Log livello info"""
        pass
    
    @abstractmethod
    def error(self, message: str, **kwargs):
        """Log livello error"""
        pass
    
    @abstractmethod
    def warning(self, message: str, **kwargs):
        """Log livello warning"""
        pass
