from sqlalchemy import Column, String, Boolean, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class AICapture(Base):
    __tablename__ = "ai_captures"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    session_id = Column(String(36), ForeignKey("therapy_sessions.id"), nullable=True)
    image_path = Column(String(255), nullable=False)
    capture_time = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="ai_captures")
    analysis = relationship("AIAnalysis", back_populates="capture", uselist=False)


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    capture_id = Column(String(36), ForeignKey("ai_captures.id"), nullable=True)
    result = Column(Text, nullable=True)
    body_parts = Column(Text, nullable=True)
    pressure_level = Column(Integer, nullable=True)
    recommendations = Column(Text, nullable=True)
    status = Column(String(20), default="pending")
    analyzed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="ai_analyses")
    capture = relationship("AICapture", back_populates="analysis")
