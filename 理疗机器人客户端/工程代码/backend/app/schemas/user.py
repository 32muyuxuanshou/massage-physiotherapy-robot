from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    phone: Optional[str] = None
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    height: Optional[int] = None
    weight: Optional[int] = None


class UserCreate(UserBase):
    phone: str = Field(..., min_length=11, max_length=11)
    password: str = Field(..., min_length=6)


class UserUpdate(BaseModel):
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    height: Optional[int] = None
    weight: Optional[int] = None


class UserResponse(UserBase):
    id: str
    phone: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserProfileResponse(UserResponse):
    pass
