# 颐本智能理疗系统 - 后端服务搭建提示词文档

> **历史设计资料**：本文是 2026-04-10 的 AI 搭建提示词，包含尚未按当前代码修订的旧目录、端口和 Compose 示例。当前运行与部署请以 `backend/README.md`、项目根目录 `DEPLOY.md` 和 `Docker傻瓜式操作教程.md` 为准。

**版本**: V0.1
**日期**: 2026-04-10
**技术栈**: Python 3.10+ / FastAPI / SQLite / SQLAlchemy
**用途**: 指导AI编码工具快速搭建后端服务
**参考文档**: `../frontend/doc/spec/api-design.md`

---

## 1. 项目概述

### 1.1 项目背景

颐本智能理疗系统是一套面向终端用户的智能理疗管理平台。需要基于已设计好的API接口文档，搭建完整的后端服务，为前端提供RESTful API支持。

### 1.2 前端项目信息

| 项目 | 信息 |
|------|------|
| 前端框架 | Vue 3 + Vite + Pinia |
| 端口 | 5173 |
| API基础URL | `/api/v1` |
| 认证方式 | Bearer Token (JWT) |

### 1.3 后端服务目标

- 提供完整的RESTful API
- 实现用户认证和授权
- 管理设备、理疗会话等业务数据
- 支持AI图像采集和分析接口
- 实现理疗全流程管理
- 支持Redis缓存（可选，保证兼容性）
- 完整的中间件和安全机制

---

## 2. 技术栈选择

### 2.1 推荐技术栈

| 层级 | 技术选型 | 版本要求 | 说明 |
|------|---------|---------|------|
| 后端语言 | Python | >= 3.10 | 高效简洁，数据处理能力强 |
| Web框架 | FastAPI | ^0.100.0 | 现代异步框架，自动API文档 |
| 数据库 | SQLite | 3.x | 轻量级，适合开发，无需配置 |
| ORM | SQLAlchemy | 2.0+ | 成熟ORM，支持异步，多数据库 |
| 数据库迁移 | Alembic | ^1.11.0 | 数据库版本管理和迁移 |
| 缓存（可选） | Redis | 6.0+ | 高性能缓存（未来扩展） |
| 认证 | python-jose | ^3.3.0 | JWT编解码 |
| 密码加密 | passlib + bcrypt | 最新 | 安全密码哈希 |
| 验证 | Pydantic | 2.0+ | 数据验证和序列化 |
| 异步Redis | redis-py | ^5.0.0 | Redis客户端（可选） |
| 日志 | loguru | ^3.9.0 | 现代化日志库 |
| 文档 | Swagger/OpenAPI | 内置 | 自动API文档 |
| 测试 | pytest + pytest-asyncio | 最新 | Python标准测试框架 |
| 部署 | Docker + uvicorn | 最新 | ASGI服务器 |

### 2.2 为什么选择这些技术

1. **Python + FastAPI**: 开发效率高，异步支持优秀，自动Swagger文档，类型安全（Pydantic）
2. **SQLite**: 零配置，零维护，适合开发测试，生产环境可迁移到PostgreSQL/MySQL（SQLAlchemy 2.0完美支持）
3. **SQLAlchemy 2.0**: 功能强大，支持异步，ORM成熟，多数据库兼容
4. **Redis兼容性**: 通过依赖注入和抽象层实现，代码编写时考虑Redis扩展，无Redis时使用内存缓存
5. **Pydantic 2.0**: FastAPI核心依赖，数据验证和序列化，与类型提示完美结合

### 2.3 Redis兼容性设计

为保证Redis的可选性和未来扩展性，采用以下设计：

```python
# 缓存抽象接口
class CacheInterface:
    async def get(self, key: str) -> Optional[str]: ...
    async def set(self, key: str, value: str, expire: int = None) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def exists(self, key: str) -> bool: ...

# Redis实现（可选）
class RedisCache(CacheInterface):
    def __init__(self, redis_url: str): ...

# 内存缓存实现（无Redis时的fallback）
class MemoryCache(CacheInterface):
    def __init__(self): ...

# 依赖注入
def get_cache() -> CacheInterface:
    if settings.REDIS_ENABLED:
        return RedisCache(settings.REDIS_URL)
    return MemoryCache()
```

