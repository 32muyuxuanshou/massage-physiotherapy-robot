<template>
  <!-- 登录页面主容器 -->
  <div class="login-page">
    <!-- 左侧品牌区域 - 展示品牌形象和功能特点 -->
    <div class="login-page__brand">
      <h1 class="login-page__title">颐本智能理疗系统</h1>
      <div class="login-page__titile__divider"></div>
      <p class="login-page__subtitle">专业理疗解决方案 &nbsp;&nbsp; 智能化健康体验</p>
      <!-- 功能特点展示 -->
      <div class="login-page__features">
        <div class="login-page__feature">
          <div class="feature-icon">
            <Monitor />
          </div>
          <span>智能分析</span>
        </div>
        <div class="login-page__feature">
          <div class="feature-icon">
            <Heart />
          </div>
          <span>个性化理疗</span>
        </div>
        <div class="login-page__feature">
          <div class="feature-icon">
            <BarChart3 />
          </div>
          <span>数据追踪</span>
        </div>
      </div>
    </div>

    <!-- 右侧登录表单区域 -->
    <div class="login-page__form-container">
      <!-- 登录卡片 -->
      <div class="login-page__card">
        <h2 class="login-page__card-title">用户登录</h2>

        <div class="login-page__input-group" @keyup.enter="handleLogin">
            <BaseInput v-model="phone" type="tel" placeholder="请输入手机号" :error="phoneError" prefix-icon
              @blur="validatePhone">
              <template #prefix>
                <Smartphone />
              </template>
            </BaseInput>
          </div>

          <!-- 密码输入框 -->
          <div class="login-page__input-group">
            <BaseInput v-model="password" :type="showPassword ? 'text' : 'password'" placeholder="请输入密码"
              :error="passwordError" prefix-icon suffix-icon>
              <template #prefix>
                <Lock />
              </template>
              <template #suffix>
                <!-- 密码可见切换图标 -->
                <component :is="showPassword ? EyeOff : Eye" class="login-page__eye-icon" @click="togglePassword" />
                <!-- 忘记密码链接 -->
                <span class="login-page__forgot">忘记密码</span>
              </template>
            </BaseInput>
          </div>

          <!-- 登录错误提示 -->
          <div v-if="loginError" class="login-page__error">
            {{ loginError }}
          </div>

          <!-- 登录按钮 -->
          <BaseButton type="primary" size="large" class="login-page__submit" :disabled="!canSubmit" :loading="loading" @click="handleLogin">
            登 录
          </BaseButton>


        <!-- 其他登录方式链接 -->
        <div class="login-page__links">
          <a href="#" class="login-page__link">手机验证码登录</a>
          <a href="#" class="login-page__link">新用户注册</a>
        </div>

        <!-- 分割线 -->
        <div class="login-page__divider"></div>

        <!-- 其他登录方式 -->
        <div class="login-page__other">
          <span>其他方式登录</span>
        </div>

        <!-- 用户协议提示 -->
        <div class="login-page__agreement">
          登录即表示同意平台《隐私政策》和《用户协议》
        </div>
      </div>

      <!-- 版权信息 -->
      <div class="login-page__copyright">
        @2026 颐本智能理疗系统保留所有权利
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import { useRouter } from 'vue-router'
// 导入Lucide图标组件
import { Smartphone, Lock, Monitor, Heart, BarChart3, Eye, EyeOff } from 'lucide-vue-next'
// 导入通用组件
import BaseInput from '@/components/common/BaseInput.vue'
import BaseButton from '@/components/common/BaseButton.vue'
// 导入用户状态管理
import { useUserStore } from '@/stores/user'

// 路由实例
const router = useRouter()
// 用户状态管理
const userStore = useUserStore()

// 表单数据
const phone = ref('')
const password = ref('')

// 表单验证错误信息
const phoneError = ref('')
const passwordError = ref('')
const loginError = ref('')

// 加载状态
const loading = ref(false)
// 密码可见状态
const showPassword = ref(false)

// 切换密码可见性
function togglePassword() {
  showPassword.value = !showPassword.value
}

// 计算是否可提交（手机号11位，密码至少6位）
const canSubmit = computed(() => {
  return phone.value.length === 11 && password.value.length >= 6
})

// 验证手机号格式
function validatePhone() {
  if (phone.value && phone.value.length !== 11) {
    phoneError.value = '手机号格式不正确'
  } else {
    phoneError.value = ''
  }
}

