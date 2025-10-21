"""
User Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any
from src.services.interfaces.user_service_interface import IUserService
from src.repository.interfaces.user_repository_interface import IUserRepository
from src.schemas.user_schema import UserSchema, UserResponseSchema
from src.models.user import User
from src.core.exceptions import (
    ValidationException, 
    NotFoundException, 
    BusinessRuleException,
    ExceptionFactory,
    ErrorCode
)
import re

class UserService(IUserService):
    """User Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""
    
    def __init__(self, user_repository: IUserRepository):
        self._user_repository = user_repository
    
    async def create_user(self, user_data: UserSchema) -> User:
        """Crea un nuovo utente con validazioni business"""
        
        # Business Rule 1: Validazione email
        await self._validate_email(user_data.email)
        
        # Business Rule 2: Email deve essere unica
        existing_user = self._user_repository.get_by_email(user_data.email)
        if existing_user:
            raise ExceptionFactory.email_duplicate(user_data.email)
        
        # Business Rule 3: Username deve essere unico
        if hasattr(user_data, 'username') and user_data.username:
            existing_username = self._user_repository.get_by_username(user_data.username)
            if existing_username:
                raise BusinessRuleException(
                    f"Utente con username '{user_data.username}' già esistente",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"username": user_data.username}
                )
        
        # Crea l'utente
        try:
            user = User(**user_data.dict())
            user = self._user_repository.create(user)
            return user
        except Exception as e:
            raise ValidationException(f"Errore nella creazione dell'utente: {str(e)}")
    
    async def update_user(self, user_id: int, user_data: UserSchema) -> User:
        """Aggiorna un utente esistente"""
        
        # Verifica esistenza
        user = self._user_repository.get_by_id_or_raise(user_id)
        
        # Business Rule: Se email cambia, deve essere unica
        if hasattr(user_data, 'email') and user_data.email != user.email:
            await self._validate_email(user_data.email)
            existing = self._user_repository.get_by_email(user_data.email)
            if existing and existing.id_user != user_id:
                raise ExceptionFactory.email_duplicate(user_data.email)
        
        # Aggiorna l'utente
        try:
            # Aggiorna i campi
            for field_name, value in user_data.dict(exclude_unset=True).items():
                if hasattr(user, field_name) and value is not None:
                    setattr(user, field_name, value)
            
            updated_user = self._user_repository.update(user)
            return updated_user
        except Exception as e:
            raise ValidationException(f"Errore nell'aggiornamento dell'utente: {str(e)}")
    
    async def get_user(self, user_id: int) -> User:
        """Ottiene un utente per ID"""
        user = self._user_repository.get_by_id_or_raise(user_id)
        return user
    
    async def get_users(self, page: int = 1, limit: int = 10, **filters) -> List[User]:
        """Ottiene la lista degli utenti con filtri"""
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
            users = self._user_repository.get_all(**filters)
            
            return users
        except Exception as e:
            raise ValidationException(f"Errore nel recupero degli utenti: {str(e)}")
    
    async def delete_user(self, user_id: int) -> bool:
        """Elimina un utente"""
        # Verifica esistenza
        self._user_repository.get_by_id_or_raise(user_id)
        
        try:
            return self._user_repository.delete(user_id)
        except Exception as e:
            raise ValidationException(f"Errore nell'eliminazione dell'utente: {str(e)}")
    
    async def get_users_count(self, **filters) -> int:
        """Ottiene il numero totale di utenti con filtri"""
        try:
            # Usa il repository con i filtri
            return self._user_repository.get_count(**filters)
        except Exception as e:
            raise ValidationException(f"Errore nel conteggio degli utenti: {str(e)}")
    
    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business per User"""
        if hasattr(data, 'email'):
            await self._validate_email(data.email)
    
    async def _validate_email(self, email: str) -> None:
        """Valida il formato dell'email"""
        if not email:
            raise ExceptionFactory.required_field_missing("email")
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            raise ExceptionFactory.invalid_email_format(email)
