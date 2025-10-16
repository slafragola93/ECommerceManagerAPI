"""
User Repository rifattorizzato seguendo SOLID
"""
from typing import Optional, List
from sqlalchemy.orm import Session, noload
from sqlalchemy import func, desc
from src.models.user import User
from src.repository.interfaces.user_repository_interface import IUserRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException
from src.services import QueryUtils

class UserRepository(BaseRepository[User, int], IUserRepository):
    """User Repository rifattorizzato seguendo SOLID"""
    
    def __init__(self, session: Session):
        super().__init__(session, User)
    
    def get_all(self, **filters) -> List[User]:
        """Ottiene tutte le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class).order_by(desc(User.id_user))
            
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
    
    def get_by_email(self, email: str) -> Optional[User]:
        """Ottiene un utente per email (case insensitive)"""
        try:
            return self._session.query(User).filter(
                func.lower(User.email) == func.lower(email)
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving user by email: {str(e)}")
    
    def get_by_username(self, username: str) -> Optional[User]:
        """Ottiene un utente per username"""
        try:
            return self._session.query(User).filter(
                func.lower(User.username) == func.lower(username)
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving user by username: {str(e)}")
