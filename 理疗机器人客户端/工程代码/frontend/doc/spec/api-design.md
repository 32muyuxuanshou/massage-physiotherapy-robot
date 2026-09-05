# 颐本智能理疗系统 - 接口设计文档

> **历史接口设计稿**：本文记录 2026-04-10 的前期目标，其中“待实现/Mock/MySQL/3000 端口”等说法不代表当前运行态。当前接口以 FastAPI Swagger 和代码为准，部署以项目根目录 `DEPLOY.md` 与 `Docker傻瓜式操作教程.md` 为准。

**版本**: V0.1
**日期**: 2026-04-10
**状态**: 待实现（V0.1使用Mock数据，V0.2接入真实API）
**作者**: 开发团队

---

## 1. 文档说明

本文档描述颐本智能理疗系统前端与后端API的接口规范。

**当前状态**: V0.1版本前端使用本地Mock数据，本文档定义的后端接口将在V0.2版本实现并对接。

**说明**: V0.1版本所有数据存储在前端内存中，使用localStorage进行简单持久化，未实现真正的HTTP请求。

---

## 2. 基础信息

### 2.1 服务配置

| 配置项 | 值 |
|--------|-----|
| 基础URL | `/api/v1` |
| 数据格式 | JSON |
| 编码格式 | UTF-8 |
| 认证方式 | Bearer Token (JWT) |
| 跨域策略 | CORS |

### 2.2 开发环境

| 环境 | 地址 |
|------|------|
| 开发服务器 | `http://localhost:3000` |
| 前端开发服务器 | `http://localhost:5173` |
| 数据库 | MySQL 8.0+ |
| 缓存 | Redis 6.0+ |

### 2.3 技术栈建议

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| 后端语言 | Python 3.10+ | 简洁高效，数据处理能力强 |
| Web框架 | FastAPI | 现代异步框架，自动API文档，高性能 |
| 数据库 | SQLite 3 | 轻量级，无需配置，适合开发和小型部署 |
| ORM | SQLAlchemy 2.0 | 成熟的ORM，支持异步，支持多种数据库 |
| 数据库迁移 | Alembic | 数据库版本管理和迁移 |
| 缓存（可选） | Redis 6.0+ | 高性能缓存，Session存储，Token黑名单（未来扩展） |
| 认证 | JWT (python-jose) | 无状态认证，支持Access/Refresh Token |
| 密码加密 | passlib + bcrypt | 安全密码哈希 |
| 验证 | Pydantic | 数据验证和序列化 |
| 日志 | loguru | 现代化日志库 |
| 文档 | Swagger/OpenAPI (内置) | 自动API文档 |
| 测试 | pytest | Python标准测试框架 |
| 部署 | Docker + uvicorn/gunicorn | ASGI服务器，容器化部署 |

### 2.4 为什么选择这些技术

1. **Python + FastAPI**: 开发效率高，异步支持优秀，自动Swagger文档，类型安全
2. **SQLite**: 零配置，零维护，适合开发测试，生产环境可迁移到PostgreSQL/MySQL
3. **SQLAlchemy 2.0**: 功能强大，支持异步，兼容多种数据库，未来可无缝切换
4. **Pydantic**: FastAPI核心依赖，数据验证和序列化，与类型提示完美结合
5. **Redis兼容性**: 通过依赖注入实现，代码编写时考虑Redis扩展，无Redis时使用内存缓存

---

## 3. 通用规范

### 3.1 通用响应格式

