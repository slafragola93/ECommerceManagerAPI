from pydantic import BaseModel
from sqlalchemy import Column, Integer


class OrderHistorySchema(BaseModel):
    id_order = Column(Integer)
    id_order_state = Column(Integer)

