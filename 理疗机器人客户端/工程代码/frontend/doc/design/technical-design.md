# 详细技术设计文档

**版本**: V0.1
**日期**: 2026-04-10
**状态**: 一期核心功能完成

---

## 1. 技术架构设计

### 1.1 系统架构图

```
┌─────────────────────────────────────────────────────────┐
│                    前端应用 (SPA)                        │
├─────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │
│  │ Vue 3   │  │ Router  │  │ Pinia   │  │ axios   │   │
│  │(框架)   │  │(路由)   │  │(状态)   │  │(HTTP)  │   │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘   │
├─────────────────────────────────────────────────────────┤
│                    公共层                                │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                │
│  │ 组件库  │  │ 样式    │  │ 工具函数│                │
│  └─────────┘  └─────────┘  └─────────┘                │
├─────────────────────────────────────────────────────────┤
│                    业务层                                │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  │
│  │ 登录页  │  │设备选择 │  │AI分析页 │  │理疗管理 │  │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘  │
└─────────────────────────────────────────────────────────┘
                          ↓
                    后端API (预留)
```

### 1.2 技术栈详情

| 类别 | 技术选型 | 版本 |
|------|---------|------|
| 核心框架 | Vue 3 | ^3.4.0 |
| 构建工具 | Vite | ^6.4.3 |
| 路由 | Vue Router | ^4.2.0 |
| 状态管理 | Pinia | ^2.1.0 |
| HTTP客户端 | Axios | ^1.19.0 |
| 图标 | Lucide Vue | ^0.300.0 |
| CSS预处理器 | SCSS | ^1.69.0 |
| 代码规范 | ESLint | 当前未配置 |
| 代码格式化 | Prettier | ^3.8.0 |

---

## 2. 项目结构设计

### 2.1 目录结构（实际实现）

```
frontend/
├── src/
│   ├── assets/                 # 资源文件
│   │   ├── icons/             # SVG图标资源
│   │   │   ├── 按摩机器人.svg
│   │   │   ├── 艾灸机器人.svg
│   │   │   ├── 光疗嫩肤机器人.svg
│   │   │   ├── 超声减脂机器人.svg
│   │   │   ├── 推拿手法.svg
│   │   │   ├── 点穴手法.svg
│   │   │   ├── 揉捏手法.svg
│   │   │   └── 拍打手法.svg
│   │   ├── images/           # 图片资源
│   │   │   └── background.png
│   │   └── styles/           # 全局样式
│   │       └── global.scss   # 全局样式
│   ├── components/           # 组件
│   │   ├── common/           # 通用组件
│   │   │   ├── BaseButton.vue
│   │   │   ├── BaseInput.vue
│   │   │   ├── BaseModal.vue
│   │   │   ├── ConfirmModal.vue
│   │   │   ├── DurationSlider.vue
│   │   │   ├── MethodSelector.vue
│   │   │   └── ParamsSettings.vue
│   │   └── layout/           # 布局组件
│   │       ├── AppHeader.vue
│   │       └── StepProgress.vue
│   ├── router/               # 路由配置
│   │   └── index.js
│   ├── stores/               # Pinia状态管理
│   │   ├── user.js
│   │   ├── device.js
│   │   └── therapy.js
│   ├── views/                # 页面视图
│   │   ├── Login/Login.vue
│   │   ├── Home/Home.vue
│   │   ├── AiAnalysis/AiAnalysis.vue
│   │   └── TherapyManagement/TherapyManagement.vue
│   ├── App.vue               # 根组件
│   └── main.js              # 入口文件
├── doc/                      # 项目文档
├── ui/                       # UI设计图
├── index.html
├── package.json
└── vite.config.js
```

**说明**:
- 本期未使用composables目录，组合式逻辑直接在各组件中实现
- 本期未使用utils目录，工具函数直接在各组件中实现
- 未实现composables目录，composables目录在V0.2版本规划中
- 业务组件功能直接集成在页面中，未单独拆分

### 2.2 文件命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| Vue组件 | PascalCase | `AppHeader.vue` |
| JavaScript文件 | camelCase | `useTimer.js` |
| SCSS文件 | kebab-case | `_variables.scss` |
| 图片资源 | kebab-case | `device-icon.svg` |

---

## 3. 组件设计

### 3.1 组件层级

