from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
import os
import uuid
from datetime import datetime

from app.database import get_db
from app.schemas.ai import AICaptureRequest, AICaptureResponse, AIAnalysisRequest, AIAnalysisResponse
from app.models.user import User
from app.services.ai_service import ai_service
from app.core.security import get_current_user


router = APIRouter(prefix="/ai", tags=["AI分析"])


@router.post("/capture", response_model=AICaptureResponse)
def capture_image(
    request: AICaptureRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session_id = request.session_id if request else None
    image_filename = f"{uuid.uuid4()}.jpg"
    image_path = f"/uploads/{image_filename}"
    
    capture = ai_service.create_capture(db, current_user.id, image_path, session_id)
    return capture


@router.post("/analyze", response_model=AIAnalysisResponse)
def analyze_image(
    request: AIAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    analysis = ai_service.create_analysis(db, current_user.id, request.capture_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="图像采集不存在",
        )
    return analysis


@router.get("/analysis/{analysis_id}", response_model=AIAnalysisResponse)
def get_analysis(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    analysis = ai_service.get_analysis(db, analysis_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分析结果不存在",
        )
    if analysis.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问",
        )
    return analysis


@router.get("/history", response_model=List[AIAnalysisResponse])
def get_analysis_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 20
):
    return ai_service.get_user_analyses(db, current_user.id, limit)
