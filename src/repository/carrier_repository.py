from http.client import HTTPException

from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from .. import AllCarriersResponseSchema, CarrierResponseSchema, CarrierSchema
from ..models import Carrier
from src.schemas.brand_schema import *
from src.services import QueryUtils


class CarrierRepository:
    """Repository brand"""

    def __init__(self, session: Session):
        """
        Inizializza la repository con la sessione del DB

        Args:
            session (Session): Sessione del DB
        """
        self.session = session

    def get_all(self,
                carriers_ids: Optional[str] = None,
                origin_ids: Optional[str] = None,
                carrier_name: Optional[str] = None,
                page: int = 1, limit: int = 10) -> AllCarriersResponseSchema:
        """
        Recupera tutti i corrieri salvati nel gestionale

        Returns:
            AllBrandsResponseSchema: Tutti i brand
        """
        query = self.session.query(Carrier).order_by(desc(Carrier.id_carrier))

        try:
            query = QueryUtils.filter_by_id(query, Carrier, 'id_carrier', carriers_ids)
            query = QueryUtils.filter_by_id(query, Carrier, 'id_origin', origin_ids)

            query = QueryUtils.filter_by_string(query, Carrier, 'name', carrier_name)

        except ValueError:
            raise HTTPException(status_code=400, detail="Parametri di ricerca non validi")

        return query.offset(QueryUtils.get_offset(limit, page)).limit(limit).all()

    def get_count(self,
                  carriers_ids: Optional[str] = None,
                  origin_ids: Optional[str] = None,
                  carrier_name: Optional[str] = None) -> int:

        query = self.session.query(func.count(Carrier.id_carrier))

        try:
            query = QueryUtils.filter_by_id(query, Carrier, 'id_carrier', carriers_ids)
            query = QueryUtils.filter_by_id(query, Carrier, 'id_origin', origin_ids)

            query = QueryUtils.filter_by_string(query, Carrier, 'name', carrier_name)

        except ValueError:
            raise HTTPException(status_code=400, detail="Parametri di ricerca non validi")

        total_count = query.scalar()

        return total_count

    def get_by_id(self, _id: int) -> CarrierResponseSchema:
        """
        Ottieni brand per ID

        Args:
            _id (int):  ID Brand.

        Returns:
            BrandResponseSchema: Istanza del brand
        """
        return self.session.query(Carrier).filter(Carrier.id_carrier == _id).first()

    def create(self, data: BrandSchema):

        carrier = Carrier(**data.model_dump())

        self.session.add(carrier)
        self.session.commit()
        self.session.refresh(carrier)

    def update(self,
               edited_carrier: Carrier,
               data: CarrierSchema):

        entity_updated = data.dict(exclude_unset=True)  # Esclude i campi non impostati

        # Set su ogni proprietà
        for key, value in entity_updated.items():
            if hasattr(edited_carrier, key) and value is not None:
                setattr(edited_carrier, key, value)

        self.session.add(edited_carrier)
        self.session.commit()

    def delete(self, carrier: Carrier) -> bool:
        self.session.delete(carrier)
        self.session.commit()

        return True
