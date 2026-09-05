from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.therapy import (
    TherapyMethodResponse,
    TherapySessionCreate,
    TherapySessionResponse,
    TherapyStatusResponse,
)
from app.models.user import User
from app.services.therapy_service import therapy_service
from app.core.security import get_current_user


router = APIRouter(prefix="/therapy", tags=["理疗"])


@router.get("/methods", response_model=List[TherapyMethodResponse])
def get_therapy_methods(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return therapy_service.get_all_methods(db)


@router.post("/sessions", response_model=TherapySessionResponse)
def create_session(
    session_create: TherapySessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    device_id = session_create.device_id
    device_name = None
    if device_id:
        device = therapy_service.get_all_methods(db)
        device_name = None
    
    methods = [m.model_dump() for m in session_create.methods]
    params = session_create.params.model_dump() if session_create.params else None
    
    session = therapy_service.create_session(
        db,
        user_id=current_user.id,
        device_id=device_id,
        device_name=device_name,
        methods=methods,
        params=params
    )
    return session


@router.get("/sessions", response_model=List[TherapySessionResponse])
def get_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 20
):
    return therapy_service.get_user_sessions(db, current_user.id, limit)


@router.get("/sessions/{session_id}", response_model=TherapySessionResponse)
def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session = therapy_service.get_session(db, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="理疗会话不存在",
        )
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问",
        )
    return session


@router.post("/sessions/{session_id}/start", response_model=TherapySessionResponse)
def start_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session = therapy_service.start_session(db, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="理疗会话不存在",
        )
    return session


@router.post("/sessions/{session_id}/pause", response_model=TherapySessionResponse)
def pause_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session = therapy_service.pause_session(db, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="理疗会话不存在",
        )
    return session


@router.post("/sessions/{session_id}/resume", response_model=TherapySessionResponse)
def resume_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session = therapy_service.resume_session(db, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="理疗会话不存在",
        )
    return session


@router.post("/sessions/{session_id}/stop", response_model=TherapySessionResponse)
def stop_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session = therapy_service.stop_session(db, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="理疗会话不存在",
        )
    return session


@router.get("/sessions/{session_id}/status", response_model=TherapyStatusResponse)
def get_session_status(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    status_info = therapy_service.get_session_status(db, session_id)
    if not status_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="理疗会话不存在",
        )
    return status_info