```
App.vue
├── AppHeader
│   ├── HomeButton
│   ├── StepProgress
│   └── UserInfo
├── RouterView
│   ├── Login
│   ├── Home
│   │   ├── DeviceCard (×4)
│   │   └── NextButton
│   ├── AiAnalysis
│   │   ├── CameraView
│   │   ├── MethodSelector (Modal)
│   │   └── ActionBar
│   ├── TherapyManagement
│   │   ├── CameraView
│   │   ├── TimerDisplay
│   │   ├── ParamsSettings (Modal)
│   │   └── ControlBar
│   └── Profile
│       └── ProfileModal
└── AppFooter (部分页面)
```

### 3.2 公共组件接口

#### BaseButton

```typescript
interface BaseButtonProps {
  type?: 'primary' | 'secondary' | 'ghost';
  size?: 'small' | 'medium' | 'large';
  disabled?: boolean;
  loading?: boolean;
  icon?: string;
}
```

#### BaseInput

```typescript
interface BaseInputProps {
  modelValue: string;
  type?: 'text' | 'password' | 'tel';
  placeholder?: string;
  disabled?: boolean;
  prefixIcon?: string;
  suffixIcon?: string;
  error?: string;
}
```

#### BaseModal

```typescript
interface BaseModalProps {
  visible: boolean;
  title?: string;
  width?: string | number;
  closable?: boolean;
  maskClosable?: boolean;
}
```

#### StepProgress

```typescript
interface StepItem {
  title: string;
  status: 'completed' | 'current' | 'pending';
}

interface StepProgressProps {
  steps: StepItem[];
  current: number;
}
```

---

## 4. 状态管理设计

### 4.1 Store结构

```
stores/
├── user.js       # 用户状态
├── device.js     # 设备状态
└── therapy.js    # 理疗状态
```

### 4.2 user.js 详细设计

```javascript
// 状态
{
  userInfo: {
    id: '',
    phone: '',
    name: '小雪',
    avatar: '/images/avatar-default.png'
  },
  isLoggedIn: false,
  token: ''
}

// actions
login(phone, password)
logout()
setUserInfo(userInfo)
```

### 4.3 device.js 详细设计

```javascript
// 状态
{
  devices: [
    {
      id: 'device-1',
      name: '按摩机器人',
      icon: 'robot-massage',
      model: '瑞尔曼',
      status: {
        camera: 'online',
        arm: 'online',
        head: 'online'
      },
      connected: false
    },
    // ...其他设备
  ],
  selectedDeviceId: null,
  isConnecting: false
}

// actions
fetchDevices()
selectDevice(deviceId)
connectDevice(deviceId)
disconnectDevice(deviceId)
```

### 4.4 therapy.js 详细设计

```javascript
// 状态
{
  // AI分析结果
  aiAnalysis: {
    modelData: null,
    analyzed: false,
    regions: []  // ['back', 'waist', 'legs']
  },
  
  // 手法选择
  methods: [
    { type: 'tuina', name: '推拿手法', duration: 30 }
  ],
  
  // 理疗参数
  params: {
    height: 50,
    speed: 50,
    intensity: 3
  },
  
  // 理疗状态
  status: 'idle',  // idle | connecting | ready | running | completed
  remainingTime: 0,  // 秒
  startTime: null
}

// actions
setAiAnalysis(data)
addMethod(method)
removeMethod(type)
updateParams(params)
startTherapy()
pauseTherapy()
resumeTherapy()
stopTherapy()
```

---

## 5. 路由设计

### 5.1 路由配置

```javascript
const routes = [
  {
    path: '/',
    redirect: '/login'
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login/Login.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/home',
    name: 'Home',
    component: () => import('@/views/Home/Home.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/ai-analysis',
    name: 'AiAnalysis',
    component: () => import('@/views/AiAnalysis/AiAnalysis.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/therapy-management',
    name: 'TherapyManagement',
    component: () => import('@/views/TherapyManagement/TherapyManagement.vue'),
    meta: { requiresAuth: true }
  }
]
```

### 5.2 路由守卫

```javascript
router.beforeEach((to, from, next) => {
  const userStore = useUserStore()
  
  if (to.meta.requiresAuth && !userStore.isLoggedIn) {
    next('/login')
  } else if (to.path === '/login' && userStore.isLoggedIn) {
    next('/home')
  } else {
    next()
  }
})
```

### 5.3 页面流转

```
/login ──────┐
             ↓
         /home ──────────┐
                        ↓
               /ai-analysis ───────┐
                                   ↓
                          /therapy-management
                                   ↓
                              (结束)
```

---

## 6. 样式系统设计

### 6.1 CSS变量定义

