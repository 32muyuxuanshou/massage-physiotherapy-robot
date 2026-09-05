import { defineStore } from 'pinia'
import { ref } from 'vue'
import { deviceApi } from '@/services'

export const useDeviceStore = defineStore('device', () => {
  const devices = ref([])
  const selectedDeviceId = ref(null)
  const isConnecting = ref(false)
  const loading = ref(false)

  async function fetchDevices() {
    loading.value = true
    try {
      const response = await deviceApi.getDevices()
      devices.value = response.data.map(d => ({
        id: d.id,
        name: d.name,
        icon: d.name,
        model: d.model,
        manufacturer: d.manufacturer,
        status: {
          camera: d.status === 'online' ? 'online' : 'offline',
          arm: d.status === 'online' ? 'online' : 'offline',
          head: d.status === 'online' ? 'online' : 'offline'
        },
        connected: false,
        type: d.type
      }))
    } catch (error) {
      console.error('获取设备列表失败:', error)
    } finally {
      loading.value = false
    }
  }

  function selectDevice(deviceId) {
    selectedDeviceId.value = deviceId
  }

  async function connectDevice(deviceId) {
    isConnecting.value = true
    try {
      await deviceApi.connectDevice(deviceId)
      const device = devices.value.find(d => d.id === deviceId)
      if (device) {
        device.connected = true
      }
    } catch (error) {
      console.error('连接设备失败:', error)
    } finally {
      isConnecting.value = false
    }
  }

  async function disconnectDevice(deviceId) {
    try {
      await deviceApi.disconnectDevice(deviceId)
      const device = devices.value.find(d => d.id === deviceId)
      if (device) {
        device.connected = false
      }
      if (selectedDeviceId.value === deviceId) {
        selectedDeviceId.value = null
      }
    } catch (error) {
      console.error('断开设备失败:', error)
    }
  }

  async function bindDevice(deviceId) {
    try {
      await deviceApi.bindDevice(deviceId)
      return { success: true, message: '绑定成功' }
    } catch (error) {
      console.error('绑定设备失败:', error)
      return { success: false, message: '绑定失败' }
    }
  }

  async function unbindDevice(deviceId) {
    try {
      await deviceApi.unbindDevice(deviceId)
      return { success: true, message: '解绑成功' }
    } catch (error) {
      console.error('解绑设备失败:', error)
      return { success: false, message: '解绑失败' }
    }
  }

  function getSelectedDevice() {
    return devices.value.find(d => d.id === selectedDeviceId.value)
  }

  function setMockDevices() {
    devices.value = [
      {
        id: 'device-1',
        name: '按摩机器人',
        icon: '按摩机器人',
        model: '瑞尔曼',
        status: { camera: 'online', arm: 'online', head: 'online' },
        connected: false
      },
      {
        id: 'device-2',
        name: '艾灸机器人',
        icon: '艾灸机器人',
        model: '瑞尔曼',
        status: { camera: 'online', arm: 'online', head: 'online' },
        connected: false
      },
      {
        id: 'device-3',
        name: '光疗嫩肤机器人',
        icon: '光疗嫩肤机器人',
        model: '瑞尔曼',
        status: { camera: 'online', arm: 'online', head: 'offline' },
        connected: false
      },
      {
        id: 'device-4',
        name: '超声减脂机器人',
        icon: '超声减脂机器人',
        model: '瑞尔曼',
        status: { camera: 'online', arm: 'online', head: 'online' },
        connected: false
      }
    ]
  }

  return {
    devices,
    selectedDeviceId,
    isConnecting,
    loading,
    fetchDevices,
    selectDevice,
    connectDevice,
    disconnectDevice,
    bindDevice,
    unbindDevice,
    getSelectedDevice,
    setMockDevices
  }
})
