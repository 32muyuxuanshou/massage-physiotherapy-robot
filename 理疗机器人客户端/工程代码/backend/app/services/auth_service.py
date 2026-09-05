from datetime import timedelta
from typing import Optional
from sqlalchemy.orm import Session

from app.models.user import User
from app.crud.user_crud import user_crud
from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)


class AuthService:
    def authenticate_user(self, db: Session, phone: str, password: str) -> Optional[User]:
        user = user_crud.get_by_phone(db, phone)
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def create_tokens(self, user_id: str) -> dict:
        access_token = create_access_token(
            data={"sub": user_id},
            expires_delta=timedelta(minutes=60)
        )
        refresh_token = create_refresh_token(data={"sub": user_id})
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

    def refresh_access_token(self, refresh_token: str) -> Optional[dict]:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            return None
        user_id = payload.get("sub")
        if user_id is None:
            return None
        return self.create_tokens(user_id)


auth_service = AuthService()
