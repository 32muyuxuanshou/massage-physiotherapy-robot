import { api, API_BASE_URL, USE_MOCK } from './api'

const mockDevices = [
  {
    id: 'device-001',
    name: '智能理疗仪A1',
    type: 'tuina',
    model: 'A1-Pro',
    manufacturer: '颐本科技',
    status: 'offline'
  },
  {
    id: 'device-002',
    name: '智能理疗仪B2',
    type: 'tuina',
    model: 'B2-Standard',
    manufacturer: '颐本科技',
    status: 'online'
  },
  {
    id: 'device-003',
    name: '全身理疗床C3',
    type: 'massage_bed',
    model: 'C3-Deluxe',
    manufacturer: '颐本科技',
    status: 'online'
  },
  {
    id: 'device-004',
    name: '便携理疗仪D4',
    type: 'portable',
    model: 'D4-Mini',
    manufacturer: '颐本科技',
    status: 'offline'
  }
]

const mockMethods = [
  { id: 'method-001', name: '推拿', type: 'tuina', description: '传统推拿手法，缓解肌肉紧张', default_duration: 30 },
  { id: 'method-002', name: '按摩', type: 'massage', description: '放松按摩，促进血液循环', default_duration: 30 },
  { id: 'method-003', name: '热敷', type: 'heat', description: '热敷理疗，舒缓疼痛', default_duration: 20 },
  { id: 'method-004', name: '针灸', type: 'acupuncture', description: '针灸刺激，调理身体', default_duration: 30 },
  { id: 'method-005', name: '拔罐', type: 'cupping', description: '拔罐理疗，祛湿排毒', default_duration: 15 },
  { id: 'method-006', name: '刮痧', type: 'scraping', description: '刮痧理疗，活血化瘀', default_duration: 20 }
]

export const authApi = {
  async login(phone, password) {
    if (USE_MOCK) {
      if (phone === '13800138000' && password === '123456') {
        return {
          data: {
            access_token: 'mock-access-token-' + Date.now(),
            refresh_token: 'mock-refresh-token-' + Date.now(),
            token_type: 'bearer'
          }
        }
      }
      // 区分手机号和密码错误
      if (phone !== '13800138000') {
        throw { response: { status: 401, data: { detail: '手机号不存在' } } }
      }
      throw { response: { status: 401, data: { detail: '密码错误' } } }
    }
    return api.post('/auth/login', { phone, password })
  },

  async register(phone, password, nickname) {
    if (USE_MOCK) {
      return {
        data: {
          access_token: 'mock-access-token-' + Date.now(),
          refresh_token: 'mock-refresh-token-' + Date.now(),
          token_type: 'bearer'
        }
      }
    }
    return api.post('/auth/register', { phone, password, nickname })
  },

  async logout() {
    if (USE_MOCK) {
      return { data: { message: '登出成功' } }
    }
    return api.post('/auth/logout')
  },

  async refreshToken(refreshToken) {
    if (USE_MOCK) {
      return {
        data: {
          access_token: 'mock-access-token-' + Date.now(),
          refresh_token: 'mock-refresh-token-' + Date.now(),
          token_type: 'bearer'
        }
      }
    }
    return api.post('/auth/refresh-token', { refresh_token: refreshToken })
  }
}

export const userApi = {
  async getProfile() {
    if (USE_MOCK) {
      return {
        data: {
          id: 'user-test-001',
          phone: '13800138000',
          nickname: '测试用户',
          avatar: '',
          gender: null,
          age: null,
          height: null,
          weight: null,
          is_active: true,
          created_at: '2026-01-01T00:00:00Z'
        }
      }
    }
    return api.get('/users/profile')
  },

  async updateProfile(userData) {
    if (USE_MOCK) {
      return { data: { ...userData, id: 'user-test-001' } }
    }
    return api.put('/users/profile', userData)
  },

  async changePassword(oldPassword, newPassword) {
    if (USE_MOCK) {
      if (oldPassword === '123456') {
        return { data: { message: '密码修改成功' } }
      }
      throw new Error('当前密码错误')
    }
    return api.post('/auth/change-password', { old_password: oldPassword, new_password: newPassword })
  }
}

export const deviceApi = {
  async getDevices() {
    if (USE_MOCK) {
      return { data: mockDevices }
    }
    return api.get('/devices')
  },

  async getDevice(deviceId) {
    if (USE_MOCK) {
      const device = mockDevices.find(d => d.id === deviceId)
      return { data: device }
    }
    return api.get(`/devices/${deviceId}`)
  },

  async bindDevice(deviceId) {
    if (USE_MOCK) {
      return { data: { message: '设备绑定成功' } }
    }
    return api.post(`/devices/${deviceId}/bind`, { device_id: deviceId })
  },

  async unbindDevice(deviceId) {
    if (USE_MOCK) {
      return { data: { message: '设备解绑成功' } }
    }
    return api.post(`/devices/${deviceId}/unbind`)
  },

  async connectDevice(deviceId) {
    if (USE_MOCK) {
      return { data: { message: '设备连接成功' } }
    }
    return api.post(`/devices/${deviceId}/connect`)
  },

  async disconnectDevice(deviceId) {
    if (USE_MOCK) {
      return { data: { message: '设备断开成功' } }
    }
    return api.post(`/devices/${deviceId}/disconnect`)
  },

  async getDeviceStatus(deviceId) {
    if (USE_MOCK) {
      return {
        data: {
          device_id: deviceId,
          is_connected: false,
          last_heartbeat: null
        }
      }
    }
    return api.get(`/devices/${deviceId}/status`)
  }
}

