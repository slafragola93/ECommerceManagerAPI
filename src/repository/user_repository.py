from sqlalchemy import func
from sqlalchemy.orm import Session
from ..models import User
from src.schemas.user_schema import *
from src.services import QueryUtils


class UserRepository:

    def __init__(self, session: Session):
        self.session = session

    def get_all(self, page: int = 1, limit: int = 10) -> AllUsersResponseSchema:

        return self.session.query(User).offset(QueryUtils.get_offset(limit, page)).limit(limit).all()

    def get_count(self) -> int:

        return self.session.query(func.count(User.id_user)).scalar()

    def get_by_id(self, _id: int) -> UserResponseSchema:

        return self.session.query(User).filter(User.id_user == _id).first()

    def create(self, data: UserSchema):

        carrier = User(**data.model_dump())

        self.session.add(carrier)
        self.session.commit()
        self.session.refresh(carrier)

    def update(self,
               edited_user: User,
               data: UserSchema):

        entity_updated = data.dict(exclude_unset=True)

        # Set su ogni proprietà
        for key, value in entity_updated.items():
            if hasattr(edited_user, key) and value is not None:
                setattr(edited_user, key, value)

        self.session.add(edited_user)
        self.session.commit()

    def delete(self, user: User) -> bool:
        self.session.delete(user)
        self.session.commit()

        return True

    @staticmethod
    def formatted_output(user: User):
        return {
            "id_user": user.id_user,
            "username": user.username,
            "email": user.email,
            "roles": [RoleResponseSchema],
            "date_add": user.date_add,
        }
