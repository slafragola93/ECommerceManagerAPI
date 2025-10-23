from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from src.core.base_repository import BaseRepository
from src.models.shipment_request import ShipmentRequest
from src.repository.interfaces.shipment_request_repository_interface import IShipmentRequestRepository


class ShipmentRequestRepository(BaseRepository[ShipmentRequest, int], IShipmentRequestRepository):
    """Repository for ShipmentRequest operations"""
    
    def __init__(self, session: Session):
        super().__init__(ShipmentRequest, session)
    
    def get_by_message_reference(self, message_ref: str) -> Optional[ShipmentRequest]:
        """Get shipment request by message reference for idempotency check"""
        stmt = select(ShipmentRequest).where(ShipmentRequest.message_reference == message_ref)
        return self.session.execute(stmt).scalar_one_or_none()
    
    def cleanup_expired(self) -> int:
        """Remove expired shipment request records and return count of deleted records"""
        now = datetime.utcnow()
        stmt = delete(ShipmentRequest).where(ShipmentRequest.expires_at < now)
        result = self.session.execute(stmt)
        self.session.commit()
        return result.rowcount
