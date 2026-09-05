<template>
  <header class="app-header">
    <div class="app-header__left">
      <div class="app-header__home" @click="goHome">
        <Home class="app-header__home-icon" />
      </div>
    </div>
    
    <div class="app-header__right">
      <div class="app-header__user" @click="toggleDropdown">
        <div class="app-header__avatar">
          <User />
        </div>
        <span class="app-header__username">{{ userStore.userInfo.nickname }}</span>
        <ChevronDown class="app-header__dropdown-icon" :class="{ 'is-open': showDropdown }" />
      </div>
      
      <Transition name="dropdown">
        <div v-if="showDropdown" class="app-header__dropdown">
          <div class="app-header__dropdown-item" @click="openProfile">
            <User />
            <span>个人中心</span>
          </div>
          <div class="app-header__dropdown-item app-header__dropdown-item--danger" @click="handleLogout">
            <LogOut />
            <span>退出登录</span>
          </div>
        </div>
      </Transition>
    </div>

    <BaseModal v-model:visible="showChangePassword" title="修改密码" width="400px">
      <div class="change-password-form">
        <div class="change-password-form__field">
          <label class="change-password-form__label">当前密码</label>
          <input 
            v-model="currentPassword" 
            type="password" 
            class="change-password-form__input"
            placeholder="请输入当前密码"
          />
        </div>
        
        <div class="change-password-form__field">
          <label class="change-password-form__label">新密码</label>
          <input 
            v-model="newPassword" 
            type="password" 
            class="change-password-form__input"
            placeholder="请输入新密码（6-20位）"
          />
        </div>
        
        <div class="change-password-form__field">
          <label class="change-password-form__label">确认新密码</label>
          <input 
            v-model="confirmPassword" 
            type="password" 
            class="change-password-form__input"
            placeholder="请再次输入新密码"
            @keyup.enter="handleChangePassword"
          />
        </div>
        
        <div v-if="passwordError" class="change-password-form__error">
          {{ passwordError }}
        </div>
      </div>
      <template #footer>
        <BaseButton type="secondary" @click="closeChangePassword">取消</BaseButton>
        <BaseButton type="primary" @click="handleChangePassword">确认修改</BaseButton>
      </template>
    </BaseModal>

    <BaseModal v-model:visible="showProfile" title="个人中心" width="400px">
      <div class="profile-modal">
        <div class="profile-modal__avatar">
          <User :size="48" />
        </div>
        
        <div class="profile-modal__field">
          <label class="profile-modal__label">昵称</label>
          <div v-if="!isEditingName" class="profile-modal__value">
            <span>{{ userStore.userInfo.nickname }}</span>
            <Edit2 class="profile-modal__edit-icon" @click="startEditName" />
          </div>
          <div v-else class="profile-modal__edit">
            <input 
              v-model="editName" 
              type="text" 
              class="profile-modal__input"
              @keyup.enter="saveName"
              @keyup.esc="cancelEditName"
            />
            <div class="profile-modal__edit-actions">
              <BaseButton type="primary" size="small" @click="saveName">保存</BaseButton>
              <BaseButton type="secondary" size="small" @click="cancelEditName">取消</BaseButton>
            </div>
          </div>
        </div>
        
        <div class="profile-modal__field">
          <label class="profile-modal__label">手机号</label>
          <div v-if="!isEditingPhone" class="profile-modal__value">
            <span>{{ formattedPhone }}</span>
            <Edit2 class="profile-modal__edit-icon" @click="startEditPhone" />
          </div>
          <div v-else class="profile-modal__edit">
            <input 
              v-model="editPhone" 
              type="tel" 
              class="profile-modal__input"
              placeholder="请输入手机号"
              @keyup.enter="savePhone"
              @keyup.esc="cancelEditPhone"
            />
            <div class="profile-modal__edit-actions">
              <BaseButton type="primary" size="small" @click="savePhone">保存</BaseButton>
              <BaseButton type="secondary" size="small" @click="cancelEditPhone">取消</BaseButton>
            </div>
          </div>
        </div>
        
        <div class="profile-modal__menu">
          <div class="profile-modal__menu-item" @click="openChangePassword">
            <Lock />
            <span>修改密码</span>
          </div>
        </div>
      </div>
      <template #footer>
        <BaseButton type="secondary" @click="handleLogout">退出登录</BaseButton>
      </template>
    </BaseModal>
  </header>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { Home, User, ChevronDown, LogOut, Lock, Settings, Edit2 } from 'lucide-vue-next'
