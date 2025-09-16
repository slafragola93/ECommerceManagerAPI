from sqlalchemy import func
from sqlalchemy.orm import Session
from ..models import Tag
from src.schemas.tag_schema import *
from src.services import QueryUtils


class TagRepository:

    def __init__(self, session: Session):
        self.session = session

    def get_all(self, page: int = 1, limit: int = 10) -> AllTagsResponseSchema:
        return self.session.query(Tag).offset(QueryUtils.get_offset(limit, page)).limit(limit).all()

    def get_count(self):
        return self.session.query(func.count(Tag.id_tag)).scalar()

    def get_by_id(self, _id: int) -> TagResponseSchema:
        return self.session.query(Tag).filter(Tag.id_tag == _id).first()
    
    def get_by_name(self, name: str) -> Tag:
        """Get tag by name"""
        return self.session.query(Tag).filter(Tag.name == name).first()

    def get_by_origin_id(self, origin_id: str) -> Tag:
        """Get tag by origin ID"""
        return self.session.query(Tag).filter(Tag.id_origin == origin_id).first()

    def create(self, name: str, id_origin: int = 0):
        """Create a new tag"""
        tag = Tag(name=name, id_origin=id_origin)
        self.session.add(tag)
        self.session.commit()
        self.session.refresh(tag)
        return tag

    def update(self,
               edited_tag: Tag,
               data: TagSchema):

        entity_updated = data.dict(exclude_unset=True)  # Esclude i campi non impostati

        # Set su ogni proprietà
        for key, value in entity_updated.items():
            if hasattr(edited_tag, key) and value is not None:
                setattr(edited_tag, key, value)

        self.session.add(edited_tag)
        self.session.commit()

    def delete(self, tag: Tag) -> bool:
        self.session.delete(tag)
        self.session.commit()

        return True
