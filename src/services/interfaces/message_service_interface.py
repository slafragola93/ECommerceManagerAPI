"""
Interfaccia per Message Service seguendo ISP
"""
from abc import ABC, abstractmethod
from typing import List
from src.core.interfaces import IBaseService
from src.schemas.message_schema import MessageSchema, MessageResponseSchema
from src.models.message import Message

class IMessageService(IBaseService):
    """Interface per il servizio message"""
    
    @abstractmethod
    async def create_message(self, message_data: MessageSchema) -> Message:
        """Crea un nuovo message"""
        pass
    
    @abstractmethod
    async def update_message(self, message_id: int, message_data: MessageSchema) -> Message:
        """Aggiorna un message esistente"""
        pass
    
    @abstractmethod
    async def get_message(self, message_id: int) -> Message:
        """Ottiene un message per ID"""
        pass
    
    @abstractmethod
    async def get_messages(self, page: int = 1, limit: int = 10, **filters) -> List[Message]:
        """Ottiene la lista dei message con filtri"""
        pass
    
    @abstractmethod
    async def delete_message(self, message_id: int) -> bool:
        """Elimina un message"""
        pass
    
    @abstractmethod
    async def get_messages_count(self, **filters) -> int:
        """Ottiene il numero totale di message con filtri"""
        pass