---

## 3. 目录结构设计

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # 应用入口
│   ├── config.py            # 配置管理
│   ├── database.py          # 数据库连接
│   ├── dependencies.py      # 依赖注入
│   │
│   ├── api/                 # API路由
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── router.py   # 路由汇总
│   │   │   ├── auth.py     # 认证接口
│   │   │   ├── users.py    # 用户接口
│   │   │   ├── devices.py  # 设备接口
│   │   │   ├── ai.py       # AI接口
│   │   │   └── therapy.py  # 理疗接口
│   │   └── deps.py         # API依赖
│   │
│   ├── core/                # 核心模块
│   │   ├── __init__.py
│   │   ├── security.py     # 安全认证
│   │   ├── cache.py        # 缓存抽象
│   │   └── exceptions.py   # 自定义异常
│   │
│   ├── models/              # SQLAlchemy模型
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── device.py
│   │   ├── ai.py
│   │   └── therapy.py
│   │
│   ├── schemas/             # Pydantic模型
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── device.py
│   │   ├── ai.py
│   │   └── therapy.py
│   │
│   ├── services/            # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── device_service.py
│   │   ├── ai_service.py
│   │   └── therapy_service.py
│   │
│   ├── crud/                # 数据访问层
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── user_crud.py
│   │   ├── device_crud.py
│   │   ├── ai_crud.py
│   │   └── therapy_crud.py
│   │
│   └── utils/               # 工具函数
│       ├── __init__.py
│       ├── responses.py     # 统一响应
│       └── validators.py    # 数据验证
│
├── tests/                    # 测试文件
│   ├── __init__.py
│   ├── conftest.py
│   ├── api/
│   │   └── v1/
│   │       ├── test_auth.py
│   │       ├── test_users.py
│   │       └── test_devices.py
│   └── services/
│       └── test_auth_service.py
│
├── alembic/                  # 数据库迁移
│   ├── env.py
│   └── versions/
│
├── data/                    # 数据目录（SQLite数据库）
├── uploads/                 # 上传文件目录
├── logs/                    # 日志文件
├── doc/                     # 项目文档
│
├── .env.example             # 环境变量示例
├── .gitignore
├── alembic.ini             # Alembic配置
├── pyproject.toml          # 项目配置
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## 4. 数据库设计

### 4.1 SQLAlchemy模型

请在 `app/models/` 中实现以下数据模型：

```python
# app/models/user.py
from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True)
    phone = Column(String(11), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    name = Column(String(20), nullable=False)
    avatar = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    device_connections = relationship("DeviceConnection", back_populates="user")
    ai_captures = relationship("AICapture", back_populates="user")
    ai_analyses = relationship("AIAnalysis", back_populates="user")
    therapy_sessions = relationship("TherapySession", back_populates="user")
    refresh_tokens = relationship("RefreshToken", back_populates="user")
```

```python
# app/models/device.py
from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Device(Base):
    __tablename__ = "devices"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(50), nullable=False)
    type = Column(String(20), nullable=False, index=True)
    icon = Column(String(50))
    model = Column(String(50))
    manufacturer = Column(String(100))
    description = Column(Text)
    specifications = Column(Text)  # JSON字符串
    status = Column(Text, nullable=False)  # JSON字符串
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    device_connections = relationship("DeviceConnection", back_populates="device")
    ai_captures = relationship("AICapture", back_populates="device")
    ai_analyses = relationship("AIAnalysis", back_populates="device")
    therapy_sessions = relationship("TherapySession", back_populates="device")
```

### 4.2 初始化数据

创建 `app/init_data.py` 实现初始化数据：

1. **设备数据**：4种理疗设备
   - 按摩机器人（massage）
   - 艾灸机器人（moxibustion）
   - 光疗嫩肤机器人（light-therapy）
   - 超声减脂机器人（fat-reduction）

2. **测试用户**：
   - 手机号：13800138000
   - 密码：123456（bcrypt加密）
   - 姓名：小雪

---

## 5. 核心模块实现步骤