#### 成功响应

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    // 业务数据
  },
  "timestamp": "2026-04-10T10:30:00.000Z"
}
```

#### 错误响应

```json
{
  "code": 400,
  "message": "错误描述信息",
  "errors": [
    {
      "field": "phone",
      "message": "手机号格式不正确"
    }
  ],
  "timestamp": "2026-04-10T10:30:00.000Z"
}
```

### 3.2 错误码定义

| 错误码 | HTTP状态码 | 说明 |
|--------|-----------|------|
| 200 | 200 | 成功 |
| 400 | 400 | 请求参数错误 |
| 401 | 401 | 未登录或Token过期 |
| 403 | 403 | 无权限访问 |
| 404 | 404 | 资源不存在 |
| 409 | 409 | 资源冲突 |
| 422 | 422 | 验证失败 |
| 500 | 500 | 服务器内部错误 |

### 3.3 分页响应格式

```json
{
  "code": 200,
  "message": "查询成功",
  "data": {
    "list": [],
    "pagination": {
      "page": 1,
      "pageSize": 10,
      "total": 100,
      "totalPages": 10
    }
  }
}
```

### 3.4 请求头规范

| 头信息 | 说明 | 必需 |
|--------|------|------|
| Content-Type | application/json | 是 |
| Authorization | Bearer {token} | 是（除登录接口） |
| Accept | application/json | 是 |

---

## 4. 认证模块

### 4.1 用户登录

**接口地址**: `POST /api/v1/auth/login`

**请求参数**:

```json
{
  "phone": "13800138000",
  "password": "123456"
}
```

**请求示例**:

```bash
curl -X POST http://localhost:3000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"phone":"13800138000","password":"123456"}'
```

**成功响应**:

```json
{
  "code": 200,
  "message": "登录成功",
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refreshToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "userInfo": {
      "id": "user-001",
      "phone": "13800138000",
      "name": "小雪",
      "avatar": ""
    }
  }
}
```

**错误响应**:

```json
{
  "code": 401,
  "message": "手机号或密码错误",
  "errors": null
}
```

### 4.2 用户注册

**接口地址**: `POST /api/v1/auth/register`

**请求参数**:

```json
{
  "phone": "13800138001",
  "password": "123456",
  "name": "新用户",
  "code": "123456"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| phone | string | 是 | 手机号（11位数字） |
| password | string | 是 | 密码（6-20位） |
| name | string | 是 | 用户名（2-20字符） |
| code | string | 是 | 验证码（6位数字） |

**成功响应**:

```json
{
  "code": 200,
  "message": "注册成功",
  "data": {
    "userId": "user-002",
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

### 4.3 发送验证码

**接口地址**: `POST /api/v1/auth/send-code`

**请求参数**:

```json
{
  "phone": "13800138000",
  "type": "register"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| phone | string | 是 | 手机号 |
| type | string | 是 | 验证码类型：register/login/changePassword |

**成功响应**:

```json
{
  "code": 200,
  "message": "验证码发送成功",
  "data": {
    "expiresIn": 300
  }
}
```

### 4.4 退出登录

**接口地址**: `POST /api/v1/auth/logout`

**请求头**: `Authorization: Bearer {token}`

**成功响应**:

```json
{
  "code": 200,
  "message": "退出登录成功"
}
```

### 4.5 刷新Token

**接口地址**: `POST /api/v1/auth/refresh-token`

**请求参数**:

```json
{
  "refreshToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**成功响应**:

```json
{
  "code": 200,
  "message": "Token刷新成功",
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refreshToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

### 4.6 修改密码

**接口地址**: `POST /api/v1/auth/change-password`

**请求头**: `Authorization: Bearer {token}`

**请求参数**:

```json
{
  "oldPassword": "123456",
  "newPassword": "654321"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| oldPassword | string | 是 | 当前密码 |
| newPassword | string | 是 | 新密码（6-20位） |

**成功响应**:

```json
{
  "code": 200,
  "message": "密码修改成功"
}
```

---

## 5. 用户模块

### 5.1 获取用户信息

**接口地址**: `GET /api/v1/users/profile`

**请求头**: `Authorization: Bearer {token}`

**成功响应**:

```json
{
  "code": 200,
  "message": "查询成功",
  "data": {
    "id": "user-001",
    "phone": "138****8000",
    "name": "小雪",
    "avatar": "",
    "createdAt": "2026-04-03T10:00:00.000Z",
    "updatedAt": "2026-04-10T10:00:00.000Z"
  }
}
```

### 5.2 更新用户信息

**接口地址**: `PUT /api/v1/users/profile`

**请求头**: `Authorization: Bearer {token}`

**请求参数**:

```json
{
  "name": "小雪",
  "avatar": "https://example.com/avatar.jpg"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 否 | 用户名（2-20字符） |
| avatar | string | 否 | 头像URL |

**成功响应**:

```json
{
  "code": 200,
  "message": "更新成功",
  "data": {
    "id": "user-001",
    "phone": "138****8000",
    "name": "小雪",
    "avatar": "https://example.com/avatar.jpg"
  }
}
```

---

## 6. 设备模块

### 6.1 获取设备列表

**接口地址**: `GET /api/v1/devices`

**请求头**: `Authorization: Bearer {token}`

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| type | string | 否 | 设备类型：massage/moxibustion/light-therapy/fat-reduction |

**成功响应**:

```json
{
  "code": 200,
  "message": "查询成功",
  "data": [
    {
      "id": "device-1",
      "name": "按摩机器人",
      "type": "massage",
      "icon": "按摩机器人",
      "model": "瑞尔曼",
      "manufacturer": "瑞尔曼医疗科技",
      "description": "智能按摩理疗机器人",
      "status": {
        "camera": "online",
        "arm": "online",
        "head": "online"
      },
      "connected": false,
      "lastConnected": null
    }
  ]
}
```

### 6.2 获取设备详情

**接口地址**: `GET /api/v1/devices/:id`

**请求头**: `Authorization: Bearer {token}`

**路径参数**: `id` - 设备ID

**成功响应**:

```json
{
  "code": 200,
  "message": "查询成功",
  "data": {
    "id": "device-1",
    "name": "按摩机器人",
    "type": "massage",
    "icon": "按摩机器人",
    "model": "瑞尔曼",
    "manufacturer": "瑞尔曼医疗科技",
    "description": "智能按摩理疗机器人",
    "specifications": {
      "dimensions": "1200x600x800mm",
      "weight": "80kg",
      "power": "220V/50Hz",
      "powerConsumption": "500W"
    },
    "status": {
      "camera": "online",
      "arm": "online",
      "head": "online"
    },
    "connected": false,
    "lastConnected": null,
    "usageCount": 0,
    "createdAt": "2026-04-01T00:00:00.000Z"
  }
}
```

### 6.3 连接设备

**接口地址**: `POST /api/v1/devices/:id/connect`

**请求头**: `Authorization: Bearer {token}`

**路径参数**: `id` - 设备ID

**成功响应**:

```json
{
  "code": 200,
  "message": "设备连接成功",
  "data": {
    "deviceId": "device-1",
    "connected": true,
    "connectionId": "conn-123456",
    "connectedAt": "2026-04-10T10:30:00.000Z"
  }
}
```

### 6.4 断开设备

**接口地址**: `POST /api/v1/devices/:id/disconnect`

**请求头**: `Authorization: Bearer {token}`

**路径参数**: `id` - 设备ID

**成功响应**:

```json
{
  "code": 200,
  "message": "设备已断开",
  "data": {
    "deviceId": "device-1",
    "connected": false,
    "disconnectedAt": "2026-04-10T11:00:00.000Z"
  }
}
```

### 6.5 获取设备状态

**接口地址**: `GET /api/v1/devices/:id/status`

**请求头**: `Authorization: Bearer {token}`

**路径参数**: `id` - 设备ID

**成功响应**:

```json
{
  "code": 200,
  "message": "查询成功",
  "data": {
    "deviceId": "device-1",
    "status": {
      "camera": "online",
      "arm": "online",
      "head": "online"
    },
    "temperature": 25.5,
    "humidity": 60,
    "uptime": 86400,
    "lastUpdate": "2026-04-10T10:30:00.000Z"
  }
}
```

---

## 7. AI分析模块

### 7.1 采集图像

**接口地址**: `POST /api/v1/ai/capture`

**请求头**: `Authorization: Bearer {token}`

**请求参数**:

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| deviceId | string | 是 | 设备ID |
| position | string | 否 | 拍摄位置：front/back/left/right |

**成功响应**:

```json
{
  "code": 200,
  "message": "图像采集成功",
  "data": {
    "captureId": "cap-123456",
    "imageUrl": "https://example.com/captures/cap-123456.jpg",
    "capturedAt": "2026-04-10T10:30:00.000Z",
    "deviceId": "device-1"
  }
}
```

### 7.2 执行AI分析

**接口地址**: `POST /api/v1/ai/analyze`

**请求头**: `Authorization: Bearer {token}`

**请求参数**:

```json
{
  "deviceId": "device-1",
  "captureId": "cap-123456"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| deviceId | string | 是 | 设备ID |
| captureId | string | 是 | 采集ID |

**成功响应**:

```json
{
  "code": 200,
  "message": "分析完成",
  "data": {
    "analysisId": "analysis-123456",
    "captureId": "cap-123456",
    "analyzed": true,
    "regions": [
      {
        "name": "背部",
        "position": "back",
        "confidence": 0.95,
        "area": 1250.5,
        "recommendedMethods": ["tuina", "niannie"]
      },
      {
        "name": "腰部",
        "position": "waist",
        "confidence": 0.92,
        "area": 450.2,
        "recommendedMethods": ["xuewei", "niannie"]
      },
      {
        "name": "腿部",
        "position": "legs",
        "confidence": 0.88,
        "area": 890.3,
        "recommendedMethods": ["paida", "tuina"]
      }
    ],
    "summary": "检测到3个理疗区域，建议使用推拿和揉捏手法",
    "analyzedAt": "2026-04-10T10:32:00.000Z"
  }
}
```

### 7.3 获取分析结果

**接口地址**: `GET /api/v1/ai/analysis/:id`

**请求头**: `Authorization: Bearer {token}`

**路径参数**: `id` - 分析记录ID

**成功响应**:

```json
{
  "code": 200,
  "message": "查询成功",
  "data": {
    "analysisId": "analysis-123456",
    "captureId": "cap-123456",
    "deviceId": "device-1",
    "userId": "user-001",
    "analyzed": true,
    "regions": [],
    "summary": "检测到3个理疗区域",
    "analyzedAt": "2026-04-10T10:32:00.000Z",
    "createdAt": "2026-04-10T10:30:00.000Z"
  }
}
```

---

## 8. 理疗模块

### 8.1 获取理疗手法列表

**接口地址**: `GET /api/v1/therapy/methods`

**请求头**: `Authorization: Bearer {token}`

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| type | string | 否 | 手法类型：tuina/xuewei/niannie/paida |

**成功响应**:

```json
{
  "code": 200,
  "message": "查询成功",
  "data": [
    {
      "type": "tuina",
      "name": "推拿手法",
      "description": "传统按摩手法，通过按压、揉捏等动作放松肌肉",
      "suitableRegions": ["back", "waist", "legs"],
      "defaultDuration": 30,
      "icon": "tuina"
    },
    {
      "type": "xuewei",
      "name": "点穴疗法",
      "description": "通过按压穴位，调理气血流通",
      "suitableRegions": ["back", "waist"],
      "defaultDuration": 30,
      "icon": "xuewei"
    },
    {
      "type": "niannie",
      "name": "揉捏技法",
      "description": "通过揉捏动作，深度放松肌肉组织",
      "suitableRegions": ["back", "legs"],
      "defaultDuration": 30,
      "icon": "niannie"
    },
    {
      "type": "paida",
      "name": "拍打疗法",
      "description": "通过拍打动作，促进血液循环",
      "suitableRegions": ["back", "waist", "legs"],
      "defaultDuration": 30,
      "icon": "paida"
    }
  ]
}
```

### 8.2 创建理疗方案

**接口地址**: `POST /api/v1/therapy/sessions`

**请求头**: `Authorization: Bearer {token}`

**请求参数**:

```json
{
  "deviceId": "device-1",
  "analysisId": "analysis-123456",
  "methods": [
    {
      "type": "tuina",
      "duration": 30
    },
    {
      "type": "niannie",
      "duration": 20
    }
  ],
  "params": {
    "height": 50,
    "speed": 50,
    "intensity": 3
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| deviceId | string | 是 | 设备ID |
| analysisId | string | 否 | 分析记录ID |
| methods | array | 是 | 理疗手法列表 |
| methods[].type | string | 是 | 手法类型 |
| methods[].duration | number | 是 | 时长（分钟） |
| params | object | 是 | 理疗参数 |
| params.height | number | 是 | 高度（0-100） |
| params.speed | number | 是 | 速度（0-100） |
| params.intensity | number | 是 | 力度（0-5） |

**成功响应**:

```json
{
  "code": 200,
  "message": "理疗方案创建成功",
  "data": {
    "sessionId": "session-123456",
    "deviceId": "device-1",
    "status": "ready",
    "totalDuration": 3000,
    "methods": [],
    "params": {
      "height": 50,
      "speed": 50,
      "intensity": 3
    },
    "createdAt": "2026-04-10T10:35:00.000Z"
  }
}
```

### 8.3 开始理疗

**接口地址**: `POST /api/v1/therapy/sessions/:id/start`

**请求头**: `Authorization: Bearer {token}`

**路径参数**: `id` - 理疗会话ID

**成功响应**:

```json
{
  "code": 200,
  "message": "理疗已开始",
  "data": {
    "sessionId": "session-123456",
    "status": "running",
    "startTime": "2026-04-10T10:36:00.000Z",
    "remainingTime": 3000
  }
}
```

### 8.4 暂停理疗

**接口地址**: `POST /api/v1/therapy/sessions/:id/pause`

**请求头**: `Authorization: Bearer {token}`

**路径参数**: `id` - 理疗会话ID

**成功响应**:

```json
{
  "code": 200,
  "message": "理疗已暂停",
  "data": {
    "sessionId": "session-123456",
    "status": "paused",
    "pausedAt": "2026-04-10T10:40:00.000Z",
    "remainingTime": 2400
  }
}
```

### 8.5 继续理疗

**接口地址**: `POST /api/v1/therapy/sessions/:id/resume`

**请求头**: `Authorization: Bearer {token}`

**路径参数**: `id` - 理疗会话ID

**成功响应**:

```json
{
  "code": 200,
  "message": "理疗已继续",
  "data": {
    "sessionId": "session-123456",
    "status": "running",
    "resumeAt": "2026-04-10T10:42:00.000Z",
    "remainingTime": 2280
  }
}
```

### 8.6 停止理疗

**接口地址**: `POST /api/v1/therapy/sessions/:id/stop`

**请求头**: `Authorization: Bearer {token}`

**路径参数**: `id` - 理疗会话ID

**成功响应**:

```json
{
  "code": 200,
  "message": "理疗已停止",
  "data": {
    "sessionId": "session-123456",
    "status": "completed",
    "stoppedAt": "2026-04-10T10:45:00.000Z",
    "elapsedTime": 540,
    "statistics": {
      "totalMethods": 2,
      "completedMethods": 1,
      "totalDuration": 3000,
      "elapsedDuration": 540,
      "efficiency": 18.0
    }
  }
}
```

### 8.7 获取理疗状态

**接口地址**: `GET /api/v1/therapy/sessions/:id/status`

**请求头**: `Authorization: Bearer {token}`

**路径参数**: `id` - 理疗会话ID

**成功响应**:

```json
{
  "code": 200,
  "message": "查询成功",
  "data": {
    "sessionId": "session-123456",
    "deviceId": "device-1",
    "status": "running",
    "startTime": "2026-04-10T10:36:00.000Z",
    "elapsedTime": 600,
    "remainingTime": 2400,
    "currentMethod": "tuina",
    "currentMethodElapsed": 600,
    "currentMethodRemaining": 1200
  }
}
```

### 8.8 获取理疗记录列表

**接口地址**: `GET /api/v1/therapy/sessions`

**请求头**: `Authorization: Bearer {token}`

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | number | 否 | 页码（默认1） |
| pageSize | number | 否 | 每页数量（默认10） |
| status | string | 否 | 状态：completed/cancelled |

**成功响应**:

```json
{
  "code": 200,
  "message": "查询成功",
  "data": {
    "list": [
      {
        "sessionId": "session-123456",
        "deviceId": "device-1",
        "deviceName": "按摩机器人",
        "status": "completed",
        "totalDuration": 3000,
        "elapsedDuration": 3000,
        "methods": [],
        "createdAt": "2026-04-10T10:35:00.000Z",
        "completedAt": "2026-04-10T10:50:00.000Z"
      }
    ],
    "pagination": {
      "page": 1,
      "pageSize": 10,
      "total": 50,
      "totalPages": 5
    }
  }
}
```

### 8.9 获取理疗记录详情

**接口地址**: `GET /api/v1/therapy/sessions/:id`

**请求头**: `Authorization: Bearer {token}`

**路径参数**: `id` - 理疗会话ID

**成功响应**:

```json
{
  "code": 200,
  "message": "查询成功",
  "data": {
    "sessionId": "session-123456",
    "userId": "user-001",
    "deviceId": "device-1",
    "deviceName": "按摩机器人",
    "analysisId": "analysis-123456",
    "status": "completed",
    "methods": [],
    "params": {
      "height": 50,
      "speed": 50,
      "intensity": 3
    },
    "startTime": "2026-04-10T10:36:00.000Z",
    "endTime": "2026-04-10T10:50:00.000Z",
    "totalDuration": 3000,
    "elapsedDuration": 3000,
    "statistics": {
      "efficiency": 100.0,
      "pauseCount": 0,
      "totalPausedTime": 0
    },
    "createdAt": "2026-04-10T10:35:00.000Z"
  }
}
```

---

## 9. 数据模型设计

### 9.1 数据库选型

- **数据库**: SQLite 3（开发/测试）、支持PostgreSQL/MySQL（生产）
- **ORM**: SQLAlchemy 2.0
- **迁移工具**: Alembic
- **缓存**: Redis（可选，通过依赖注入保持兼容性）

### 9.2 数据表设计

#### users（用户表）

```sql
CREATE TABLE users (
  id VARCHAR(36) PRIMARY KEY,
  phone VARCHAR(11) NOT NULL UNIQUE,
  password VARCHAR(255) NOT NULL,
  name VARCHAR(20) NOT NULL,
  avatar VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_phone (phone)
);
```

#### devices（设备表）

```sql
CREATE TABLE devices (
  id VARCHAR(36) PRIMARY KEY,
  name VARCHAR(50) NOT NULL,
  type VARCHAR(20) NOT NULL,
  icon VARCHAR(50),
  model VARCHAR(50),
  manufacturer VARCHAR(100),
  description TEXT,
  specifications TEXT,
  status TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_type (type)
);
```

#### device_connections（设备连接表）

```sql
CREATE TABLE device_connections (
  id VARCHAR(36) PRIMARY KEY,
  device_id VARCHAR(36) NOT NULL,
  user_id VARCHAR(36) NOT NULL,
  status VARCHAR(20) NOT NULL,
  connected_at TIMESTAMP,
  disconnected_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (device_id) REFERENCES devices(id),
  FOREIGN KEY (user_id) REFERENCES users(id)
);
```

#### ai_captures（AI采集记录表）

```sql
CREATE TABLE ai_captures (
  id VARCHAR(36) PRIMARY KEY,
  user_id VARCHAR(36) NOT NULL,
  device_id VARCHAR(36) NOT NULL,
  image_url VARCHAR(255) NOT NULL,
  position VARCHAR(20),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (device_id) REFERENCES devices(id)
);
```

#### ai_analyses（AI分析记录表）

```sql
CREATE TABLE ai_analyses (
  id VARCHAR(36) PRIMARY KEY,
  user_id VARCHAR(36) NOT NULL,
  device_id VARCHAR(36) NOT NULL,
  capture_id VARCHAR(36) NOT NULL UNIQUE,
  regions TEXT NOT NULL,
  summary TEXT,
  analyzed_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (device_id) REFERENCES devices(id),
  FOREIGN KEY (capture_id) REFERENCES ai_captures(id)
);
```

#### therapy_sessions（理疗会话表）

```sql
CREATE TABLE therapy_sessions (
  id VARCHAR(36) PRIMARY KEY,
  user_id VARCHAR(36) NOT NULL,
  device_id VARCHAR(36) NOT NULL,
  analysis_id VARCHAR(36),
  status VARCHAR(20) NOT NULL,
  methods TEXT NOT NULL,
  params TEXT NOT NULL,
  total_duration INTEGER NOT NULL,
  elapsed_duration INTEGER DEFAULT 0,
  start_time TIMESTAMP,
  end_time TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (device_id) REFERENCES devices(id),
  FOREIGN KEY (analysis_id) REFERENCES ai_analyses(id)
);
```

#### refresh_tokens（刷新Token表）

```sql
CREATE TABLE refresh_tokens (
  id VARCHAR(36) PRIMARY KEY,
  user_id VARCHAR(36) NOT NULL,
  token VARCHAR(255) NOT NULL UNIQUE,
  expires_at TIMESTAMP NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id),
  INDEX idx_token (token),
  INDEX idx_user_id (user_id)
);
```

**注意**: SQLite不支持JSON类型字段，使用TEXT类型存储JSON数据，SQLAlchemy会自动处理序列化/反序列化。

---

## 10. 安全性设计

### 10.1 认证与授权

- 使用JWT实现无状态认证
- Access Token有效期：1小时
- Refresh Token有效期：7天
- Token存储在HTTP Only Cookie或LocalStorage

### 10.2 密码安全

- 密码使用bcrypt加密存储
- 密码强度：6-20位
- 登录失败锁定：连续5次失败后锁定15分钟

### 10.3 数据安全

- 所有API使用HTTPS
- 输入数据验证和过滤
- SQL注入防护（使用ORM）
- XSS防护

### 10.4 速率限制

- 登录接口：5次/分钟
- 注册接口：3次/分钟
- 通用接口：100次/分钟

---

## 11. 部署架构

### 11.1 Docker部署

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=sqlite:///./data/physiotherapy.db
      - REDIS_URL=redis://cache:6379
      - SECRET_KEY=your-secret-key
      - ACCESS_TOKEN_EXPIRE_MINUTES=60
      - REFRESH_TOKEN_EXPIRE_DAYS=7
    volumes:
      - ./data:/app/data
      - ./uploads:/app/uploads
    depends_on:
      - cache
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000

  cache:
    image: redis:6.0-alpine
    volumes:
      - redis_data:/data

volumes:
  redis_data:
```

### 11.2 环境变量配置

```env
# 环境配置
ENVIRONMENT=development
DEBUG=true

# 服务配置
HOST=0.0.0.0
PORT=8000

# 数据库配置（开发环境使用SQLite）
DATABASE_URL=sqlite:///./data/physiotherapy.db

# 数据库配置（生产环境可切换为PostgreSQL/MySQL）
# DATABASE_URL=postgresql://user:pass@localhost:5432/physiotherapy

# Redis配置（可选，代码应兼容无Redis情况）
REDIS_URL=redis://localhost:6379
REDIS_ENABLED=false

# 安全配置
SECRET_KEY=your-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

# 文件上传
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=10485760

# CORS配置
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

---

## 12. API测试

### 12.1 测试账号

| 账号 | 密码 | 说明 |
|------|------|------|
| 13800138000 | 123456 | 测试用户 |
| 13800138001 | 123456 | 测试用户2 |

### 12.2 测试脚本

```bash
# API基础URL
BASE_URL=http://localhost:8000/api/v1

# 1. 登录获取Token
curl -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"phone":"13800138000","password":"123456"}'

# 2. 使用Token获取设备列表
curl -X GET "$BASE_URL/devices" \
  -H "Authorization: Bearer $TOKEN"

# 3. 采集图像
curl -X POST "$BASE_URL/ai/capture" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"deviceId":"device-1"}'

# 4. 创建理疗会话
curl -X POST "$BASE_URL/therapy/sessions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"deviceId":"device-1","methods":[{"type":"tuina","duration":30}],"params":{"height":50,"speed":50,"intensity":3}}'
```

### 12.3 Swagger文档

FastAPI自动生成交互式API文档：

- 开发环境: http://localhost:8000/docs
- 生产环境: http://your-domain.com/docs

---

## 13. 更新日志

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-04-10 | V0.1 | 初始化接口设计文档 |
