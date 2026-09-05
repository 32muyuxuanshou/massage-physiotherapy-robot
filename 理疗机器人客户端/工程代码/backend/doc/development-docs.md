# 颐本智能理疗系统 - 后端开发文档

> **历史开发稿**：本文保留 2026-04-10 的设计背景，部分端口、目录、状态和 Docker 命令已过期。当前运行与部署请以 `backend/README.md`、项目根目录 `DEPLOY.md` 和 `Docker傻瓜式操作教程.md` 为准。

**版本**: V1.0
**日期**: 2026-04-10
**技术栈**: Python 3.10+ / FastAPI / SQLAlchemy / SQLite

---

## 1. 项目概述

### 1.1 项目背景

颐本智能理疗系统是一套面向终端用户的智能理疗管理平台。后端服务基于已设计好的API接口文档，提供完整的RESTful API支持。

### 1.2 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        用户设备                             │
│                   (浏览器/移动端)                           │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI 后端服务                         │
│                        端口: 8000                           │
└──────────────────────────┬──────────────────────────────────┘
                           │
         ┌─────────────────┴─────────────────┐
         ▼                                   ▼
┌─────────────────────┐            ┌─────────────────────┐
│    SQLAlchemy ORM   │            │      Redis          │
│    (数据持久化)     │            │    (可选缓存)       │
└─────────────────────┘            └─────────────────────┘
```

### 1.3 功能模块

| 模块 | 功能描述 |
|------|---------|
| 认证模块 | 用户注册、登录、Token刷新、登出 |
| 用户模块 | 个人信息获取与修改、密码修改 |
| 设备模块 | 设备列表、绑定、解绑、连接、断开 |
| AI分析模块 | 图像采集、AI分析、历史记录 |
| 理疗模块 | 理疗方法、会话创建、开始/暂停/继续/停止 |

---

## 2. 项目结构

```
backend/
├── app/
│   ├── api/                    # API 路由层
│   │   └── v1/
│   │       ├── auth.py        # 认证接口
│   │       ├── users.py       # 用户接口
│   │       ├── devices.py     # 设备接口
│   │       ├── ai.py          # AI分析接口
│   │       ├── therapy.py    # 理疗接口
│   │       └── router.py     # 路由汇总
│   │
│   ├── core/                   # 核心模块
│   │   ├── security.py        # JWT认证、密码加密
│   │   ├── cache.py           # 缓存抽象层
│   │   └── exceptions.py      # 自定义异常
│   │
│   ├── models/                 # SQLAlchemy 数据模型
│   │   ├── user.py            # 用户模型
│   │   ├── device.py           # 设备模型
│   │   ├── ai.py               # AI分析模型
│   │   └── therapy.py          # 理疗模型
│   │
│   ├── schemas/                # Pydantic 数据验证
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── device.py
│   │   ├── ai.py
│   │   └── therapy.py
│   │
│   ├── services/               # 业务逻辑层
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── device_service.py
│   │   ├── ai_service.py
│   │   └── therapy_service.py
│   │
│   ├── crud/                   # 数据访问层
│   │   ├── base.py             # 基础CRUD
│   │   ├── user_crud.py
│   │   ├── device_crud.py
│   │   ├── ai_crud.py
│   │   └── therapy_crud.py
│   │
│   ├── utils/                  # 工具函数
│   │   ├── responses.py         # 响应封装
│   │   └── validators.py        # 数据验证
│   │
│   ├── scripts/                # 脚本
│   │   └── init_db.py          # 数据库初始化
│   │
│   ├── config.py               # 配置管理
│   ├── database.py            # 数据库连接
│   └── main.py                # 应用入口
│
├── data/                       # 数据存储目录
├── uploads/                    # 上传文件目录
├── logs/                       # 日志目录
│
├── .env                        # 环境变量
├── requirements.txt            # Python依赖
├── pyproject.toml             # 项目配置
├── Dockerfile                 # Docker镜像
└── docker-compose.yml         # Docker编排
```

---

## 3. 数据库设计

### 3.1 数据模型

#### 用户表 (users)
```python
class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)          # UUID
    phone = Column(String(11), unique=True, index=True) # 手机号
    password_hash = Column(String(255))                # 密码哈希
    nickname = Column(String(50))                       # 昵称
    avatar = Column(String(255))                        # 头像URL
    gender = Column(String(10))                         # 性别
    age = Column(Integer)                               # 年龄
    height = Column(Integer)                            # 身高(cm)
    weight = Column(Integer)                            # 体重(kg)
    is_active = Column(Boolean, default=True)          # 是否激活
    created_at = Column(DateTime)                      # 创建时间
    updated_at = Column(DateTime)                      # 更新时间
