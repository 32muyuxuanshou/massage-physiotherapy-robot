from sqlalchemy import Column, String, Boolean, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    type = Column(String(50), nullable=False)
    model = Column(String(100), nullable=True)
    manufacturer = Column(String(100), nullable=True)
    status = Column(String(20), default="offline")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    connections = relationship("DeviceConnection", back_populates="device")


class DeviceConnection(Base):
    __tablename__ = "device_connections"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    device_id = Column(String(36), ForeignKey("devices.id"), nullable=False)
    device_name = Column(String(100), nullable=True)
    is_connected = Column(Boolean, default=False)
    connected_at = Column(DateTime, nullable=True)
    last_heartbeat = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="devices")
    device = relationship("Device", back_populates="connections")
