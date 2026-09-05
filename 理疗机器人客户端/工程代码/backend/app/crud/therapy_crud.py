from typing import Optional, List
from sqlalchemy.orm import Session
import json

from app.models.therapy import TherapyMethod, TherapySession
from app.crud.base import CRUDBase


class TherapyMethodCRUD(CRUDBase[TherapyMethod]):
    def get_active_methods(self, db: Session) -> List[TherapyMethod]:
        return db.query(TherapyMethod).filter(TherapyMethod.is_active == True).all()


class TherapySessionCRUD(CRUDBase[TherapySession]):
    def create_session(
        self,
        db: Session,
        user_id: str,
        device_id: str = None,
        device_name: str = None,
        methods: list = None,
        params: dict = None
    ) -> TherapySession:
        import uuid
        session = TherapySession(
            id=str(uuid.uuid4()),
            user_id=user_id,
            device_id=device_id,
            device_name=device_name,
            methods=json.dumps(methods) if methods else None,
            params=json.dumps(params) if params else None,
            status="pending",
            total_duration=sum(m.get("duration", 30) for m in (methods or []))
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def start_session(self, db: Session, session_id: str) -> Optional[TherapySession]:
        from datetime import datetime
        session = self.get(db, session_id)
        if session:
            session.status = "running"
            session.started_at = datetime.utcnow()
            db.commit()
            db.refresh(session)
        return session

    def pause_session(self, db: Session, session_id: str) -> Optional[TherapySession]:
        from datetime import datetime
        session = self.get(db, session_id)
        if session and session.status == "running":
            session.status = "paused"
            session.paused_at = datetime.utcnow()
            if session.started_at and session.paused_at:
                session.duration = int((session.paused_at - session.started_at).total_seconds())
            db.commit()
            db.refresh(session)
        return session

    def resume_session(self, db: Session, session_id: str) -> Optional[TherapySession]:
        from datetime import datetime
        session = self.get(db, session_id)
        if session and session.status == "paused":
            session.status = "running"
            session.resumed_at = datetime.utcnow()
            db.commit()
            db.refresh(session)
        return session

    def stop_session(self, db: Session, session_id: str) -> Optional[TherapySession]:
        from datetime import datetime
        session = self.get(db, session_id)
        if session:
            session.status = "completed"
            session.completed_at = datetime.utcnow()
            if session.started_at and session.completed_at:
                session.duration = int((session.completed_at - session.started_at).total_seconds())
            db.commit()
            db.refresh(session)
        return session

    def get_user_sessions(self, db: Session, user_id: str, limit: int = 20) -> List[TherapySession]:
        return db.query(TherapySession).filter(
            TherapySession.user_id == user_id
        ).order_by(TherapySession.created_at.desc()).limit(limit).all()


therapy_method_crud = TherapyMethodCRUD(TherapyMethod)
therapy_session_crud = TherapySessionCRUD(TherapySession)
