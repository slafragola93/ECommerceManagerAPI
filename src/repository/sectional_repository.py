from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import SectionalResponseSchema, SectionalSchema
from ..models import Sectional
from src.schemas.sectional_schema import *
from src.services import QueryUtils


class SectionalRepository:
    """
    Repository sezionale
    """

    def __init__(self, session: Session):
        """
        Inizializza la repository con la sessione del DB

        Args:
            session (Session): Sessione del DB
        """
        self.session = session

    def get_by_id(self, _id: int) -> SectionalResponseSchema:
        return self.session.query(Sectional).filter(Sectional.id_sectional == _id).first()

    def get_by_name(self, name: str) -> SectionalResponseSchema:
        return self.session.query(Sectional).filter(Sectional.name == name).first()

    def create(self, data: SectionalSchema):
        sectional = Sectional(**data.model_dump())

        if self.get_by_name(sectional.name) is not None:
            return

        self.session.add(sectional)
        self.session.commit()

    def create_and_get_id(self, data: SectionalSchema):
        sectional = Sectional(**data.model_dump())

        if self.get_by_name(sectional.name) is not None:
            return self.get_by_name(sectional.name).id_sectional

        self.session.add(sectional)
        self.session.commit()
        self.session.refresh(sectional)

        return sectional.id_sectional

    def update(self, edited_sectional: Sectional, data: SectionalSchema):

        entity_updated = data.dict(exclude_unset=True)  # Esclude i campi non impostati

        for key, value in entity_updated.items():
            if hasattr(edited_sectional, key) and value is not None:
                setattr(edited_sectional, key, value)

        self.session.add(edited_sectional)
        self.session.commit()

    def delete(self, sectional: Sectional) -> bool:
        self.session.delete(sectional)
        self.session.commit()

        return True
