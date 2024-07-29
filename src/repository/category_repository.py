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
        return self.session.query(Category).order_by(desc(Category.id_category)).offset(QueryUtils.get_offset(limit, page)).limit(limit).all()
    def list_all(self):
        return self.session.query(Category).order_by(asc(Category.name)).all()

    def get_count(self) -> int:
        return self.session.query(func.count(Category.id_category)).scalar()

    def get_by_id(self, _id: int) -> CategoryResponseSchema:
        return self.session.query(Category).filter(Category.id_category == _id).first()

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
