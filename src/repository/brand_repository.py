from sqlalchemy import func, desc
from sqlalchemy.orm import Session
from ..models import Brand
from src.schemas.brand_schema import *
from src.services import QueryUtils


class BrandRepository:
    """Repository brand"""

    def __init__(self, session: Session):
        """
        Inizializza la repository con la sessione del DB

        Args:
            session (Session): Sessione del DB
        """
        self.session = session

    def get_all(self, page: int = 1, limit: int = 10) -> AllBrandsResponseSchema:
        """
        Recupera tutti i brands

        Returns:
            AllBrandsResponseSchema: Tutti i brand
        """
        return self.session.query(Brand).order_by(desc(Brand.id_brand)).offset(QueryUtils.get_offset(limit, page)).limit(limit).all()

    def get_count(self):
        return self.session.query(func.count(Brand.id_brand)).scalar()

    def get_by_id(self, _id: int) -> BrandResponseSchema:
        """
        Ottieni brand per ID

        Args:
            _id (int):  ID Brand.

        Returns:
            BrandResponseSchema: Istanza del brand
        """
        return self.session.query(Brand).filter(Brand.id_brand == _id).first()

    def create(self, data: BrandSchema):

        brand = Brand(**data.model_dump())

        self.session.add(brand)
        self.session.commit()
        self.session.refresh(brand)

    def update(self,
               edited_brand: Brand,
               data: BrandSchema):

        entity_updated = data.dict(exclude_unset=True)  # Esclude i campi non impostati

        # Set su ogni proprietà
        for key, value in entity_updated.items():
            if hasattr(edited_brand, key) and value is not None:
                setattr(edited_brand, key, value)

        self.session.add(edited_brand)
        self.session.commit()

    def delete(self, brand: Brand) -> bool:
        self.session.delete(brand)
        self.session.commit()

        return True
