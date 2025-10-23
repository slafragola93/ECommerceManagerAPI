from typing import List
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.base_repository import BaseRepository
from src.models.shipment_document import ShipmentDocument
from src.repository.interfaces.shipment_document_repository_interface import IShipmentDocumentRepository


class ShipmentDocumentRepository(BaseRepository[ShipmentDocument, int], IShipmentDocumentRepository):
    """Repository for ShipmentDocument operations"""
    
    def __init__(self, session: Session):
        super().__init__(ShipmentDocument, session)
    
    def get_expired_documents(self) -> List[ShipmentDocument]:
        """Get all expired shipment documents"""
        now = datetime.utcnow()
        stmt = select(ShipmentDocument).where(ShipmentDocument.expires_at < now)
        result = self.session.execute(stmt)
        return result.scalars().all()
    
    def delete_by_id(self, document_id: int) -> bool:
        """Delete a shipment document by ID"""
        document = self.get_by_id(document_id)
        if document:
            self.session.delete(document)
            self.session.commit()
            return True
        return False

