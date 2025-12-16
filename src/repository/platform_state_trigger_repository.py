"""
PlatformStateTrigger Repository rifattorizzato seguendo SOLID
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_
from src.models.platform_state_trigger import PlatformStateTrigger
from src.repository.interfaces.platform_state_trigger_repository_interface import IPlatformStateTriggerRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException


class PlatformStateTriggerRepository(BaseRepository[PlatformStateTrigger, int], IPlatformStateTriggerRepository):
    """PlatformStateTrigger Repository rifattorizzato seguendo SOLID"""
    
    def __init__(self, session: Session):
        super().__init__(session, PlatformStateTrigger)
    
    def get_active_triggers_by_event(self, event_type: str, id_store: int) -> List[PlatformStateTrigger]:
        """Ottiene tutti i trigger attivi per un evento e store specifici"""
        try:
            return self._session.query(PlatformStateTrigger).filter(
                and_(
                    PlatformStateTrigger.event_type == event_type,
                    PlatformStateTrigger.id_store == id_store,
                    PlatformStateTrigger.is_active == True
                )
            ).all()
        except Exception as e:
            raise InfrastructureException(
                f"Database error retrieving active triggers for event {event_type} and store {id_store}: {str(e)}"
            )
    
    def get_trigger_by_state(
        self, 
        event_type: str, 
        id_store: int, 
        state_type: str,
        id_state_local: int
    ) -> Optional[PlatformStateTrigger]:
        """Ottiene un trigger specifico per evento, store, tipo stato e stato locale"""
        try:
            return self._session.query(PlatformStateTrigger).filter(
                and_(
                    PlatformStateTrigger.event_type == event_type,
                    PlatformStateTrigger.id_store == id_store,
                    PlatformStateTrigger.state_type == state_type,
                    PlatformStateTrigger.id_state_local == id_state_local,
                    PlatformStateTrigger.is_active == True
                )
            ).first()
        except Exception as e:
            raise InfrastructureException(
                f"Database error retrieving trigger for event {event_type}, store {id_store}, "
                f"state_type {state_type}, state_local {id_state_local}: {str(e)}"
            )

