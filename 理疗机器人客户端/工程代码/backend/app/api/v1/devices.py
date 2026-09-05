from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.device import (
    DeviceResponse,
    DeviceConnectionRequest,
    DeviceConnectionResponse,
    DeviceStatusResponse,
)
from app.models.user import User
from app.services.device_service import device_service
from app.core.security import get_current_user


router = APIRouter(prefix="/devices", tags=["设备"])


@router.get("", response_model=List[DeviceResponse])
def get_devices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return device_service.get_all_devices(db)


@router.get("/{device_id}", response_model=DeviceResponse)
def get_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    device = device_service.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="设备不存在",
        )
    return device


@router.post("/{device_id}/bind")
def bind_device(
    device_id: str,
    request: DeviceConnectionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    device = device_service.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="设备不存在",
        )
    
    connection = device_service.bind_device(
        db, current_user.id, device_id, device.name
    )
    return {"message": "设备绑定成功", "data": connection}


@router.post("/{device_id}/unbind")
def unbind_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    success = device_service.unbind_device(db, current_user.id, device_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="设备未绑定",
        )
    return {"message": "设备解绑成功"}


@router.post("/{device_id}/connect")
def connect_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    result = device_service.connect_device(db, current_user.id, device_id)
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("message", "设备未绑定"),
        )
    return result


@router.post("/{device_id}/disconnect")
def disconnect_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    result = device_service.disconnect_device(db, current_user.id, device_id)
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("message", "设备未绑定"),
        )
    return result


@router.get("/{device_id}/status", response_model=DeviceStatusResponse)
def get_device_status(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    status_info = device_service.get_device_status(db, current_user.id, device_id)
    if not status_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="设备未绑定",
        )
    return status_info
