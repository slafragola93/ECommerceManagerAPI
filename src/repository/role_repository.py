from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..models import Role
from src.schemas.role_schema import *
from src.services import QueryUtils


class RoleRepository:
    """
    Repository ruoli
    """

    def __init__(self, session: Session):
        """
        Inizializza la repository con la sessione del DB

        Args:
            session (Session): Sessione del DB
        """
        self.session = session

    def get_all(self,
                page: int = 1, limit: int = 10
                ) -> AllRolesResponseSchema:
        """
        Recupera tutti i ruoli

        Returns:
            AllRoleResponseSchema: Tutti i ruoli
        """

        return self.session.query(Role).offset(QueryUtils.get_offset(limit, page)).limit(limit).all()

    def get_count(self) -> AllRolesResponseSchema:

        return self.session.query(func.count(Role.id_role)).scalar()

    def get_by_id(self, _id: int) -> RoleResponseSchema:
        return self.session.query(Role).filter(Role.id_role == _id).first()

    def create(self, data: RoleSchema):
        role = Role(**data.model_dump())

        self.session.add(role)
        self.session.commit()
        self.session.refresh(role)

    def update(self, edited_role: Role, data: RoleSchema):

        entity_updated = data.dict(exclude_unset=True)  # Esclude i campi non impostati

        for key, value in entity_updated.items():
            if hasattr(edited_role, key) and value is not None:
                setattr(edited_role, key, value)

        self.session.add(edited_role)
        self.session.commit()

    def delete(self, role: Role) -> bool:
        self.session.delete(role)
        self.session.commit()

        return True
