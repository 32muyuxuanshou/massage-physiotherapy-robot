import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { therapyApi, aiApi } from '@/services'

export const useTherapyStore = defineStore('therapy', () => {
  const aiAnalysis = ref({
    modelData: null,
    analyzed: false,
    regions: []
  })

  const methods = ref([])
  const availableMethods = ref([])
  const params = ref({
    height: 50,
    speed: 50,
    intensity: 3
  })

  const status = ref('idle')
  const remainingTime = ref(0)
  const startTime = ref(null)
  const timerInterval = ref(null)
  const totalElapsed = ref(0)
  const currentRoundElapsed = ref(0)

  const currentSessionId = ref(null)
  const sessionHistory = ref([])

  const aiAnalysisPage = ref({
    hasCaptured: false,
    hasAnalyzed: false,
    hasMethodSet: false
  })

  const loading = ref(false)

  const totalDuration = computed(() => {
    return methods.value.reduce((sum, m) => sum + m.duration, 0) * 60
  })

  async function fetchMethods() {
    loading.value = true
    try {
      const response = await therapyApi.getMethods()
      availableMethods.value = response.data.map(m => ({
        id: m.id,
        type: m.type,
        name: m.name,
        description: m.description,
        defaultDuration: m.default_duration
      }))
    } catch (error) {
      console.error('获取理疗方法失败:', error)
    } finally {
      loading.value = false
    }
  }

  async function fetchSessionHistory() {
    try {
      const response = await therapyApi.getSessions()
      sessionHistory.value = response.data
    } catch (error) {
      console.error('获取理疗历史失败:', error)
    }
  }

  async function createSession(deviceId, selectedMethods, paramsData) {
    loading.value = true
    try {
      const sessionData = {
        device_id: deviceId,
        methods: selectedMethods.map(m => ({ type: m.type, duration: m.duration })),
        params: paramsData || params.value
      }
      const response = await therapyApi.createSession(sessionData)
      currentSessionId.value = response.data.id
      return { success: true, sessionId: response.data.id }
    } catch (error) {
      console.error('创建理疗会话失败:', error)
      return { success: false, message: '创建失败' }
    } finally {
      loading.value = false
    }
  }

  async function startTherapy() {
    console.log('startTherapy', currentSessionId.value)
    if (!currentSessionId.value) return
    
    try {
      const response = await therapyApi.startSession(currentSessionId.value)
      status.value = 'running'
      remainingTime.value = totalDuration.value
      currentRoundElapsed.value = 0
      startTime.value = Date.now()
      
      timerInterval.value = setInterval(() => {
        if (remainingTime.value > 0) {
          remainingTime.value--
          currentRoundElapsed.value++
        } else {
          stopTherapy()
        }
      }, 1000)
    } catch (error) {
      console.error('开始理疗失败:', error)
    }
  }

  async function pauseTherapy() {
    if (!currentSessionId.value) return
    
    try {
      await therapyApi.pauseSession(currentSessionId.value)
      status.value = 'paused'
      if (timerInterval.value) {
        clearInterval(timerInterval.value)
      }
    } catch (error) {
      console.error('暂停理疗失败:', error)
    }
  }

  async function resumeTherapy() {
    if (!currentSessionId.value) return
    
    try {
      await therapyApi.resumeSession(currentSessionId.value)
      status.value = 'running'
      timerInterval.value = setInterval(() => {
        if (remainingTime.value > 0) {
          remainingTime.value--
          currentRoundElapsed.value++
        } else {
          stopTherapy()
        }
      }, 1000)
    } catch (error) {
      console.error('继续理疗失败:', error)
    }
  }

  async function stopTherapy() {
    if (!currentSessionId.value) return
    
    try {
      await therapyApi.stopSession(currentSessionId.value)
      status.value = 'completed'
      if (timerInterval.value) {
        clearInterval(timerInterval.value)
      }
    } catch (error) {
      console.error('停止理疗失败:', error)
    }
  }

  function finishTherapy() {
    if (timerInterval.value) {
      clearInterval(timerInterval.value)
    }
    totalElapsed.value += currentRoundElapsed.value
    currentRoundElapsed.value = 0
    status.value = 'idle'
    remainingTime.value = 0
    startTime.value = null
    currentSessionId.value = null
  }

  function resetTherapy() {
    status.value = 'idle'
    remainingTime.value = 0
    startTime.value = null
    totalElapsed.value = 0
    currentRoundElapsed.value = 0
    currentSessionId.value = null
    if (timerInterval.value) {
      clearInterval(timerInterval.value)
    }
  }

  function setAiAnalysis(data) {
    aiAnalysis.value = data
  }

  function addMethod(method) {
    const existing = methods.value.find(m => m.type === method.type)
    if (!existing) {
      methods.value.push(method)
    } else {
      existing.duration = method.duration
    }
  }

  function removeMethod(type) {
    const index = methods.value.findIndex(m => m.type === type)
    if (index > -1) {
      methods.value.splice(index, 1)
    }
  }

  function updateParams(newParams) {
    params.value = { ...params.value, ...newParams }
  }

  function setAiAnalysisPage(data) {
    aiAnalysisPage.value = { ...aiAnalysisPage.value, ...data }
  }

  function updateMethodsWithAccumulation() {
    remainingTime.value = totalDuration.value
    currentRoundElapsed.value = 0
  }

  async function captureImage(sessionId = null) {
    try {
      const response = await aiApi.captureImage(sessionId)
      return { success: true, data: response.data }
    } catch (error) {
      console.error('图像采集失败:', error)
      return { success: false, message: '图像采集失败' }
    }
  }

  async function analyzeImage(captureId) {
    try {
      const response = await aiApi.analyzeImage(captureId)
      aiAnalysis.value = {
        modelData: response.data,
        analyzed: true,
        regions: JSON.parse(response.data.body_parts || '[]')
      }
      return { success: true, data: response.data }
    } catch (error) {
      console.error('AI分析失败:', error)
      return { success: false, message: 'AI分析失败' }
    }
  }

  function setMockData() {
    availableMethods.value = [
      { type: 'tuina', name: '推拿手法', defaultDuration: 30 },
      { type: 'massage', name: '按摩手法', defaultDuration: 30 },
      { type: 'heat', name: '热敷', defaultDuration: 20 }
    ]
    methods.value = [
      { type: 'tuina', name: '推拿手法', duration: 30 }
    ]
  }

  return {
    aiAnalysis,
    methods,
    availableMethods,
    params,
    status,
    remainingTime,
    startTime,
    totalDuration,
    totalElapsed,
    currentRoundElapsed,
    aiAnalysisPage,
    currentSessionId,
    sessionHistory,
    loading,
    fetchMethods,
    fetchSessionHistory,
    createSession,
    startTherapy,
    pauseTherapy,
    resumeTherapy,
    stopTherapy,
    finishTherapy,
    resetTherapy,
    setAiAnalysis,
    addMethod,
    removeMethod,
    updateParams,
    setAiAnalysisPage,
    updateMethodsWithAccumulation,
    captureImage,
    analyzeImage,
    setMockData
  }
})
