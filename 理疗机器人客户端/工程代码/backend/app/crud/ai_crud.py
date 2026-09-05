from typing import Optional
from sqlalchemy.orm import Session
import json

from app.models.ai import AICapture, AIAnalysis
from app.crud.base import CRUDBase


class AICaptureCRUD(CRUDBase[AICapture]):
    def create_capture(self, db: Session, user_id: str, image_path: str, session_id: str = None) -> AICapture:
        import uuid
        capture = AICapture(
            id=str(uuid.uuid4()),
            user_id=user_id,
            session_id=session_id,
            image_path=image_path
        )
        db.add(capture)
        db.commit()
        db.refresh(capture)
        return capture

    def get_by_user(self, db: Session, user_id: str, limit: int = 20):
        return db.query(AICapture).filter(
            AICapture.user_id == user_id
        ).order_by(AICapture.capture_time.desc()).limit(limit).all()


class AIAnalysisCRUD(CRUDBase[AIAnalysis]):
    def create_analysis(
        self,
        db: Session,
        user_id: str,
        capture_id: str = None,
        result: str = None,
        body_parts: str = None,
        pressure_level: int = None,
        recommendations: str = None
    ) -> AIAnalysis:
        import uuid
        from datetime import datetime
        analysis = AIAnalysis(
            id=str(uuid.uuid4()),
            user_id=user_id,
            capture_id=capture_id,
            result=result,
            body_parts=body_parts,
            pressure_level=pressure_level,
            recommendations=recommendations,
            status="completed" if result else "pending",
            analyzed_at=datetime.utcnow() if result else None
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        return analysis

    def get_by_user(self, db: Session, user_id: str, limit: int = 20):
        return db.query(AIAnalysis).filter(
            AIAnalysis.user_id == user_id
        ).order_by(AIAnalysis.created_at.desc()).limit(limit).all()


ai_capture_crud = AICaptureCRUD(AICapture)
ai_analysis_crud = AIAnalysisCRUD(AIAnalysis)