export const therapyApi = {
  async getMethods() {
    if (USE_MOCK) {
      return { data: mockMethods }
    }
    return api.get('/therapy/methods')
  },

  async createSession(sessionData) {
    if (USE_MOCK) {
      return {
        data: {
          id: 'session-' + Date.now(),
          user_id: 'user-test-001',
          device_id: sessionData.device_id,
          methods: JSON.stringify(sessionData.methods),
          params: JSON.stringify(sessionData.params),
          status: 'pending',
          duration: 0,
          total_duration: sessionData.methods.reduce((sum, m) => sum + m.duration, 0) * 60,
          created_at: new Date().toISOString()
        }
      }
    }
    return api.post('/therapy/sessions', sessionData)
  },

  async getSessions(limit = 20) {
    if (USE_MOCK) {
      return {
        data: [
          {
            id: 'session-history-1',
            user_id: 'user-test-001',
            device_id: 'device-001',
            device_name: '智能理疗仪A1',
            methods: '[{"type":"tuina","duration":30}]',
            params: '{"height":50,"speed":50,"intensity":3}',
            status: 'completed',
            duration: 1800,
            total_duration: 1800,
            created_at: '2026-04-01T10:00:00Z',
            completed_at: '2026-04-01T10:30:00Z'
          }
        ]
      }
    }
    return api.get(`/therapy/sessions?limit=${limit}`)
  },

  async getSession(sessionId) {
    if (USE_MOCK) {
      return {
        data: {
          id: sessionId,
          user_id: 'user-test-001',
          device_id: 'device-001',
          device_name: '智能理疗仪A1',
          methods: '[{"type":"tuina","duration":30}]',
          params: '{"height":50,"speed":50,"intensity":3}',
          status: 'pending',
          duration: 0,
          total_duration: 1800,
          created_at: new Date().toISOString()
        }
      }
    }
    return api.get(`/therapy/sessions/${sessionId}`)
  },

  async startSession(sessionId) {
    if (USE_MOCK) {
      return { data: { id: sessionId, status: 'running', started_at: new Date().toISOString() } }
    }
    return api.post(`/therapy/sessions/${sessionId}/start`)
  },

  async pauseSession(sessionId) {
    if (USE_MOCK) {
      return { data: { id: sessionId, status: 'paused', paused_at: new Date().toISOString() } }
    }
    return api.post(`/therapy/sessions/${sessionId}/pause`)
  },

  async resumeSession(sessionId) {
    if (USE_MOCK) {
      return { data: { id: sessionId, status: 'running', resumed_at: new Date().toISOString() } }
    }
    return api.post(`/therapy/sessions/${sessionId}/resume`)
  },

  async stopSession(sessionId) {
    if (USE_MOCK) {
      return { data: { id: sessionId, status: 'completed', completed_at: new Date().toISOString() } }
    }
    return api.post(`/therapy/sessions/${sessionId}/stop`)
  },

  async getSessionStatus(sessionId) {
    if (USE_MOCK) {
      return {
        data: {
          session_id: sessionId,
          status: 'running',
          duration: 0,
          total_duration: 1800
        }
      }
    }
    return api.get(`/therapy/sessions/${sessionId}/status`)
  }
}

export const aiApi = {
  async captureImage(sessionId = null) {
    if (USE_MOCK) {
      return {
        data: {
          id: 'capture-' + Date.now(),
          user_id: 'user-test-001',
          session_id: sessionId,
          image_path: '/uploads/mock-image.jpg',
          capture_time: new Date().toISOString()
        }
      }
    }
    return api.post('/ai/capture', { session_id: sessionId })
  },

  async analyzeImage(captureId) {
    if (USE_MOCK) {
      return {
        data: {
          id: 'analysis-' + Date.now(),
          user_id: 'user-test-001',
          capture_id: captureId,
          result: '理疗效果良好，肌肉紧张程度明显改善',
          body_parts: '["腰部", "背部", "颈部"]',
          pressure_level: 5,
          recommendations: '建议继续保持规律理疗，每次30分钟，每周2-3次',
          status: 'completed',
          analyzed_at: new Date().toISOString(),
          created_at: new Date().toISOString()
        }
      }
    }
    return api.post('/ai/analyze', { capture_id: captureId })
  },

  async getAnalysis(analysisId) {
    if (USE_MOCK) {
      return {
        data: {
          id: analysisId,
          user_id: 'user-test-001',
          capture_id: 'capture-1',
          result: '理疗效果良好',
          body_parts: '["腰部"]',
          pressure_level: 5,
          recommendations: '建议继续保持',
          status: 'completed',
          analyzed_at: new Date().toISOString(),
          created_at: new Date().toISOString()
        }
      }
    }
    return api.get(`/ai/analysis/${analysisId}`)
  },

  async getAnalysisHistory(limit = 20) {
    if (USE_MOCK) {
      return {
        data: [
          {
            id: 'analysis-history-1',
            user_id: 'user-test-001',
            result: '理疗效果良好',
            body_parts: '["腰部"]',
            pressure_level: 5,
            status: 'completed',
            created_at: '2026-04-01T10:00:00Z'
          }
        ]
      }
    }
    return api.get(`/ai/history?limit=${limit}`)
  }
}

export { API_BASE_URL, USE_MOCK }
