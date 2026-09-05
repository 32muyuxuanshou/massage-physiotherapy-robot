<template>
  <div class="home-page">
    <AppHeader />
    
    <div class="home-page__header">
      <StepProgress :steps="stepList" />
    </div>
    
    <main class="home-page__content">
      <div class="home-page__device-list">
        <div 
          v-for="device in deviceStore.devices" 
          :key="device.id"
          class="device-card"
          :class="{ 'is-selected': device.id === deviceStore.selectedDeviceId }"
          @click="selectDevice(device.id)"
        >
          <div class="device-card__left">
            <div class="device-card__icon">
              <img :src="getDeviceIcon(device.icon)" class="device-icon" />
            </div>
            <div class="device-card__info">
              <h3 class="device-card__name">{{ device.name }}</h3>
              <p class="device-card__model">设备型号：{{ device.model }}</p>
            </div>
          </div>
          
          <div class="device-card__center">
            <div class="device-card__status">
              <span 
                class="device-card__status-dot"
                :class="device.status.camera === 'online' ? 'is-online' : 'is-offline'"
              />
              <span class="device-card__status-label">相机</span>
            </div>
            <div class="device-card__status">
              <span 
                class="device-card__status-dot"
                :class="device.status.arm === 'online' ? 'is-online' : 'is-offline'"
              />
              <span class="device-card__status-label">机械臂</span>
            </div>
            <div class="device-card__status">
              <span 
                class="device-card__status-dot"
                :class="device.status.head === 'online' ? 'is-online' : 'is-offline'"
              />
              <span class="device-card__status-label">按摩头</span>
            </div>
          </div>
          
          <div class="device-card__right">
            <button 
              class="device-card__connect-btn"
              :class="{ 'is-connected': device.connected }"
              @click.stop="toggleConnect(device)"
              :disabled="deviceStore.isConnecting"
            >
              <component :is="device.connected ? Wifi : WifiOff" class="connect-btn-icon" />
              <span class="connect-btn-text">{{ device.connected ? '已连接' : '已断开' }}</span>
            </button>
          </div>
        </div>
      </div>
    </main>
    
    <footer class="home-page__footer">
      <BaseButton 
        type="primary" 
        size="large" 
        :disabled="!canGoNext"
        @click="goNext"
      >
        下一步
      </BaseButton>
    </footer>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Wifi, WifiOff } from 'lucide-vue-next'
import AppHeader from '@/components/layout/AppHeader.vue'
import StepProgress from '@/components/layout/StepProgress.vue'
import BaseButton from '@/components/common/BaseButton.vue'
import { useDeviceStore } from '@/stores/device'

import AnMoJiQiRen from '@/assets/icons/按摩机器人.svg'
import AiJiuJiQiRen from '@/assets/icons/艾灸机器人.svg'
import GuangLiaoNenFuJiQiRen from '@/assets/icons/光疗嫩肤机器人.svg'
import ChaoShengJianZhiJiQiRen from '@/assets/icons/超声减脂机器人.svg'

const router = useRouter()
const deviceStore = useDeviceStore()

onMounted(async () => {
  await deviceStore.fetchDevices()
})

const deviceIcons = {
  '按摩机器人': AnMoJiQiRen,
  '艾灸机器人': AiJiuJiQiRen,
  '光疗嫩肤机器人': GuangLiaoNenFuJiQiRen,
  '超声减脂机器人': ChaoShengJianZhiJiQiRen
}

function getDeviceIcon(iconName) {
  return deviceIcons[iconName] || AnMoJiQiRen
}

const stepList = computed(() => [
  { title: '设备选择', status: 'current' },
  { title: 'AI分析', status: 'pending' },
  { title: '理疗管理', status: 'pending' }
])

const canGoNext = computed(() => {
  const selected = deviceStore.getSelectedDevice()
  return selected && selected.connected
})

function selectDevice(deviceId) {
  deviceStore.selectDevice(deviceId)
}

async function toggleConnect(device) {
  if (device.connected) {
    await deviceStore.disconnectDevice(device.id)
  } else {
    await deviceStore.connectDevice(device.id)
  }
}

function goNext() {
  router.push('/ai-analysis')
}
</script>

<style scoped>
.home-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  min-width: 1024px;
  background-image: url('@/assets/images/background.png');
  background-size: cover;
  background-position: center;
  overflow-x: hidden;
  box-sizing: border-box;
}

.home-page__header {
  padding: 16px 5%;
  display: flex;
  justify-content: flex-start;
}

.home-page__content {
  flex: 1;
  padding: 20px 5%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.home-page__device-list {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.device-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 4%;
  border-radius: var(--radius-medium);
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid rgba(232, 137, 76, 0.2);
  box-shadow: 0px 2px 1px  rgba(232, 138, 77, 0.3);
  color: rgba(183, 64, 24, 1);
}

.device-card.is-selected {
  background-color: rgba(232, 137, 76, 0.2);
}

.device-card__left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.device-card__icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.device-icon {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.device-card__name {
  font-size: var(--font-size-base);
  font-weight: 600;
  margin-bottom: 2px;
}

.device-card__model {
  font-size: var(--font-size-xs);
  color: var(--color-text-light);
}

.device-card__center {
  display: flex;
  gap: 16px;
}

.device-card__status {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  min-width: 80px;
}

.device-card__status-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-light);
}

.device-card__status-dot {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 1px solid var(--color-text-light);
  position: relative;
}

.device-card__status-dot::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.device-card__status-dot.is-online::after {
  background-color: var(--color-success);
}

.device-card__status-dot.is-offline::after {
  background-color: var(--color-error);
}

.device-card__right {
  display: flex;
  align-items: center;
}

.device-card__connect-btn {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 1);
  background: linear-gradient(180deg, rgba(255, 255, 255, 1) 0%, rgba(219, 220, 220, 1) 100%);
  color: rgba(62, 58, 57, 1);
  font-size: var(--font-size-xs);
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  opacity: 1;
}

.device-card__connect-btn.is-connected {
  background: rgba(232, 137, 76, 0.2);
  color: rgba(232, 137, 76, 1);
  border: none;
}

.device-card__connect-btn .connect-btn-icon {
  width: 24px;
  height: 24px;
}

.device-card__connect-btn .connect-btn-text {
  font-size: 12px;
  font-weight: 500;
}

.device-card__connect-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.device-card__connect-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.home-page__footer {
  display: flex;
  justify-content: flex-end;
  padding: 16px 5%;
}

.home-page__footer :deep(.base-button) {
  width: 180px;
  height: 48px;
  font-size: var(--font-size-base);
}
</style>