```

#### 设备表 (devices)
```python
class Device(Base):
    __tablename__ = "devices"

    id = Column(String(36), primary_key=True)
    name = Column(String(100))                         # 设备名称
    type = Column(String(50))                          # 设备类型
    model = Column(String(100))                        # 型号
    manufacturer = Column(String(100))                  # 制造商
    status = Column(String(20), default="offline")     # 在线状态
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
```

#### 设备连接表 (device_connections)
```python
class DeviceConnection(Base):
    __tablename__ = "device_connections"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"))
    device_id = Column(String(36), ForeignKey("devices.id"))
    device_name = Column(String(100))
    is_connected = Column(Boolean, default=False)
    connected_at = Column(DateTime)
    last_heartbeat = Column(DateTime)
    created_at = Column(DateTime)
```

#### AI采集表 (ai_captures)
```python
class AICapture(Base):
    __tablename__ = "ai_captures"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"))
    session_id = Column(String(36), ForeignKey("therapy_sessions.id"))
    image_path = Column(String(255))                   # 图像路径
    capture_time = Column(DateTime)
    created_at = Column(DateTime)
```

#### AI分析表 (ai_analyses)
```python
class AIAnalysis(Base):
    __tablename__ = "ai_analyses"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"))
    capture_id = Column(String(36), ForeignKey("ai_captures.id"))
    result = Column(Text)                              # 分析结果
    body_parts = Column(Text)                         # 部位(JSON数组)
    pressure_level = Column(Integer)                 # 压力等级
    recommendations = Column(Text)                   # 建议
    status = Column(String(20), default="pending")
    analyzed_at = Column(DateTime)
    created_at = Column(DateTime)
```

#### 理疗方法表 (therapy_methods)
```python
class TherapyMethod(Base):
    __tablename__ = "therapy_methods"

    id = Column(String(36), primary_key=True)
    name = Column(String(100))                        # 方法名称
    type = Column(String(50))                         # 方法类型
    description = Column(Text)                       # 描述
    default_duration = Column(Integer, default=30)   # 默认时长(分钟)
    params_schema = Column(Text)                     # 参数Schema
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime)
```

#### 理疗会话表 (therapy_sessions)
```python
class TherapySession(Base):
    __tablename__ = "therapy_sessions"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"))
    device_id = Column(String(36), ForeignKey("devices.id"))
    device_name = Column(String(100))
    methods = Column(Text)                            # 手法(JSON数组)
    params = Column(Text)                             # 参数(JSON)
    status = Column(String(20), default="pending")  # pending/running/paused/completed
    started_at = Column(DateTime)
    paused_at = Column(DateTime)
    resumed_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration = Column(Integer, default=0)             # 已运行时长(秒)
    total_duration = Column(Integer, default=0)       # 总时长(秒)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