### 5.1 项目初始化

**提示词**：

```
请帮我初始化一个Python + FastAPI后端项目：

1. 创建pyproject.toml，配置以下依赖：

[project]
name = "physiotherapy-backend"
version = "0.1.0"
requires-python = ">=3.10"

dependencies = [
    "fastapi>=0.100.0",
    "uvicorn[standard]>=0.23.0",
    "sqlalchemy>=2.0.0",
    "alembic>=1.11.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "python-multipart>=0.0.6",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "loguru>=0.7.0",
    "redis>=5.0.0",
    "python-dotenv>=1.0.0",
    "email-validator>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "httpx>=0.24.0",
    "pytest-cov>=4.1.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"

2. 创建目录结构（参考上述目录结构）

3. 创建.env.example环境变量文件

4. 配置SQLAlchemy数据库连接

5. 初始化Alembic：alembic init alembic
```

### 5.2 配置模块实现

**提示词**：

```
请帮我实现配置模块（app/config.py）：

1. 使用pydantic-settings管理配置
2. 从环境变量读取配置
3. 支持从.env文件加载

from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "Physiotherapy Backend"
    VERSION: str = "0.1.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    
    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # 数据库配置
    DATABASE_URL: str = "sqlite:///./data/physiotherapy.db"
    
    # Redis配置（可选）
    REDIS_ENABLED: bool = False
    REDIS_URL: str = "redis://localhost:6379"
    
    # 安全配置
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # 文件上传
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    # CORS配置
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

### 5.3 数据库模块实现

**提示词**：

```
请帮我实现数据库模块（app/database.py）：

1. 配置SQLAlchemy引擎（支持SQLite）
2. 创建SessionLocal和get_db依赖
3. 支持数据库连接测试
4. 创建Base基类

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from app.config import get_settings

settings = get_settings()

# 根据数据库URL类型选择连接方式
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=settings.DEBUG
    )
else:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        echo=settings.DEBUG
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """初始化数据库"""
    from app.models import user, device, ai, therapy
    Base.metadata.create_all(bind=engine)
```

### 5.4 缓存模块实现（可选Redis兼容性）

**提示词**：

```
请帮我实现缓存模块（app/core/cache.py）：

1. 定义缓存抽象接口
2. 实现内存缓存（无Redis时使用）
3. 实现Redis缓存（可选）
4. 提供依赖注入函数

from abc import ABC, abstractmethod
from typing import Optional, Any
import json
import asyncio
from datetime import datetime, timedelta

class CacheInterface(ABC):
    @abstractmethod
    async def get(self, key: str) -> Optional[str]: ...
    
    @abstractmethod
    async def set(self, key: str, value: str, expire: int = None) -> None: ...
    
    @abstractmethod
    async def delete(self, key: str) -> None: ...
    
    @abstractmethod
    async def exists(self, key: str) -> bool: ...

class MemoryCache(CacheInterface):
    """内存缓存实现（无Redis时的fallback）"""
    def __init__(self):
        self._cache: dict = {}
        self._expire: dict = {}
    
    async def get(self, key: str) -> Optional[str]:
        if key in self._expire:
            if datetime.utcnow() > self._expire[key]:
                await self.delete(key)
                return None
        return self._cache.get(key)
    
    async def set(self, key: str, value: str, expire: int = None) -> None:
        self._cache[key] = value
        if expire:
            self._expire[key] = datetime.utcnow() + timedelta(seconds=expire)
    
    async def delete(self, key: str) -> None:
        self._cache.pop(key, None)
        self._expire.pop(key, None)
    
    async def exists(self, key: str) -> bool:
        return await self.get(key) is not None

class RedisCache(CacheInterface):
    """Redis缓存实现（可选）"""
    def __init__(self, redis_url: str):
        import redis.asyncio as redis
        self.redis = redis.from_url(redis_url)
    
    async def get(self, key: str) -> Optional[str]:
        return await self.redis.get(key)
    
    async def set(self, key: str, value: str, expire: int = None) -> None:
        if expire:
            await self.redis.setex(key, expire, value)
        else:
            await self.redis.set(key, value)
    
    async def delete(self, key: str) -> None:
        await self.redis.delete(key)
    
    async def exists(self, key: str) -> bool:
        return await self.redis.exists(key) > 0