import BaseModal from '@/components/common/BaseModal.vue'
import BaseButton from '@/components/common/BaseButton.vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const showDropdown = ref(false)
const showProfile = ref(false)
const showChangePassword = ref(false)

const isEditingName = ref(false)
const isEditingPhone = ref(false)
const editName = ref('')
const editPhone = ref('')

const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const passwordError = ref('')

const formattedPhone = computed(() => {
  const phone = userStore.userInfo.phone
  if (phone) {
    return phone.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2')
  }
  return ''
})

function toggleDropdown() {
  showDropdown.value = !showDropdown.value
}

function goHome() {
  if (userStore.isLoggedIn) {
    router.push('/home')
  }
}

function openProfile() {
  showDropdown.value = false
  showProfile.value = true
  isEditingName.value = false
  isEditingPhone.value = false
}

function startEditName() {
  editName.value = userStore.userInfo.nickname || ''
  isEditingName.value = true
}

async function saveName() {
  if (editName.value.trim()) {
    const result = await userStore.updateUserInfo({ nickname: editName.value.trim() })
    if (result.success) {
      isEditingName.value = false
    }
  }
}

function cancelEditName() {
  isEditingName.value = false
  editName.value = ''
}

function startEditPhone() {
  editPhone.value = userStore.userInfo.phone || ''
  isEditingPhone.value = true
}

async function savePhone() {
  const phoneRegex = /^1[3-9]\d{9}$/
  if (phoneRegex.test(editPhone.value)) {
    const result = await userStore.updateUserInfo({ phone: editPhone.value })
    if (result.success) {
      isEditingPhone.value = false
    }
  } else {
    alert('请输入有效的手机号')
  }
}

function cancelEditPhone() {
  isEditingPhone.value = false
  editPhone.value = ''
}

function openChangePassword() {
  showProfile.value = false
  showChangePassword.value = true
  resetPasswordForm()
}

function resetPasswordForm() {
  currentPassword.value = ''
  newPassword.value = ''
  confirmPassword.value = ''
  passwordError.value = ''
}

function closeChangePassword() {
  showChangePassword.value = false
  resetPasswordForm()
}

async function handleChangePassword() {
  passwordError.value = ''
  
  if (!currentPassword.value) {
    passwordError.value = '请输入当前密码'
    return
  }
  
  if (!newPassword.value) {
    passwordError.value = '请输入新密码'
    return
  }
  
  if (newPassword.value.length < 6 || newPassword.value.length > 20) {
    passwordError.value = '新密码长度应为6-20位'
    return
  }
  
  if (newPassword.value !== confirmPassword.value) {
    passwordError.value = '两次输入的新密码不一致'
    return
  }
  
  const result = await userStore.changePassword(currentPassword.value, newPassword.value)
  
  if (result.success) {
    alert('密码修改成功！')
    closeChangePassword()
  } else {
    passwordError.value = result.message
  }
}

function handleLogout() {
  showDropdown.value = false
  showProfile.value = false
  userStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 48px;
  padding: 0 16px;
  background-color: rgba(232, 138, 77, 0.2);
}

.app-header__right {
  flex: 1;
  display: flex;
  justify-content: flex-end;
  position: relative;
}

.app-header__home {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-medium);
  background-color: var(--color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.app-header__home-icon {
  color: var(--color-white);
  width: 16px;
  height: 16px;
}

.app-header__user {
  display: flex;
  align-items: center;
  cursor: pointer;
  padding: 6px 10px;
  border-radius: var(--radius-medium);
  transition: background-color 0.2s;
}

.app-header__user:hover {
  background-color: var(--color-primary-lighter);
}

.app-header__avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background-color: var(--color-primary-lighter);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-primary);
}

