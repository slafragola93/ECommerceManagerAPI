from sqlalchemy import or_
from sqlalchemy.orm import Session
from ..models import Message
from src.schemas.message_schema import *
from src.services import QueryUtils


class MessageRepository:
    """
    Repository messaggio
    """

    def __init__(self, session: Session):
        """
        Inizializza la repository con la sessione del DB

        Args:
            session (Session): Sessione del DB
        """
        self.session = session

    def get_all(self,
                user_id: int = None,
                page: int = 1, limit: int = 10
                ) -> CurrentMessagesResponseSchema:
        """
        Recupera tutti i messaggi disponibili

        Returns:
            AllMessagesResponseSchema: Tutte i messaggi disponibili
        """
        query = self.session.query(Message)

        if user_id is not None:
            query = query.filter(or_(Message.id_user == user_id))

        messages = query.offset(QueryUtils.get_offset(limit, page)).limit(limit).all()

        return messages

    def get_by_id(self, _id: int) -> MessageResponseSchema:
        return self.session.query(Message).filter(Message.id_message == _id).first()

    def get_by_id_user(self, _id: int, generic: bool = True) -> AllMessagesResponseSchema:
        if generic:
            messages = self.session.query(Message).filter(or_(Message.id_user == _id, Message.id_user == None)).all()
        else:
            messages = self.session.query(Message).filter(Message.id_user == _id).all()
        return messages

    def create(self, data: MessageSchema):
        message = Message(**data.model_dump())

        self.session.add(message)
        self.session.commit()
        self.session.refresh(message)

    def update(self, edited_message: Message, data: MessageSchema):

        entity_updated = data.dict(exclude_unset=True)

        for key, value in entity_updated.items():
            if hasattr(edited_message, key) and value is not None:
                setattr(edited_message, key, value)

        self.session.add(edited_message)
        self.session.commit()

    def delete(self, message: Message) -> bool:
        self.session.delete(message)
        self.session.commit()

        return True
