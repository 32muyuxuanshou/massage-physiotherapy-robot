# 全局组件规格

**版本**: V0.1
**日期**: 2026-04-10
**状态**: 一期核心功能完成

本文档定义颐本智能理疗系统中全局复用组件的规格。

---

## 顶部导航栏 (AppHeader)

### 左侧区域
- 首页图标: 橙色圆形背景 + 白色房屋图标
- 点击返回首页

### 中间区域
- 三步骤进度条:
  1. 设备选择
  2. AI分析
  3. 理疗管理
- 已完成: 实心橙色圆点
- 当前: 橙色高亮圆点
- 未开始: 灰色圆点
- 连接线: 虚线 + 箭头

### 右侧区域
- 用户头像: 圆形卡通头像
- 用户名: "小雪"
- 下拉箭头: 展开下拉菜单
- 下拉菜单内容:
  - 个人中心（点击打开弹窗）
  - 退出登录（返回登录页）

---

## 用户下拉菜单 (UserDropdown)

### 功能
- 展开/收起菜单
- 点击"个人中心"打开弹窗
- 点击"退出登录"执行退出

### 菜单项

| 菜单项 | 说明 |
|--------|------|
| 个人中心 | 打开个人中心弹窗 |
| 退出登录 | 直接退出，返回登录页 |

---

## 按钮组件 (BaseButton)

### 类型

| 类型 | 样式 | 用途 |
|------|------|------|
| primary | 橙色实心背景，白色文字 | 登录、下一步、确认、开始 |
| secondary | 浅橙色/浅灰色半透明背景 | 重新采集、重新分析、上一步 |
| ghost | 无背景，橙色边框 | 次要操作 |

### 规格
- 圆角: 胶囊形 (border-radius: 999px)
- 高度: 44px - 56px
- 内边距: 16px 32px

---

## 输入框组件 (BaseInput)

### 规格
- 样式: 胶囊型（全圆角）
- 背景: 浅肤色
- 图标: 左侧带图标标识
- 密码框: 右侧显示/隐藏切换

---

## 卡片组件 (BaseCard)

### 规格
- 背景: 白色
- 圆角: 24px
- 阴影: 0 4px 12px rgba(0,0,0,0.08)

---

## 弹窗组件 (BaseModal)

### 规格
- 背景: 白色
- 圆角: 24px
- 遮罩: 半透明黑色
- 关闭按钮: 右上角×

---

## 滑块组件 (BaseSlider)

### 类型

| 类型 | 范围 | 用途 |
|------|------|------|
| 时长 | 0-60分钟 | 手法时长设置 |
| 高度 | 0-100% | 理疗参数设置 |
| 速度 | 0-100% | 理疗参数设置 |
| 力度 | 0-5档 | 理疗参数设置 |

---

## 状态指示灯 (StatusIndicator)

### 状态

| 状态 | 颜色 | 含义 |
|------|------|------|
| online | 绿色 | 正常 |
| offline | 红色 | 异常 |

---

## 步骤进度条 (StepProgress)

### 步骤

| 步骤 | 名称 | 状态 |
|------|------|------|
| 1 | 设备选择 | completed/current/pending |
| 2 | AI分析 | completed/current/pending |
| 3 | 理疗管理 | completed/current/pending |

---

## 组件Props设计

### BaseButton
```typescript
interface Props {
  type?: 'primary' | 'secondary' | 'ghost';
  size?: 'small' | 'medium' | 'large';
  disabled?: boolean;
  loading?: boolean;
  icon?: string;
}
```

### BaseInput
```typescript
interface Props {
  modelValue: string;
  type?: 'text' | 'password' | 'tel';
  placeholder?: string;
  disabled?: boolean;
  prefixIcon?: string;
  suffixIcon?: string;
  error?: string;
}
```

### BaseModal
```typescript
interface Props {
  visible: boolean;
  title?: string;
  width?: string | number;
  closable?: boolean;
  maskClosable?: boolean;
}
```

### StepProgress
```typescript
interface StepItem {
  title: string;
  status: 'completed' | 'current' | 'pending';
}

interface Props {
  steps: StepItem[];
  current: number;
}
```
