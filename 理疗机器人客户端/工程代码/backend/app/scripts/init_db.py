import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from app.database import engine, Base, SessionLocal
from app.config import get_settings
from app.models import User, Device, DeviceConnection, TherapyMethod, AICapture, AIAnalysis, TherapySession
from app.core.security import get_password_hash


def init_db():
    Base.metadata.create_all(bind=engine)
    print("数据库表已创建")

    if not get_settings().SEED_DEMO_DATA:
        print("演示数据初始化已关闭")
        return

    db = SessionLocal()
    try:
        existing_user = db.query(User).filter(User.phone == "13800138000").first()
        if not existing_user:
            test_user = User(
                id="user-test-001",
                phone="13800138000",
                password_hash=get_password_hash("123456"),
                nickname="测试用户",
                is_active=True
            )
            db.add(test_user)
            print("测试用户已创建: 手机号 13800138000, 密码 123456")

        devices = [
            {"id": "device-1", "name": "按摩机器人", "type": "tuina", "model": "瑞尔曼", "manufacturer": "颐本科技"},
            {"id": "device-2", "name": "艾灸机器人", "type": "acupuncture", "model": "瑞尔曼", "manufacturer": "颐本科技"},
            {"id": "device-3", "name": "光疗嫩肤机器人", "type": "phototherapy", "model": "瑞尔曼", "manufacturer": "颐本科技"},
            {"id": "device-4", "name": "超声减脂机器人", "type": "ultrasound", "model": "瑞尔曼", "manufacturer": "颐本科技"},
        ]

        for device_data in devices:
            existing_device = db.query(Device).filter(Device.id == device_data["id"]).first()
            if not existing_device:
                device = Device(**device_data, status="online", is_active=True)
                db.add(device)
                print(f"设备已创建: {device_data['name']}")

        methods = [
            {"id": "method-001", "name": "推拿手法", "type": "tuina", "description": "传统推拿手法，缓解肌肉紧张", "default_duration": 30},
            {"id": "method-002", "name": "点穴疗法", "type": "xuewei", "description": "点穴刺激，调理经络", "default_duration": 30},
            {"id": "method-003", "name": "揉捏技法", "type": "niannie", "description": "揉捏放松，缓解疲劳", "default_duration": 30},
            {"id": "method-004", "name": "拍打疗法", "type": "paida", "description": "拍打通络，促进循环", "default_duration": 30},
        ]

        for method_data in methods:
            existing_method = db.query(TherapyMethod).filter(TherapyMethod.id == method_data["id"]).first()
            if not existing_method:
                method = TherapyMethod(**method_data, is_active=True)
                db.add(method)
                print(f"理疗方法已创建: {method_data['name']}")

        db.commit()
        print("\n数据库初始化完成！")

    except Exception as e:
        print(f"初始化数据时出错: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
