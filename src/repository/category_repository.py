from sqlalchemy import func, desc, asc
from sqlalchemy.orm import Session
from .. import AllCategoryResponseSchema, CategoryResponseSchema, CategorySchema
from ..models import Category
from src.services import QueryUtils


class CategoryRepository:

    def __init__(self, session: Session):
        """
        Inizializza la repository con la sessione del DB

        Args:
            session (Session): Sessione del DB
        """
        self.session = session

    def get_all(self, page: int = 1, limit: int = 10) -> AllCategoryResponseSchema:
        return self.session.query(Category).order_by(desc(Category.id_category)).offset(
            QueryUtils.get_offset(limit, page)).limit(limit).all()

    def list_all(self) -> list[dict]:
        return self.session.query(Category).order_by(asc(Category.name)).all()

    def get_count(self) -> int:
        return self.session.query(func.count(Category.id_category)).scalar()

    def get_by_id(self, _id: int) -> CategoryResponseSchema:
        return self.session.query(Category).filter(Category.id_category == _id).first()
    
    def get_by_origin_id(self, origin_id: str) -> Category:
        """Get category by origin ID"""
        return self.session.query(Category).filter(Category.id_origin == origin_id).first()

    def bulk_create(self, data_list: list[CategorySchema], batch_size: int = 1000):
        """Bulk insert categories for better performance"""
        # Get existing origin IDs to avoid duplicates
        origin_ids = [str(data.id_origin) for data in data_list]
        existing_categories = self.session.query(Category).filter(Category.id_origin.in_(origin_ids)).all()
        existing_origin_ids = {str(category.id_origin) for category in existing_categories}
        
        # Filter out existing categories
        new_categories_data = [data for data in data_list if str(data.id_origin) not in existing_origin_ids]
        
        if not new_categories_data:
            return 0
        
        # Process in batches
        total_inserted = 0
        for i in range(0, len(new_categories_data), batch_size):
            batch = new_categories_data[i:i + batch_size]
            categories = []
            
            for data in batch:
                category = Category(**data.model_dump())
                categories.append(category)
            
            self.session.bulk_save_objects(categories)
            total_inserted += len(categories)
            
            # Commit every batch
            self.session.commit()
            
        return total_inserted

    def create(self, data: CategorySchema):

        category = Category(**data.model_dump())

        self.session.add(category)
        self.session.commit()
        self.session.refresh(category)

    def update(self,
               edited_category: Category,
               data: CategorySchema):

        entity_updated = data.dict(exclude_unset=True)  # Esclude i campi non impostati

        # Set su ogni proprietà
        for key, value in entity_updated.items():
            if hasattr(edited_category, key) and value is not None:
                setattr(edited_category, key, value)

        self.session.add(edited_category)
        self.session.commit()

    def delete(self, category: Category) -> bool:
        self.session.delete(category)
        self.session.commit()

        return True