# 依赖注入
async def get_cache() -> CacheInterface:
    settings = get_settings()
    if settings.REDIS_ENABLED:
        return RedisCache(settings.REDIS_URL)
    return MemoryCache()
```

### 5.5 安全认证模块实现

**提示词**：

```
请帮我实现安全认证模块（app/core/security.py）：

1. JWT Token生成和验证
2. 密码哈希和验证
3. 创建认证依赖
4. Token黑名单管理

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import get_db
from app.core.cache import get_cache, CacheInterface

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据"
        )

async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    cache: CacheInterface = Depends(get_cache)
) -> dict:
    token = credentials.credentials
    
    # 检查Token黑名单
    is_blacklisted = await cache.exists(f"blacklist:{token}")
    if is_blacklisted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token已被撤销"
        )
    
    payload = decode_token(token)
    
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的Token类型"
        )
    
    return payload

async def add_to_blacklist(token: str, cache: CacheInterface) -> None:
    """将Token加入黑名单"""
    await cache.set(f"blacklist:{token}", "1", expire=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
```

### 5.6 Pydantic模型实现

**提示词**：

```
请帮我实现Pydantic模型（app/schemas/）：

1. 基础响应模型
2. 认证相关模型
3. 用户相关模型
4. 设备相关模型
5. AI相关模型
6. 理疗相关模型

from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime

# 基础响应
class ResponseModel(BaseModel):
    code: int = 200
    message: str = "操作成功"
    data: Optional[Any] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class ErrorResponse(BaseModel):
    code: int
    message: str
    errors: Optional[List[dict]] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

# 认证模型
class LoginRequest(BaseModel):
    phone: str = Field(..., pattern=r"^1[3-9]\d{9}$")
    password: str = Field(..., min_length=6, max_length=20)

class LoginResponse(BaseModel):
    token: str
    refreshToken: str
    userInfo: dict

# 用户模型
class UserBase(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=20)
    avatar: Optional[str] = None

class UserUpdate(UserBase):
    pass

class UserResponse(BaseModel):
    id: str
    phone: str
    name: str
    avatar: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime
    
    class Config:
        from_attributes = True

# 设备模型
class DeviceStatus(BaseModel):
    camera: str
    arm: str
    head: str

class DeviceResponse(BaseModel):
    id: str
    name: str
    type: str
    icon: str
    model: str
    manufacturer: Optional[str]
    description: Optional[str]
    status: DeviceStatus
    connected: bool
    lastConnected: Optional[datetime]
    
    class Config:
        from_attributes = True

# AI模型
class RegionInfo(BaseModel):
    name: str
    position: str
    confidence: float
    area: float
    recommendedMethods: List[str]

class AnalysisResponse(BaseModel):
    analysisId: str
    captureId: str
    analyzed: bool
    regions: List[RegionInfo]
    summary: Optional[str]
    analyzedAt: datetime
    
    class Config:
        from_attributes = True

# 理疗模型
class TherapyMethod(BaseModel):
    type: str
    name: str
    duration: int = Field(..., ge=0, le=60)

class TherapyParams(BaseModel):
    height: int = Field(..., ge=0, le=100)
    speed: int = Field(..., ge=0, le=100)
    intensity: int = Field(..., ge=0, le=5)

class TherapySessionCreate(BaseModel):
    deviceId: str
    analysisId: Optional[str] = None
    methods: List[TherapyMethod]
    params: TherapyParams

class TherapySessionResponse(BaseModel):
    sessionId: str
    deviceId: str
    status: str
    totalDuration: int
    methods: List[TherapyMethod]
    params: TherapyParams
    createdAt: datetime
    
    class Config:
        from_attributes = True
```

### 5.7 CRUD操作实现

**提示词**：

```
请帮我实现CRUD操作（app/crud/base.py 和 app/crud/）：

1. 基础CRUD类
2. 用户CRUD
3. 设备CRUD
4. AI CRU
5. 理疗CRUD

from typing import TypeVar, Generic, Type, Optional, List, Any
from sqlalchemy.orm import Session
from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)

