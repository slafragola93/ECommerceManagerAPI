from sqlalchemy import func, desc, asc
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

    def list_all(self):
        return self.session.query(Brand).order_by(asc(Brand.name)).all()

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
    
    def get_by_origin_id(self, origin_id: str) -> Brand:
        """Get brand by origin ID"""
        return self.session.query(Brand).filter(Brand.id_origin == origin_id).first()

    def bulk_create(self, data_list: list[BrandSchema], batch_size: int = 1000):
        """Bulk insert brands for better performance"""
        # Get existing origin IDs to avoid duplicates
        origin_ids = [str(data.id_origin) for data in data_list]
        existing_brands = self.session.query(Brand).filter(Brand.id_origin.in_(origin_ids)).all()
        existing_origin_ids = {str(brand.id_origin) for brand in existing_brands}
        
        # Filter out existing brands
        new_brands_data = [data for data in data_list if str(data.id_origin) not in existing_origin_ids]
        
        if not new_brands_data:
            return 0
        
        # Process in batches
        total_inserted = 0
        for i in range(0, len(new_brands_data), batch_size):
            batch = new_brands_data[i:i + batch_size]
            brands = []
            
            for data in batch:
                brand = Brand(**data.model_dump())
                brands.append(brand)
            
            self.session.bulk_save_objects(brands)
            total_inserted += len(brands)
            
            # Commit every batch
            self.session.commit()
            
        return total_inserted

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
