from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.device import Device, DeviceConnection
from app.crud.device_crud import device_crud


class DeviceService:
    def get_all_devices(self, db: Session) -> List[Device]:
        return device_crud.get_all(db)

    def get_device_by_id(self, db: Session, device_id: str) -> Optional[Device]:
        return device_crud.get(db, device_id)

    def get_user_devices(self, db: Session, user_id: str) -> List[DeviceConnection]:
        return device_crud.get_by_user(db, user_id)

    def bind_device(self, db: Session, user_id: str, device_id: str, device_name: str = None) -> Optional[DeviceConnection]:
        existing = device_crud.get_user_device(db, user_id, device_id)
        if existing:
            return existing
        return device_crud.create_connection(db, user_id, device_id, device_name)

    def unbind_device(self, db: Session, user_id: str, device_id: str) -> bool:
        connection = device_crud.get_user_device(db, user_id, device_id)
        if connection:
            device_crud.delete(db, connection.id)
            return True
        return False

    def connect_device(self, db: Session, user_id: str, device_id: str) -> dict:
        device = device_crud.get(db, device_id)
        if not device:
            return {"success": False, "message": "设备不存在"}
        
        connection = device_crud.get_user_device(db, user_id, device_id)
        if not connection:
            device_name = device.name if device else None
            connection = device_crud.create_connection(db, user_id, device_id, device_name)
        
        from datetime import datetime
        connection.is_connected = True
        connection.connected_at = datetime.utcnow()
        db.commit()
        db.refresh(connection)
        
        return {"success": True, "message": "设备连接成功", "data": connection}

    def disconnect_device(self, db: Session, user_id: str, device_id: str) -> dict:
        connection = device_crud.get_user_device(db, user_id, device_id)
        if not connection:
            return {"success": False, "message": "设备未绑定"}
        
        connection.is_connected = False
        connection.connected_at = None
        db.commit()
        
        return {"success": True, "message": "设备断开成功"}

    def get_device_status(self, db: Session, user_id: str, device_id: str) -> Optional[dict]:
        connection = device_crud.get_user_device(db, user_id, device_id)
        if connection:
            return {
                "device_id": connection.device_id,
                "is_connected": connection.is_connected,
                "last_heartbeat": connection.last_heartbeat
            }
        return None


device_service = DeviceService()
