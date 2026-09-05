from typing import Optional
from sqlalchemy.orm import Session

from app.models.user import User
from app.crud.base import CRUDBase
from app.core.security import get_password_hash


class UserCRUD(CRUDBase[User]):
    def get_by_phone(self, db: Session, phone: str) -> Optional[User]:
        return db.query(User).filter(User.phone == phone).first()

    def create(self, db: Session, phone: str, password: str, **kwargs) -> User:
        user_data = {
            "id": self._generate_id(),
            "phone": phone,
            "password_hash": get_password_hash(password),
            **kwargs
        }
        return super().create(db, user_data)

    def update(self, db: Session, id: str, obj_in: dict) -> Optional[User]:
        if "password" in obj_in:
            obj_in["password_hash"] = get_password_hash(obj_in.pop("password"))
        return super().update(db, id, obj_in)

    def _generate_id(self) -> str:
        import uuid
        return str(uuid.uuid4())


user_crud = UserCRUD(User)
