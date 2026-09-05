from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class TherapyMethodItem(BaseModel):
    type: str
    duration: int = Field(default=30, ge=1, le=120)


class TherapyParams(BaseModel):
    height: Optional[int] = Field(default=50, ge=0, le=100)
    speed: Optional[int] = Field(default=50, ge=0, le=100)
    intensity: Optional[int] = Field(default=3, ge=1, le=10)
    temperature: Optional[int] = Field(default=37, ge=30, le=45)


class TherapyMethodResponse(BaseModel):
    id: str
    name: str
    type: str
    description: Optional[str]
    default_duration: int

    class Config:
        from_attributes = True


class TherapySessionCreate(BaseModel):
    device_id: Optional[str] = None
    methods: List[TherapyMethodItem]
    params: Optional[TherapyParams] = None


class TherapySessionResponse(BaseModel):
    id: str
    user_id: str
    device_id: Optional[str]
    device_name: Optional[str]
    methods: Optional[str]
    params: Optional[str]
    status: str
    started_at: Optional[datetime]
    paused_at: Optional[datetime]
    resumed_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration: int
    total_duration: int
    created_at: datetime

    class Config:
        from_attributes = True


class TherapyStatusResponse(BaseModel):
    session_id: str
    status: str
    duration: int
    total_duration: int