.app-header__avatar svg {
  width: 14px;
  height: 14px;
}

.app-header__username {
  margin: 0 6px;
  font-size: var(--font-size-xs);
  color: var(--color-text);
}

.app-header__dropdown-icon {
  width: 14px;
  height: 14px;
  color: var(--color-text-light);
  transition: transform 0.2s;
}

.app-header__dropdown-icon.is-open {
  transform: rotate(180deg);
}

.app-header__dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 6px;
  background-color: var(--color-white);
  border-radius: var(--radius-medium);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  min-width: 140px;
  overflow: hidden;
  z-index: 100;
}

.app-header__dropdown-item {
  display: flex;
  align-items: center;
  padding: 10px 14px;
  cursor: pointer;
  transition: background-color 0.2s;
  font-size: var(--font-size-xs);
}

.app-header__dropdown-item:hover {
  background-color: var(--color-primary-lighter);
}

.app-header__dropdown-item svg {
  width: 16px;
  height: 16px;
  margin-right: 10px;
  color: var(--color-text-light);
}

.app-header__dropdown-item--danger {
  color: var(--color-error);
}

.app-header__dropdown-item--danger svg {
  color: var(--color-error);
}

.profile-modal {
  text-align: center;
}

.profile-modal__avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background-color: var(--color-primary-lighter);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 12px;
  color: var(--color-primary);
}

.profile-modal__field {
  margin-bottom: 16px;
}

.profile-modal__label {
  display: block;
  font-size: var(--font-size-xs);
  color: var(--color-text-light);
  margin-bottom: 6px;
  text-align: left;
}

.profile-modal__value {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  background-color: var(--color-white);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  font-size: var(--font-size-sm);
}

.profile-modal__edit-icon {
  width: 16px;
  height: 16px;
  color: var(--color-text-light);
  cursor: pointer;
  transition: color 0.2s;
}

.profile-modal__edit-icon:hover {
  color: var(--color-primary);
}

.profile-modal__edit {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.profile-modal__input {
  width: 100%;
  padding: 6px 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  font-size: var(--font-size-sm);
  outline: none;
  transition: border-color 0.2s;
}

.profile-modal__input:focus {
  border-color: var(--color-primary);
}

.profile-modal__edit-actions {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
}

.profile-modal__menu {
  text-align: left;
  margin-top: 16px;
}

.profile-modal__menu-item {
  display: flex;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid var(--color-border);
  cursor: pointer;
  transition: color 0.2s;
  font-size: var(--font-size-sm);
}

.profile-modal__menu-item:last-child {
  border-bottom: none;
}

.profile-modal__menu-item:hover {
  color: var(--color-primary);
}

.profile-modal__menu-item svg {
  width: 16px;
  height: 16px;
  margin-right: 10px;
  color: var(--color-text-light);
}

.dropdown-enter-active,
.dropdown-leave-active {
  transition: all 0.2s ease;
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

.change-password-form {
  padding: 16px 0;
}

.change-password-form__field {
  margin-bottom: 16px;
}

.change-password-form__field:last-of-type {
  margin-bottom: 0;
}

.change-password-form__label {
  display: block;
  font-size: var(--font-size-xs);
  color: var(--color-text);
  margin-bottom: 6px;
  text-align: left;
}

.change-password-form__input {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  font-size: var(--font-size-sm);
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
}

.change-password-form__input:focus {
  border-color: var(--color-primary);
}

.change-password-form__input::placeholder {
  color: var(--color-text-light);
}

.change-password-form__error {
  margin-top: 12px;
  padding: 8px;
  background-color: rgba(220, 53, 69, 0.1);
  border: 1px solid var(--color-error);
  border-radius: var(--radius-medium);
  color: var(--color-error);
  font-size: var(--font-size-xs);
  text-align: center;
}
</style>