```

---

## 4. API 接口设计

### 4.1 认证接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/auth/login | 用户登录 |
| POST | /api/v1/auth/register | 用户注册 |
| POST | /api/v1/auth/refresh-token | 刷新Token |
| POST | /api/v1/auth/logout | 登出 |
| POST | /api/v1/auth/change-password | 修改密码 |

### 4.2 用户接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/users/profile | 获取个人信息 |
| PUT | /api/v1/users/profile | 更新个人信息 |

### 4.3 设备接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/devices | 获取设备列表 |
| GET | /api/v1/devices/{device_id} | 获取设备详情 |
| POST | /api/v1/devices/{device_id}/bind | 绑定设备 |
| POST | /api/v1/devices/{device_id}/unbind | 解绑设备 |
| POST | /api/v1/devices/{device_id}/connect | 连接设备 |
| POST | /api/v1/devices/{device_id}/disconnect | 断开设备 |
| GET | /api/v1/devices/{device_id}/status | 获取设备状态 |

### 4.4 AI分析接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/ai/capture | 采集图像 |
| POST | /api/v1/ai/analyze | AI分析 |
| GET | /api/v1/ai/analysis/{analysis_id} | 获取分析结果 |
| GET | /api/v1/ai/history | 获取分析历史 |

### 4.5 理疗接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/therapy/methods | 获取理疗方法列表 |
| POST | /api/v1/therapy/sessions | 创建理疗会话 |
| GET | /api/v1/therapy/sessions | 获取理疗历史 |
| GET | /api/v1/therapy/sessions/{session_id} | 获取会话详情 |
| POST | /api/v1/therapy/sessions/{session_id}/start | 开始理疗 |
| POST | /api/v1/therapy/sessions/{session_id}/pause | 暂停理疗 |
| POST | /api/v1/therapy/sessions/{session_id}/resume | 继续理疗 |
| POST | /api/v1/therapy/sessions/{session_id}/stop | 停止理疗 |
| GET | /api/v1/therapy/sessions/{session_id}/status | 获取会话状态 |

---

## 5. 配置说明

### 5.1 环境变量 (.env)

```bash
# 服务配置
ENV=development                    # 运行环境
DEBUG=true                         # 调试模式
HOST=0.0.0.0                      # 服务地址
PORT=8000                          # 服务端口

# 数据库配置
DATABASE_URL=sqlite:///./data/physiotherapy.db

# Redis配置（可选）
REDIS_ENABLED=false
REDIS_URL=redis://localhost:6379

# JWT配置
SECRET_KEY=your-secret-key         # 密钥
ALGORITHM=HS256                    # 算法
ACCESS_TOKEN_EXPIRE_MINUTES=60     # Access Token过期时间
REFRESH_TOKEN_EXPIRE_DAYS=7        # Refresh Token过期时间

# CORS配置
CORS_ORIGINS=http://localhost:5173
```

---

## 6. 开发指南

### 6.1 开发环境搭建

```bash
# 1. 进入后端目录
cd backend

# 2. 创建虚拟环境
python -m venv venv

# 3. 激活虚拟环境
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 4. 安装依赖
pip install -r requirements.txt

# 5. 初始化数据库
python -m app.scripts.init_db

# 6. 启动服务
uvicorn app.main:app --reload --port 8000
```

### 6.2 Docker 部署

```bash
# 1. 构建镜像
docker build -t physiotherapy-backend .

# 2. 运行容器
docker run -d -p 8000:8000 --name physiotherapy-backend physiotherapy-backend
```

### 6.3 Docker Compose 一键部署

```bash
# 在项目根目录
docker-compose up -d
```

---

## 7. 测试账号

| 手机号 | 密码 | 说明 |
|--------|------|------|
| 13800138000 | 123456 | 测试用户 |

---

## 8. API 文档

启动服务后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 9. 依赖说明

| 依赖包 | 版本 | 说明 |
|--------|------|------|
| fastapi | >=0.100.0 | Web框架 |
| uvicorn[standard] | >=0.23.0 | ASGI服务器 |
| sqlalchemy | >=2.0.0 | ORM |
| aiosqlite | >=0.19.0 | 异步SQLite驱动 |
| pydantic | >=2.0.0 | 数据验证 |
| pydantic-settings | >=2.0.0 | 设置管理 |
| python-jose[cryptography] | >=3.3.0 | JWT编解码 |
| passlib[bcrypt] | >=1.7.4 | 密码加密 |
| bcrypt | 4.0.1 | 密码哈希 |
| python-multipart | >=0.0.6 | 表单解析 |
| loguru | >=0.9.0 | 日志记录 |

---

## 10. 注意事项

1. **数据库路径**：Windows环境下需使用绝对路径或正确处理相对路径
2. **密码版本**：bcrypt 版本需锁定为 4.0.1，避免兼容性问题
3. **CORS配置**：生产环境需修改允许的跨域来源
4. **密钥安全**：生产环境务必修改 SECRET_KEY

---

*文档更新时间: 2026-04-10*
