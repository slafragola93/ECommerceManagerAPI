from sqlalchemy import Integer, Column, Text

from src import Base


class Message(Base):
    __tablename__ = "messages"

    id_message = Column(Integer, primary_key=True, index=True)
    id_user = Column(Integer, index=True, nullable=True)
    message = Column(Text)
