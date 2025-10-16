"""
Base Repository implementation seguendo SRP e OCP
"""
from typing import Generic, TypeVar, Optional, List, Dict, Any, Type, Union
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from src.core.interfaces import IRepository
from src.core.exceptions import NotFoundException, InfrastructureException

T = TypeVar('T')
K = TypeVar('K')

class BaseRepository(Generic[T, K], IRepository[T, K]):
    """Repository base con implementazioni comuni seguendo DRY e SRP"""
    
    def __init__(self, session: Session, model_class: Type[T]):
        self._session = session
        self._model_class = model_class
    
    def get_by_id(self, id: K) -> Optional[T]:
        """Ottiene un'entità per ID"""
        try:
            id_field = self._get_id_field()
            return self._session.query(self._model_class).filter(
                getattr(self._model_class, id_field) == id
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving {self._model_class.__name__}: {str(e)}")
    
    def get_by_id_or_raise(self, id: K) -> T:
        """Ottiene un'entità per ID o lancia NotFoundException"""
        entity = self.get_by_id(id)
        if not entity:
            raise NotFoundException(self._model_class.__name__, id)
        return entity
    
    def get_all(self, **filters) -> List[T]:
        """Ottiene tutte le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class)
            query = self._apply_filters(query, filters)
            return query.all()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving {self._model_class.__name__} list: {str(e)}")
    
    def get_count(self, **filters) -> int:
        """Conta le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class)
            query = self._apply_filters(query, filters)
            return query.count()
        except Exception as e:
            raise InfrastructureException(f"Database error counting {self._model_class.__name__}: {str(e)}")
    
    def exists(self, id: K) -> bool:
        """Verifica se un'entità esiste"""
        try:
            # Trova il campo ID corretto
            id_field = self._get_id_field()
            return self._session.query(self._model_class).filter(
                getattr(self._model_class, id_field) == id
            ).first() is not None
        except Exception as e:
            raise InfrastructureException(f"Database error checking {self._model_class.__name__} existence: {str(e)}")
    
    def create(self, entity: Union[T, dict]) -> T:
        """Crea una nuova entità"""
        try:
            # Se è un dizionario, crea un'istanza del modello
            if isinstance(entity, dict):
                model_instance = self._model_class(**entity)
                self._session.add(model_instance)
                self._session.commit()
                self._session.refresh(model_instance)
                return model_instance
            else:
                # Se è già un'istanza del modello
                self._session.add(entity)
                self._session.commit()
                self._session.refresh(entity)
                return entity
        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(f"Database error creating {self._model_class.__name__}: {str(e)}")
    
    def update(self, entity: T) -> T:
        """Aggiorna un'entità esistente"""
        try:
            self._session.merge(entity)
            self._session.commit()
            self._session.refresh(entity)
            return entity
        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(f"Database error updating {self._model_class.__name__}: {str(e)}")
    
    def delete(self, id: K) -> bool:
        """Elimina un'entità per ID"""
        try:
            entity = self.get_by_id_or_raise(id)
            self._session.delete(entity)
            self._session.commit()
            return True
        except NotFoundException:
            raise
        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(f"Database error deleting {self._model_class.__name__}: {str(e)}")
    
    def delete_entity(self, entity: T) -> bool:
        """Elimina un'entità esistente"""
        try:
            self._session.delete(entity)
            return True
        except Exception as e:
            raise InfrastructureException(f"Database error deleting {self._model_class.__name__}: {str(e)}")
    
    def _apply_filters(self, query, filters: Dict[str, Any]):
        """Applica filtri alla query"""
        for field_name, value in filters.items():
            if value is None:
                continue
            
            if hasattr(self._model_class, field_name):
                field = getattr(self._model_class, field_name)
                
                if isinstance(value, list):
                    # Filtro IN per liste
                    query = query.filter(field.in_(value))
                elif isinstance(value, str) and '%' in value:
                    # Filtro LIKE per stringhe
                    query = query.filter(field.like(value))
                elif isinstance(value, str):
                    # Filtro esatto per stringhe
                    query = query.filter(field == value)
                else:
                    # Filtro esatto per altri tipi
                    query = query.filter(field == value)
        
        return query
    
    def paginate(self, query, page: int = 1, limit: int = 10):
        """Applica paginazione a una query"""
        offset = (page - 1) * limit
        return query.offset(offset).limit(limit)
    
    def get_offset(self, limit: int, page: int) -> int:
        """Calcola l'offset per la paginazione"""
        return (page - 1) * limit
    
    def _get_id_field(self) -> str:
        """Trova il campo ID corretto per il modello"""
        model_name = self._model_class.__name__
        
        # Lista di pattern da provare in ordine di priorità
        patterns = [
            'id',  # Campo generico 'id'
            f'id_{model_name.lower()}',  # id_modelname
            f'id_{self._convert_camel_to_snake(model_name)}',  # id_model_name (con underscore)
        ]
        
        for pattern in patterns:
            if hasattr(self._model_class, pattern):
                return pattern
        
        raise ValueError(f"Cannot find ID field for {model_name}. Tried patterns: {patterns}")
    
    def _convert_camel_to_snake(self, camel_str: str) -> str:
        """Converte CamelCase in snake_case"""
        import re
        # Inserisce underscore prima delle maiuscole che seguono minuscole o numeri
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', camel_str)
        # Inserisce underscore prima delle maiuscole che precedono minuscole
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
