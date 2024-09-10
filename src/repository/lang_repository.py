from sqlalchemy import asc
from sqlalchemy.orm import Session
from ..models import Lang
from src.schemas.lang_schema import *
from src.services import QueryUtils


class LangRepository:
    """
    Repository lingue
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
                ) -> AllLangsResponseSchema:
        """
        Recupera tutti le lingue disponibili

        Returns:
            AllLangsResponseSchema: Tutte le lingue
        """
        return self.session.query(Lang).offset(QueryUtils.get_offset(limit, page)).limit(limit).all()

    def get_by_id(self, _id: int) -> LangResponseSchema:
        return self.session.query(Lang).filter(Lang.id_lang == _id).first()

    def create(self, data: LangSchema):
        lang = Lang(**data.model_dump())

        self.session.add(lang)
        self.session.commit()
        self.session.refresh(lang)

    def update(self, edited_lang: Lang, data: LangSchema):

        entity_updated = data.dict(exclude_unset=True)

        for key, value in entity_updated.items():
            if hasattr(edited_lang, key) and value is not None:
                setattr(edited_lang, key, value)

        self.session.add(edited_lang)
        self.session.commit()

    def delete(self, lang: Lang) -> bool:
        self.session.delete(lang)
        self.session.commit()

        return True
