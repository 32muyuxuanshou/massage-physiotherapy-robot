from typing import Optional
from sqlalchemy.orm import Session

from app.models.user import User
from app.crud.user_crud import user_crud


class UserService:
    def get_user_by_id(self, db: Session, user_id: str) -> Optional[User]:
        return user_crud.get(db, user_id)

    def get_user_by_phone(self, db: Session, phone: str) -> Optional[User]:
        return user_crud.get_by_phone(db, phone)

    def update_user(self, db: Session, user_id: str, user_data: dict) -> Optional[User]:
        return user_crud.update(db, user_id, user_data)


user_service = UserService()