```scss
// 颜色
$color-primary: #E68A4F;
$color-primary-light: #F28C55;
$color-primary-lighter: #FFE4D6;
$color-background: #FFF2E6;
$color-text: #5D4E37;
$color-text-light: #8B7355;
$color-border: #E8DED0;
$color-success: #4CAF50;
$color-error: #F44336;

// 圆角
$radius-small: 8px;
$radius-medium: 16px;
$radius-large: 24px;
$radius-full: 999px;

// 间距
$spacing-xs: 4px;
$spacing-sm: 8px;
$spacing-md: 16px;
$spacing-lg: 24px;
$spacing-xl: 32px;

// 字体
$font-family: 'PingFang SC', -apple-system, 'Segoe UI', sans-serif;
$font-size-xs: 12px;
$font-size-sm: 14px;
$font-size-base: 16px;
$font-size-lg: 18px;
$font-size-xl: 22px;
$font-size-xxl: 28px;
```

### 6.2 混合宏

```scss
@mixin flex-center {
  display: flex;
  align-items: center;
  justify-content: center;
}

@mixin card-base {
  background: white;
  border-radius: $radius-large;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

@mixin button-base {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 12px 24px;
  border-radius: $radius-full;
  font-size: $font-size-base;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}
```

---

## 7. 相机实时图像设计

### 7.1 图像流设计

```javascript
// 相机图像配置
const cameraConfig = {
  source: 'device-camera',  // 设备相机
  resolution: { width: 1280, height: 720 },
  fps: 30,
  format: 'video/webm'
}
```

### 7.2 图像显示状态

| 状态 | 显示内容 |
|------|---------|
| 初始 | 显示"等待连接设备"提示 |
| 连接中 | 显示连接加载动画 |
| 已连接 | 显示实时相机画面 |
| 采集中 | 显示采集加载动画 |
| 分析中 | 显示分析加载动画 |
| 已分析 | 显示带分区标记的图像 |

### 7.3 分区标记

AI分析完成后，在图像上叠加显示理疗分区标记：
- 使用半透明颜色覆盖
- 可交互显示分区详情

---

## 8. API接口设计 (预留)

### 8.1 接口列表

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/login | POST | 用户登录 |
| /api/devices | GET | 获取设备列表 |
| /api/devices/:id/connect | POST | 连接设备 |
| /api/devices/:id/disconnect | POST | 断开设备 |
| /api/analysis/start | POST | 启动AI分析 |
| /api/therapy/start | POST | 开始理疗 |
| /api/therapy/pause | POST | 暂停理疗 |
| /api/therapy/stop | POST | 停止理疗 |

### 8.2 Mock数据

开发阶段使用本地Mock数据，接口文档仅供参考。

---

## 9. 性能优化设计

### 9.1 优化策略

| 策略 | 实现方式 |
|------|---------|
| 代码分割 | Vue Router 动态导入 |
| 懒加载 | 组件按需加载 |
| 图片优化 | 使用WebP格式 |
| 图像优化 | 视频流缓存管理 |
| 缓存 | Pinia持久化存储 |

### 9.2 加载优化

```javascript
// 路由懒加载示例
const Login = () => import('@/views/Login/Login.vue')

// 组件异步加载
const BaseModal = defineAsyncComponent(() => 
  import('@/components/common/BaseModal.vue')
)
```

---

## 10. 错误处理设计

### 10.1 错误类型

| 错误类型 | 处理方式 |
|---------|---------|
| 网络错误 | 显示重试提示 |
| 登录过期 | 跳转登录页 |
| 设备异常 | 显示错误提示 |
| 设备相机异常 | 显示重试提示 |

### 10.2 全局错误捕获

```javascript
// main.js
app.config.errorHandler = (err, vm, info) => {
  console.error('Global error:', err)
  // 上报错误日志
}
```

---

## 11. 验收标准

### 11.1 功能验收

- [ ] 用户可以正常登录
- [ ] 设备列表正确显示4种设备
- [ ] 设备状态指示灯正确显示
- [ ] 相机实时图像正确展示
- [ ] AI分析流程完整
- [ ] 手法选择弹窗功能正常
- [ ] 参数设置弹窗功能正常
- [ ] 理疗倒计时功能正常
- [ ] 页面流转正确

### 11.2 性能验收

- [ ] 首屏加载时间 ≤ 3秒
- [ ] 页面切换无明显卡顿
- [ ] 视频流帧率 ≥ 24fps

### 11.3 兼容性验收

- [ ] Chrome 最新版正常
- [ ] Firefox 最新版正常
- [ ] Edge 最新版正常
