from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AICaptureRequest(BaseModel):
    session_id: Optional[str] = None


class AICaptureResponse(BaseModel):
    id: str
    user_id: str
    session_id: Optional[str]
    image_path: str
    capture_time: datetime

    class Config:
        from_attributes = True


class AIAnalysisRequest(BaseModel):
    capture_id: str


class AIAnalysisResponse(BaseModel):
    id: str
    user_id: str
    capture_id: Optional[str]
    result: Optional[str]
    body_parts: Optional[str]
    pressure_level: Optional[int]
    recommendations: Optional[str]
    status: str
    analyzed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True
