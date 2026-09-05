from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class DeviceBase(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    model: Optional[str] = None
    manufacturer: Optional[str] = None


class DeviceResponse(DeviceBase):
    id: str
    status: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class DeviceConnectionRequest(BaseModel):
    device_id: str


class DeviceConnectionResponse(BaseModel):
    id: str
    user_id: str
    device_id: str
    device_name: Optional[str]
    is_connected: bool
    connected_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class DeviceStatusResponse(BaseModel):
    device_id: str
    is_connected: bool
    last_heartbeat: Optional[datetime]