// 处理登录提交
async function handleLogin() {
  loginError.value = ''
  phoneError.value = ''
  passwordError.value = ''

  // 表单验证
  if (!phone.value) {
    phoneError.value = '请输入手机号'
    return
  }

  if (phone.value.length !== 11) {
    phoneError.value = '手机号格式不正确'
    return
  }

  if (!password.value) {
    passwordError.value = '请输入密码'
    return
  }

  if (password.value.length < 6) {
    passwordError.value = '密码至少6位'
    return
  }

  // 设置加载状态
  loading.value = true

  try {
    // 调用用户登录
    const result = await userStore.login(phone.value, password.value)

    // 处理登录结果
    if (result.success) {
      router.push('/home')
    } else {
      // 根据错误消息显示不同的提示
      const message = result.message || ''
      if (message.includes('手机号') || message.includes('不存在')) {
        phoneError.value = message
      } else if (message.includes('密码') || message.includes('错误')) {
        passwordError.value = '密码不正确，请重新输入'
        loginError.value = ''
      } else {
        loginError.value = message || '登录失败，请稍后重试'
      }
      // 使用 nextTick 确保 UI 更新后再聚焦
      await nextTick()
    }
  } catch (error) {
    console.error('登录异常:', error)
    loginError.value = '登录失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* 页面主容器 */
.login-page {
  display: flex;
  min-height: 100vh;
  min-width: 1024px;
  background-image: url('@/assets/images/background.png');
  background-size: cover;
  background-position: center;
  padding: 0 5%;
}

/* 左侧品牌区域 */
.login-page__brand {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: left;
  justify-content: center;
  padding: 20px 0;
}

/* 右侧表单容器 */
.login-page__form-container {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
}

/* 登录卡片 */
.login-page__card {
  width: 100%;
  max-width: 420px;
  border: 1px solid rgba(232, 138, 77, 1);
  border-radius: 24px;
  background-color: #FFFBEC;
  padding: 40px 50px;
}

/* 页面标题 */
.login-page__title {
  font-size: 32px;
  font-weight: 700;
  color: #B63F1A;
}

.login-page__titile__divider {
  height: 3px;
  width: 48px;
  background-color: #B63F1A;
  margin-top: 10px;
  margin-bottom: 10px;
}

/* 页面副标题 */
.login-page__subtitle {
  color: #E88A4D;
  margin-bottom: 40px;
  font-size: 18px;
}

/* 功能特点列表 */
.login-page__features {
  display: flex;
  gap: 32px;
}

/* 功能特点项 */
.login-page__feature {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.login-page__feature svg {
  width: 24px;
  height: 24px;
  color: #E88A4D;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 功能图标圆形背景 */
.login-page__feature .feature-icon {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background-color: #E88A4D;
  display: flex;
  align-items: center;
  justify-content: center;
}

.login-page__feature .feature-icon svg {
  color: white;
  width: 28px;
  height: 28px;
}

.login-page__feature span {
  font-size: 14px;
  color: #E88A4D;
}

/* 卡片标题 */
.login-page__card-title {
  font-size: var(--font-size-lg);
  font-weight: 600;
  text-align: center;
  margin-bottom: 24px;
  color: #B63F1A;
}

/* 输入框组 */
.login-page__input-group {
  margin-bottom: 12px;
}

/* 输入框样式覆盖 */
.login-page__input-group :deep(.base-input) {
  width: 100%;
  height: 48px;
  border-radius: 24px;
  background: rgba(232, 138, 77, 0.2);
  color: rgba(232, 138, 77, 0.6);
  font-size: var(--font-size-sm);
}

/* 输入框图标样式 */
.login-page__input-group :deep(.base-input__icon svg) {
  color: rgba(232, 138, 77, 0.6) !important;
  width: 20px !important;
  height: 20px !important;
}

/* 输入框文本样式 */
.login-page__input-group :deep(.base-input__field) {
  color: rgba(232, 138, 77, 0.6) !important;
  font-size: var(--font-size-sm);
}

/* 输入框占位符样式 */
.login-page__input-group :deep(.base-input__field::placeholder) {
  color: rgba(232, 138, 77, 0.5) !important;
}

/* 错误提示 */
.login-page__error {
  color: var(--color-error);
  font-size: var(--font-size-xs);
  margin-bottom: 12px;
  text-align: center;
}

/* 登录按钮 */
.login-page__submit {
  width: 100%;
  margin-top: 8px;
  height: 48px;
  opacity: 1;
  border-radius: 24px;
  background: rgba(232, 138, 77, 1) !important;
  color: white !important;
  border: none !important;
  font-size: var(--font-size-base);
}

/* 链接列表 */
.login-page__links {
  display: flex;
  justify-content: space-between;
  margin-top: 16px;
  font-size: var(--font-size-xs);
}

/* 链接样式 */
.login-page__link {
  color: #B63F1A;
}

/* 其他登录方式区域 */
.login-page__other {
  text-align: center;
  margin-top: 16px;
}

.login-page__other span {
  color: #B63F1A;
  font-size: var(--font-size-xs);
}

/* 分割线 */
.login-page__divider {
  height: 1px;
  background-color: #E88A4D;
  margin-top: 12px;
  margin-bottom: 12px;
}

/* 密码可见图标 */
.login-page__eye-icon {
  cursor: pointer;
  color: rgba(232, 138, 77, 0.6) !important;
  width: 24px;
  height: 24px;
  margin-left: 4px;
}

/* 忘记密码链接 */
.login-page__forgot {
  color: rgba(232, 138, 77, 0.6);
  font-size: var(--font-size-xs);
  margin-left: 8px;
  cursor: pointer;
  text-decoration: none;
}

.login-page__forgot:hover {
  text-decoration: underline;
}

/* 用户协议提示 */
.login-page__agreement {
  margin-top: 12px;
  text-align: center;
  font-size: 10px;
  color: #B63F1A;
}

/* 版权信息 */
.login-page__copyright {
  position: absolute;
  bottom: 16px;
  font-size: 10px;
  color: var(--color-text-light);
  right: 3%;
}
</style>