class CRUDBase(Generic[ModelType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model
    
    def get(self, db: Session, id: str) -> Optional[ModelType]:
        return db.query(self.model).filter(self.model.id == id).first()
    
    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        return db.query(self.model).offset(skip).limit(limit).all()
    
    def create(self, db: Session, *, obj_in: dict) -> ModelType:
        db_obj = self.model(**obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def update(self, db: Session, *, db_obj: ModelType, obj_in: dict) -> ModelType:
        for field, value in obj_in.items():
            setattr(db_obj, field, value)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def delete(self, db: Session, *, id: str) -> Optional[ModelType]:
        obj = db.query(self.model).filter(self.model.id == id).first()
        if obj:
            db.delete(obj)
            db.commit()
        return obj
```

### 5.8 业务服务层实现

**提示词**：

```
请帮我实现业务服务层（app/services/）：

1. 认证服务
2. 用户服务
3. 设备服务
4. AI服务
5. 理疗服务

# app/services/auth_service.py 示例
from typing import Optional
from sqlalchemy.orm import Session
from app.core.security import (
    verify_password, get_password_hash, 
    create_access_token, create_refresh_token
)
from app.crud.user_crud import user_crud
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse
from app.core.exceptions import AuthenticationError, NotFoundError

class AuthService:
    def __init__(self):
        self.user_crud = user_crud
    
    async def login(self, db: Session, phone: str, password: str) -> dict:
        user = self.user_crud.get_by_phone(db, phone)
        
        if not user or not verify_password(password, user.password):
            raise AuthenticationError("手机号或密码错误")
        
        access_token = create_access_token(data={"sub": user.id, "phone": user.phone})
        refresh_token = create_refresh_token(data={"sub": user.id})
        
        # 保存refresh token到数据库
        self._save_refresh_token(db, user.id, refresh_token)
        
        return {
            "token": access_token,
            "refreshToken": refresh_token,
            "userInfo": {
                "id": user.id,
                "phone": user.phone,
                "name": user.name,
                "avatar": user.avatar
            }
        }
    
    async def register(self, db: Session, phone: str, password: str, name: str) -> dict:
        existing_user = self.user_crud.get_by_phone(db, phone)
        if existing_user:
            raise AuthenticationError("手机号已注册")
        
        user_data = {
            "phone": phone,
            "password": get_password_hash(password),
            "name": name
        }
        user = self.user_crud.create(db, obj_in=user_data)
        
        access_token = create_access_token(data={"sub": user.id, "phone": user.phone})
        
        return {
            "userId": user.id,
            "token": access_token
        }

auth_service = AuthService()
```

### 5.9 API路由实现

**提示词**：

```
请帮我实现API路由（app/api/v1/）：

1. 认证路由
2. 用户路由
3. 设备路由
4. AI路由
5. 理疗路由

# app/api/v1/auth.py 示例
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.security import verify_token
from app.schemas.auth import LoginRequest, LoginResponse
from app.services.auth_service import auth_service
from app.utils.responses import success_response

router = APIRouter(prefix="/auth", tags=["认证"])

@router.post("/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    result = await auth_service.login(db, request.phone, request.password)
    return success_response(result, "登录成功")

@router.post("/logout")
async def logout(
    token_data: dict = Depends(verify_token),
    cache = Depends(get_cache)
):
    # 将token加入黑名单
    # await add_to_blacklist(token, cache)
    return success_response(None, "退出登录成功")

@router.post("/change-password")
async def change_password(
    oldPassword: str,
    newPassword: str,
    token_data: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    user_id = token_data.get("sub")
    await auth_service.change_password(db, user_id, oldPassword, newPassword)
    return success_response(None, "密码修改成功")
```

### 5.10 中间件实现

**提示词**：

```
请帮我实现中间件（app/middleware/）：

1. 请求日志中间件
2. 错误处理中间件
3. CORS中间件
4. 限流中间件（可选）

# app/middleware/logging.py
from loguru import logger
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import time

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        logger.info(f"Request: {request.method} {request.url.path}")
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        logger.info(
            f"Response: {response.status_code} "
            f"Time: {process_time:.3f}s "
            f"Path: {request.url.path}"
        )
        
        response.headers["X-Process-Time"] = str(process_time)
        return response

# app/middleware/errors.py
from fastapi import Request, status
from fastapi.responses import JSONResponse
from app.core.exceptions import AppException

async def exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "errors": exc.errors
        }
    )

async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": exc.detail
        }
    )
```

### 5.11 主应用入口

**提示词**：

```
请帮我实现主应用入口（app/main.py）：

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import get_settings
from app.database import init_db
from app.api.v1.router import api_router
from app.middleware.logging import LoggingMiddleware
from app.middleware.errors import exception_handler, http_exception_handler
from app.core.exceptions import AppException
from fastapi import HTTPException

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时
    init_db()
    # 初始化数据（仅开发环境）
    if settings.DEBUG:
        from app.init_data import init_default_data
        init_default_data()
    yield
    # 关闭时
    pass

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# 中间件
app.add_middleware(LoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 异常处理
app.add_exception_handler(AppException, exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)

# 路由
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "Physiotherapy Backend API", "version": settings.VERSION}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

---

## 6. 工具函数实现

### 6.1 统一响应

**提示词**：

```
请帮我实现统一响应（app/utils/responses.py）：

from typing import Any, Optional
from datetime import datetime

def success_response(data: Any = None, message: str = "操作成功") -> dict:
    return {
        "code": 200,
        "message": message,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }

def error_response(code: int, message: str, errors: Optional[list] = None) -> dict:
    return {
        "code": code,
        "message": message,
        "errors": errors or [],
        "timestamp": datetime.utcnow().isoformat()
    }

def paginated_response(
    items: list,
    page: int,
    page_size: int,
    total: int,
    message: str = "查询成功"
) -> dict:
    return {
        "code": 200,
        "message": message,
        "data": {
            "list": items,
            "pagination": {
                "page": page,
                "pageSize": page_size,
                "total": total,
                "totalPages": (total + page_size - 1) // page_size
            }
        },
        "timestamp": datetime.utcnow().isoformat()
    }
```

### 6.2 自定义异常

**提示词**：

```
请帮我实现自定义异常（app/core/exceptions.py）：

from typing import Optional, List

class AppException(Exception):
    def __init__(
        self,
        status_code: int = 500,
        code: int = 500,
        message: str = "服务器内部错误",
        errors: Optional[List[dict]] = None
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.errors = errors or []
        super().__init__(self.message)

class AuthenticationError(AppException):
    def __init__(self, message: str = "认证失败"):
        super().__init__(status_code=401, code=401, message=message)

class AuthorizationError(AppException):
    def __init__(self, message: str = "无权限访问"):
        super().__init__(status_code=403, code=403, message=message)

class NotFoundError(AppException):
    def __init__(self, message: str = "资源不存在"):
        super().__init__(status_code=404, code=404, message=message)

class ValidationError(AppException):
    def __init__(self, message: str = "参数验证失败", errors: Optional[List[dict]] = None):
        super().__init__(status_code=422, code=422, message=message, errors=errors)

class ConflictError(AppException):
    def __init__(self, message: str = "资源冲突"):
        super().__init__(status_code=409, code=409, message=message)
```

---

## 7. 数据初始化

**提示词**：

```
请帮我实现数据初始化（app/init_data.py）：

import uuid
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.device import Device
from app.core.security import get_password_hash
import json

DEFAULT_DEVICES = [
    {
        "id": "device-1",
        "name": "按摩机器人",
        "type": "massage",
        "icon": "按摩机器人",
        "model": "瑞尔曼",
        "manufacturer": "瑞尔曼医疗科技",
        "description": "智能按摩理疗机器人，通过AI分析实现个性化按摩",
        "specifications": json.dumps({
            "dimensions": "1200x600x800mm",
            "weight": "80kg",
            "power": "220V/50Hz"
        }),
        "status": json.dumps({
            "camera": "online",
            "arm": "online",
            "head": "online"
        })
    },
    {
        "id": "device-2",
        "name": "艾灸机器人",
        "type": "moxibustion",
        "icon": "艾灸机器人",
        "model": "瑞尔曼",
        "manufacturer": "瑞尔曼医疗科技",
        "description": "智能艾灸理疗机器人，精准温控，安全可靠",
        "specifications": json.dumps({
            "dimensions": "1000x500x700mm",
            "weight": "60kg",
            "power": "220V/50Hz"
        }),
        "status": json.dumps({
            "camera": "online",
            "arm": "online",
            "head": "online"
        })
    },
    {
        "id": "device-3",
        "name": "光疗嫩肤机器人",
        "type": "light-therapy",
        "icon": "光疗嫩肤机器人",
        "model": "瑞尔曼",
        "manufacturer": "瑞尔曼医疗科技",
        "description": "光子嫩肤理疗机器人，改善肌肤状态",
        "specifications": json.dumps({
            "dimensions": "800x400x600mm",
            "weight": "40kg",
            "power": "220V/50Hz"
        }),
        "status": json.dumps({
            "camera": "online",
            "arm": "online",
            "head": "offline"
        })
    },
    {
        "id": "device-4",
        "name": "超声减脂机器人",
        "type": "fat-reduction",
        "icon": "超声减脂机器人",
        "model": "瑞尔曼",
        "manufacturer": "瑞尔曼医疗科技",
        "description": "超声波减脂理疗机器人，非侵入式减脂",
        "specifications": json.dumps({
            "dimensions": "1100x550x750mm",
            "weight": "70kg",
            "power": "220V/50Hz"
        }),
        "status": json.dumps({
            "camera": "online",
            "arm": "online",
            "head": "online"
        })
    }
]

DEFAULT_USER = {
    "id": "user-001",
    "phone": "13800138000",
    "password": get_password_hash("123456"),
    "name": "小雪",
    "avatar": ""
}

def init_default_data():
    from app.database import SessionLocal
    
    db = SessionLocal()
    try:
        # 初始化用户
        existing_user = db.query(User).filter(User.phone == DEFAULT_USER["phone"]).first()
        if not existing_user:
            user = User(**DEFAULT_USER)
            db.add(user)
        
        # 初始化设备
        for device_data in DEFAULT_DEVICES:
            existing_device = db.query(Device).filter(Device.id == device_data["id"]).first()
            if not existing_device:
                device = Device(**device_data)
                db.add(device)
        
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error initializing data: {e}")
    finally:
        db.close()
```

---

## 8. 测试实现

### 8.1 测试配置

**提示词**：

```
请帮我实现测试配置（tests/conftest.py）：

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db
from app.models.user import User
from app.core.security import get_password_hash

# 测试数据库
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def test_user(db):
    user = User(
        id="test-user-001",
        phone="13800138000",
        password=get_password_hash("123456"),
        name="测试用户"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
```

### 8.2 API测试示例

**提示词**：

```
请帮我实现API测试（tests/api/v1/test_auth.py）：

import pytest
from fastapi import status

def test_login_success(client, test_user):
    response = client.post(
        "/api/v1/auth/login",
        json={"phone": "13800138000", "password": "123456"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["code"] == 200
    assert "token" in data["data"]
    assert "refreshToken" in data["data"]
    assert data["data"]["userInfo"]["phone"] == "13800138000"

def test_login_wrong_password(client, test_user):
    response = client.post(
        "/api/v1/auth/login",
        json={"phone": "13800138000", "password": "wrongpassword"}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_login_user_not_found(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"phone": "13900000000", "password": "123456"}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_get_profile(client, test_user):
    # 先登录获取token
    login_response = client.post(
        "/api/v1/auth/login",
        json={"phone": "13800138000", "password": "123456"}
    )
    token = login_response.json()["data"]["token"]
    
    # 获取用户信息
    response = client.get(
        "/api/v1/users/profile",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["data"]["phone"] == "13800138000"
    assert data["data"]["name"] == "测试用户"
```

---

## 9. Docker配置

**提示词**：

```
请帮我创建Docker配置文件：

1. **Dockerfile**：
```dockerfile
FROM python:3.10-slim

WORKDIR /app

# 安装依赖
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

# 复制源代码
COPY . .

# 创建数据目录
RUN mkdir -p data uploads logs

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

2. **docker-compose.yml**：
```yaml
version: '3.8'

services:
  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=sqlite:///./data/physiotherapy.db
      - REDIS_URL=redis://cache:6379
      - REDIS_ENABLED=false
      - SECRET_KEY=your-secret-key-change-in-production
    volumes:
      - ./data:/app/data
      - ./uploads:/app/uploads
    depends_on:
      - cache
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

  cache:
    image: redis:6.0-alpine
    volumes:
      - redis_data:/data

volumes:
  redis_data:
```

3. **.dockerignore**：
```
__pycache__
*.pyc
*.pyo
*.pyd
.Python
*.so
*.egg
*.egg-info
dist
build
.pytest_cache
.coverage
htmlcov
.env
.venv
venv/
.idea
.vscode
*.md
!README.md
test.db
tests/
docs/
```

---

## 10. 启动和部署

### 10.1 开发环境启动

```bash
# 1. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows

# 2. 安装依赖
pip install -e ".[dev]"

# 3. 创建数据目录
mkdir -p data uploads logs

# 4. 配置环境变量
cp .env.example .env
# 编辑.env文件

# 5. 初始化数据库
python -c "from app.database import init_db; init_db()"
python -c "from app.init_data import init_default_data; init_default_data()"

# 6. 启动开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 10.2 生产环境部署

```bash
# 1. 构建
docker build -t physiotherapy-backend:latest .

# 2. 启动
docker-compose up -d

# 3. 查看日志
docker-compose logs -f backend

# 4. 验证部署
curl http://localhost:8000/health
```

### 10.3 API文档访问

- 开发环境: http://localhost:8000/docs
- 生产环境: http://your-domain.com/docs

---

## 11. 常见问题处理

### 11.1 数据库问题

**问题**：无法创建数据库文件
**解决**：
1. 检查data目录是否存在
2. 检查读写权限
3. 使用绝对路径配置DATABASE_URL

### 11.2 Redis连接问题

**问题**：Redis连接失败
**解决**：
1. 检查Redis服务是否启动
2. 设置REDIS_ENABLED=false使用内存缓存
3. 检查REDIS_URL配置

### 11.3 Token验证失败

**问题**：Token验证总是失败
**解决**：
1. 检查SECRET_KEY是否一致
2. 检查Token是否过期
3. 检查Token格式（Bearer Token）
4. 检查Token黑名单

---

## 12. 开发建议

### 12.1 代码规范

1. 使用Python类型提示
2. 遵循PEP 8规范
3. 所有API添加docstring
4. 统一错误处理
5. 适当的日志记录

### 12.2 性能优化

1. 使用async/await异步编程
2. 数据库添加适当索引
3. 实现请求限流
4. 图片压缩和CDN（后续）

### 12.3 安全性

1. 所有密码必须加密（bcrypt）
2. 敏感信息使用环境变量
3. 实现CSRF防护（后续）
4. SQL注入防护（SQLAlchemy自动处理）
5. 实施速率限制

---

## 13. 后续扩展建议

### 13.1 V0.2扩展

1. 启用Redis缓存
2. 实现真实短信发送
3. 实现邮件发送
4. 实现设备实时通信（WebSocket）
5. 实现实时理疗监控

### 13.2 V0.3扩展

1. 集成真实AI算法
2. 实现图像识别
3. 实现智能推荐
4. 迁移到PostgreSQL/MySQL

### 13.3 V0.4扩展

1. 实现多语言支持
2. 实现数据分析报表
3. 实现用户反馈系统

---

## 14. 参考资料

1. **API接口文档**：`../frontend/doc/spec/api-design.md`
2. **前端项目**：`../frontend/`
3. **FastAPI文档**：https://fastapi.tiangolo.com/
4. **SQLAlchemy文档**：https://docs.sqlalchemy.org/
5. **Pydantic文档**：https://docs.pydantic.dev/
6. **Redis文档**：https://redis.io/

---

## 15. 更新日志

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-04-10 | V0.1 | 初始版本，提供完整搭建指南 |
