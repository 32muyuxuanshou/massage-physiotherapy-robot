from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.device import Device, DeviceConnection
from app.crud.base import CRUDBase


class DeviceCRUD(CRUDBase[Device]):
    def get_by_user(self, db: Session, user_id: str) -> List[DeviceConnection]:
        return db.query(DeviceConnection).filter(
            DeviceConnection.user_id == user_id
        ).all()

    def get_user_device(self, db: Session, user_id: str, device_id: str) -> Optional[DeviceConnection]:
        return db.query(DeviceConnection).filter(
            DeviceConnection.user_id == user_id,
            DeviceConnection.device_id == device_id
        ).first()

    def create_connection(self, db: Session, user_id: str, device_id: str, device_name: str = None) -> DeviceConnection:
        import uuid
        connection = DeviceConnection(
            id=str(uuid.uuid4()),
            user_id=user_id,
            device_id=device_id,
            device_name=device_name,
            is_connected=False
        )
        db.add(connection)
        db.commit()
        db.refresh(connection)
        return connection

    def connect_device(self, db: Session, user_id: str, device_id: str) -> Optional[DeviceConnection]:
        connection = self.get_user_device(db, user_id, device_id)
        if connection:
            from datetime import datetime
            connection.is_connected = True
            connection.connected_at = datetime.utcnow()
            db.commit()
            db.refresh(connection)
        return connection

    def disconnect_device(self, db: Session, user_id: str, device_id: str) -> Optional[DeviceConnection]:
        connection = self.get_user_device(db, user_id, device_id)
        if connection:
            connection.is_connected = False
            connection.connected_at = None
            db.commit()
            db.refresh(connection)
        return connection


device_crud = DeviceCRUD(Device)
