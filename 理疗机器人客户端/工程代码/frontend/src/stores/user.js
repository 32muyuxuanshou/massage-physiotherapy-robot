import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, userApi } from '@/services'

export const useUserStore = defineStore('user', () => {
  const userInfo = ref({
    id: '',
    phone: '',
    nickname: '',
    avatar: '',
    gender: null,
    age: null,
    height: null,
    weight: null
  })
  
  const isLoggedIn = ref(false)
  const token = ref('')
  const loading = ref(false)

  async function login(phone, password) {
    loading.value = true
    try {
      const response = await authApi.login(phone, password)
      const tokenData = response.data
      
      token.value = tokenData.access_token
      isLoggedIn.value = true
      
      localStorage.setItem('token', token.value)
      localStorage.setItem('refresh_token', tokenData.refresh_token)
      
      await fetchUserProfile()
      
      return { success: true }
    } catch (error) {
      console.error('登录失败:', error)
      return { 
        success: false, 
        message: error.response?.data?.detail || error.message || '登录失败' 
      }
    } finally {
      loading.value = false
    }
  }

  async function fetchUserProfile() {
    try {
      const response = await userApi.getProfile()
      const userData = response.data
      userInfo.value = {
        id: userData.id,
        phone: userData.phone,
        nickname: userData.nickname || '用户',
        avatar: userData.avatar || '',
        gender: userData.gender,
        age: userData.age,
        height: userData.height,
        weight: userData.weight
      }
    } catch (error) {
      console.error('获取用户信息失败:', error)
    }
  }

  function logout() {
    authApi.logout().catch(console.error)
    isLoggedIn.value = false
    token.value = ''
    userInfo.value = {
      id: '',
      phone: '',
      nickname: '',
      avatar: '',
      gender: null,
      age: null,
      height: null,
      weight: null
    }
    localStorage.removeItem('token')
    localStorage.removeItem('refresh_token')
  }

  function checkLogin() {
    const savedToken = localStorage.getItem('token')
    if (savedToken) {
      token.value = savedToken
      isLoggedIn.value = true
      fetchUserProfile()
    }
  }

  async function updateUserInfo(info) {
    try {
      const response = await userApi.updateProfile(info)
      const updatedData = response.data
      userInfo.value = {
        ...userInfo.value,
        ...updatedData
      }
      return { success: true, message: '更新成功' }
    } catch (error) {
      console.error('更新用户信息失败:', error)
      return { success: false, message: '更新失败' }
    }
  }

  async function changePassword(oldPassword, newPassword) {
    try {
      const response = await userApi.changePassword(oldPassword, newPassword)
      return { success: true, message: response.data.message || '密码修改成功' }
    } catch (error) {
      console.error('修改密码失败:', error)
      return { success: false, message: error.response?.data?.detail || '修改密码失败' }
    }
  }

  return {
    userInfo,
    isLoggedIn,
    token,
    loading,
    login,
    logout,
    checkLogin,
    fetchUserProfile,
    updateUserInfo,
    changePassword
  }
})
