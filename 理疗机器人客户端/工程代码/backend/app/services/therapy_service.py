from typing import Optional, List
from sqlalchemy.orm import Session
import json

from app.models.therapy import TherapyMethod, TherapySession
from app.crud.therapy_crud import therapy_method_crud, therapy_session_crud


class TherapyService:
    def get_all_methods(self, db: Session) -> List[TherapyMethod]:
        return therapy_method_crud.get_active_methods(db)

    def get_method_by_id(self, db: Session, method_id: str) -> Optional[TherapyMethod]:
        return therapy_method_crud.get(db, method_id)

    def create_session(
        self,
        db: Session,
        user_id: str,
        device_id: str = None,
        device_name: str = None,
        methods: list = None,
        params: dict = None
    ) -> TherapySession:
        return therapy_session_crud.create_session(
            db, user_id, device_id, device_name, methods, params
        )

    def get_session(self, db: Session, session_id: str) -> Optional[TherapySession]:
        return therapy_session_crud.get(db, session_id)

    def start_session(self, db: Session, session_id: str) -> Optional[TherapySession]:
        return therapy_session_crud.start_session(db, session_id)

    def pause_session(self, db: Session, session_id: str) -> Optional[TherapySession]:
        return therapy_session_crud.pause_session(db, session_id)

    def resume_session(self, db: Session, session_id: str) -> Optional[TherapySession]:
        return therapy_session_crud.resume_session(db, session_id)

    def stop_session(self, db: Session, session_id: str) -> Optional[TherapySession]:
        return therapy_session_crud.stop_session(db, session_id)

    def get_user_sessions(self, db: Session, user_id: str, limit: int = 20) -> List[TherapySession]:
        return therapy_session_crud.get_user_sessions(db, user_id, limit)

    def get_session_status(self, db: Session, session_id: str) -> Optional[dict]:
        session = therapy_session_crud.get(db, session_id)
        if session:
            return {
                "session_id": session.id,
                "status": session.status,
                "duration": session.duration,
                "total_duration": session.total_duration
            }
        return None


therapy_service = TherapyService()
