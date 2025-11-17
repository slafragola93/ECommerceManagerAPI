"""
Interfaccia per PlatformStateTrigger Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List
from src.core.interfaces import IRepository
from src.models.platform_state_trigger import PlatformStateTrigger


class IPlatformStateTriggerRepository(IRepository[PlatformStateTrigger, int]):
    """Interface per la repository dei platform_state_trigger"""
    
    @abstractmethod
    def get_active_triggers_by_event(self, event_type: str, id_platform: int) -> List[PlatformStateTrigger]:
        """Ottiene tutti i trigger attivi per un evento e piattaforma specifici"""
        pass
    
    @abstractmethod
    def get_trigger_by_state(
        self, 
        event_type: str, 
        id_platform: int, 
        state_type: str,
        id_state_local: int
    ) -> Optional[PlatformStateTrigger]:
        """Ottiene un trigger specifico per evento, piattaforma, tipo stato e stato locale"""
        pass

