from typing import Optional, List
from sqlalchemy.orm import Session
import json
import random

from app.models.ai import AICapture, AIAnalysis
from app.crud.ai_crud import ai_capture_crud, ai_analysis_crud


class AIService:
    def create_capture(self, db: Session, user_id: str, image_path: str, session_id: str = None) -> AICapture:
        return ai_capture_crud.create_capture(db, user_id, image_path, session_id)

    def get_capture(self, db: Session, capture_id: str) -> Optional[AICapture]:
        return ai_capture_crud.get(db, capture_id)

    def get_user_captures(self, db: Session, user_id: str, limit: int = 20) -> List[AICapture]:
        return ai_capture_crud.get_by_user(db, user_id, limit)

    def create_analysis(self, db: Session, user_id: str, capture_id: str) -> AIAnalysis:
        capture = ai_capture_crud.get(db, capture_id)
        if not capture:
            return None
        
        result = self._mock_analyze(image_path=capture.image_path)
        
        return ai_analysis_crud.create_analysis(
            db,
            user_id=user_id,
            capture_id=capture_id,
            result=result["result"],
            body_parts=json.dumps(result["body_parts"]),
            pressure_level=result["pressure_level"],
            recommendations=result["recommendations"]
        )

    def get_analysis(self, db: Session, analysis_id: str) -> Optional[AIAnalysis]:
        return ai_analysis_crud.get(db, analysis_id)

    def get_user_analyses(self, db: Session, user_id: str, limit: int = 20) -> List[AIAnalysis]:
        return ai_analysis_crud.get_by_user(db, user_id, limit)

    def _mock_analyze(self, image_path: str) -> dict:
        body_parts = ["腰部", "背部", "颈部"]
        return {
            "result": "理疗效果良好，肌肉紧张程度明显改善",
            "body_parts": body_parts,
            "pressure_level": random.randint(3, 7),
            "recommendations": "建议继续保持规律理疗，每次30分钟，每周2-3次"
        }


ai_service = AIService()
