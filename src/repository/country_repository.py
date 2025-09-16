from typing import List, Type

from sqlalchemy import func, asc
from sqlalchemy.orm import Session
from .. import AllCountryResponseSchema, CountryResponseSchema, CountrySchema, Country
from ..models import Country
from src.services import QueryUtils


class CountryRepository:

    def __init__(self, session: Session):
        """
        Inizializza la repository con la sessione del DB

        Args:
            session (Session): Sessione del DB
        """
        self.session = session

    def get_all(self, page: int = 1, limit: int = 0) -> AllCountryResponseSchema:
        query = self.session.query(Country).order_by(asc(Country.name))
        if limit == 0:
            return query.all()
        query = query.offset(QueryUtils.get_offset(limit, page)).limit(limit)
        return query

    def list_all(self) -> list[CountryResponseSchema]:
        results = self.session.query(Country.id_country, Country.name).order_by(asc(Country.name)).all()
        return [{"id_country": id_country, "name": name} for id_country, name in results]

    def get_count(self) -> AllCountryResponseSchema:
        return self.session.query(func.count(Country.id_country)).scalar()

    def get_by_id(self, _id: int) -> CountryResponseSchema:
        return self.session.query(Country).filter(Country.id_country == _id).first()
    
    def get_by_origin_id(self, origin_id: str) -> Country:
        """Get country by origin ID"""
        return self.session.query(Country).filter(Country.id_origin == origin_id).first()

    def get_by_iso_code(self, iso_code: str) -> Country:
        """Get country by ISO code"""
        return self.session.query(Country).filter(Country.iso_code == iso_code).first()

    def create(self, data: CountrySchema):

        country = Country(**data.model_dump())

        self.session.add(country)
        self.session.commit()
        self.session.refresh(country)

    def update(self,
               edited_country: Country,
               data: CountrySchema):

        entity_updated = data.dict(exclude_unset=True)  # Esclude i campi non impostati

        # Set su ogni proprietà
        for key, value in entity_updated.items():
            if hasattr(edited_country, key) and value is not None:
                setattr(edited_category, key, value)

        self.session.add(entity_updated)
        self.session.commit()

    def delete(self, country: Country) -> bool:
        self.session.delete(country)
        self.session.commit()

        return True
