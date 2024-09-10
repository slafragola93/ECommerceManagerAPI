from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..models import CarrierApi
from src.schemas.carrier_api_schema import *
from src.services import QueryUtils


class CarrierApiRepository:
    """Repository corrieri API"""

    def __init__(self, session: Session):
        """
        Inizializza la repository con la sessione del DB

        Args:
            session (Session): Sessione del DB
        """
        self.session = session

    def get_all(self, page: int = 1, limit: int = 10) -> AllCarriersApiResponseSchema:
        """
        Recupera tutti i corrieri API

        Returns:
            AllCarriersApiResponseSchema: Tutti i corrieri API
        """

        return self.session.query(CarrierApi).offset(QueryUtils.get_offset(limit, page)).limit(limit).all()

    def get_count(self) -> int:

        return self.session.query(func.count(CarrierApi.id_carrier_api)).scalar()


    def get_by_id(self, _id: int) -> CarrierApiResponseSchema:
        """
        Ottieni corriere per ID

        Args:
            _id (int): Indirizzo ID.

        Returns:
            AddressResponseSchema: Istanza dell'indirizzo.
        """
        return self.session.query(CarrierApi).filter(CarrierApi.id_carrier_api == _id).first()

    def create(self, data: CarrierApiSchema):

        carrier = CarrierApi(**data.model_dump())

        self.session.add(carrier)
        self.session.commit()
        self.session.refresh(carrier)

    def update(self,
               edited_carrier: CarrierApi,
               data: CarrierApiSchema):

        entity_updated = data.dict(exclude_unset=True)  # Esclude i campi non impostati

        # Set su ogni proprietà
        for key, value in entity_updated.items():
            if hasattr(edited_carrier, key) and value is not None:
                setattr(edited_carrier, key, value)

        self.session.add(edited_carrier)
        self.session.commit()

    def delete(self, carrier_api: CarrierApi) -> bool:
        self.session.delete(carrier_api)
        self.session.commit()

        return True

