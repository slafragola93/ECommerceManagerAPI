"""
Interfaccia per Message Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List
from src.core.interfaces import IRepository
from src.models.message import Message

class IMessageRepository(IRepository[Message, int]):
    """Interface per la repository dei message"""
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Message]:
        """Ottiene un message per nome"""
        pass
