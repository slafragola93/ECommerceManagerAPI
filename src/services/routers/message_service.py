"""
Message Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any
from src.services.interfaces.message_service_interface import IMessageService
from src.repository.interfaces.message_repository_interface import IMessageRepository
from src.schemas.message_schema import MessageSchema
from src.models.message import Message
from src.core.exceptions import (
    ValidationException, 
    NotFoundException, 
    BusinessRuleException,
    ExceptionFactory,
    ErrorCode
)

class MessageService(IMessageService):
    """Message Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""
    
    def __init__(self, message_repository: IMessageRepository):
        self._message_repository = message_repository
    
    async def create_message(self, message_data: MessageSchema) -> Message:
        """Crea un nuovo message con validazioni business"""
        
        # Business Rule 1: Nome deve essere unico
        if hasattr(message_data, 'name') and message_data.name:
            existing_message = self._message_repository.get_by_name(message_data.name)
            if existing_message:
                raise BusinessRuleException(
                    f"Message with name '{message_data.name}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": message_data.name}
                )
        
        # Crea il message
        try:
            message = Message(**message_data.model_dump())
            message = self._message_repository.create(message)
            return message
        except Exception as e:
            raise ValidationException(f"Error creating message: {str(e)}")
    
    async def update_message(self, message_id: int, message_data: MessageSchema) -> Message:
        """Aggiorna un message esistente"""
        
        # Verifica esistenza
        message = self._message_repository.get_by_id_or_raise(message_id)
        
        # Business Rule: Se nome cambia, deve essere unico
        if hasattr(message_data, 'name') and message_data.name != message.name:
            existing = self._message_repository.get_by_name(message_data.name)
            if existing and existing.id_message != message_id:
                raise BusinessRuleException(
                    f"Message with name '{message_data.name}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": message_data.name}
                )
        
        # Aggiorna il message
        try:
            # Aggiorna i campi
            for field_name, value in message_data.model_dump(exclude_unset=True).items():
                if hasattr(message, field_name) and value is not None:
                    setattr(message, field_name, value)
            
            updated_message = self._message_repository.update(message)
            return updated_message
        except Exception as e:
            raise ValidationException(f"Error updating message: {str(e)}")
    
    async def get_message(self, message_id: int) -> Message:
        """Ottiene un message per ID"""
        message = self._message_repository.get_by_id_or_raise(message_id)
        return message
    
    async def get_messages(self, page: int = 1, limit: int = 10, **filters) -> List[Message]:
        """Ottiene la lista dei message con filtri"""
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
            messages = self._message_repository.get_all(**filters)
            
            return messages
        except Exception as e:
            raise ValidationException(f"Error retrieving messages: {str(e)}")
    
    async def delete_message(self, message_id: int) -> bool:
        """Elimina un message"""
        # Verifica esistenza
        self._message_repository.get_by_id_or_raise(message_id)
        
        try:
            return self._message_repository.delete(message_id)
        except Exception as e:
            raise ValidationException(f"Error deleting message: {str(e)}")
    
    async def get_messages_count(self, **filters) -> int:
        """Ottiene il numero totale di message con filtri"""
        try:
            # Usa il repository con i filtri
            return self._message_repository.get_count(**filters)
        except Exception as e:
            raise ValidationException(f"Error counting messages: {str(e)}")
    
    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business per Message"""
        # Validazioni specifiche per Message se necessarie
        pass
