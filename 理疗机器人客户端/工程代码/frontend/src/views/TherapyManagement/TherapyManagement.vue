<template>
  <div class="therapy-page">
    <AppHeader />
    
    <div class="therapy-page__header">
      <StepProgress :steps="stepList" />
      <BaseButton type="secondary" class="back-button" @click="goBack">
        上一步
      </BaseButton>
    </div>
    
    <main class="therapy-page__content">
      <div class="therapy-page__camera">
        <div class="therapy-page__camera-view">
          <Camera />
          <div class="therapy-page__timer" v-if="therapyStore.status !== 'idle'">
            <span class="therapy-page__timer-label">剩余时间：</span>
            <span class="therapy-page__timer-value">{{ formattedTime }}</span>
          </div>
        </div>
      </div>
    </main>
    
    <footer class="therapy-page__footer">
      <div class="therapy-page__info">
        <h3 class="therapy-page__device-name">{{ deviceName }}</h3>
        <p class="therapy-page__methods">{{ methodNames }}</p>
      </div>
      
      <div class="therapy-page__controls">
        <BaseButton type="secondary" class="action-button" @click="openMethodSelector" :disabled="therapyStore.status === 'running'">
          <div class="action-button__content">
            <RotateCcw class="btn-icon" />
            <div>
              重新选择
            </div>
          </div>
        </BaseButton>

        <BaseButton type="secondary" class="action-button" @click="openParamsSettings" :disabled="therapyStore.status === 'running'">
          <div class="action-button__content">
            <Settings class="btn-icon" />
            <div>
              参数设置
            </div>
          </div>
        </BaseButton>

        <BaseButton
          v-if="therapyStore.status === 'idle' || therapyStore.status === 'completed'"
          type="primary"
          class="action-button"
          @click="startTherapy"
        >
          <div class="action-button__content">
            <Play class="btn-icon" />
            <div>
              开始
            </div>
          </div>
        </BaseButton>

        <BaseButton
          v-else-if="therapyStore.status === 'running'"
          type="secondary"
          class="action-button"
          @click="pauseTherapy"
        >
          <div class="action-button__content">
            <Pause class="btn-icon" />
            <div>
              暂停
            </div>
          </div>
        </BaseButton>

        <BaseButton
          v-else-if="therapyStore.status === 'paused'"
          type="primary"
          class="action-button"
          @click="resumeTherapy"
        >
          <div class="action-button__content">
            <Play class="btn-icon" />
            <div>
              继续
            </div>
          </div>
        </BaseButton>

        <BaseButton
          type="secondary"
          class="action-button action-button--stop"
          @click="stopTherapy"
          :disabled="therapyStore.status === 'idle'"
        >
          <div class="action-button__content">
            <Square class="btn-icon" />
            <div>
              结束
            </div>
          </div>
        </BaseButton>
      </div>
    </footer>

    <MethodSelector
      v-model:visible="showMethodSelector"
      @confirm="onMethodConfirm"
    />

    <ParamsSettings
      v-model:visible="showParamsSettings"
      @confirm="onParamsConfirm"
    />

    <ConfirmModal
      v-model="showFinishModal"
      title="确认结束"
      confirmText="确认结束"
      :description="finishModalDescription"
      :onConfirm="handleFinishConfirm"
    >
      <p class="finish-modal-info">剩余时间：<span class="remaining-time">{{ formattedTime }}</span></p>
      <p class="finish-modal-question">确认结束本次理疗吗？</p>
    </ConfirmModal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Camera, RotateCcw, Settings, Play, Pause, Square } from 'lucide-vue-next'
import AppHeader from '@/components/layout/AppHeader.vue'
import StepProgress from '@/components/layout/StepProgress.vue'
import BaseButton from '@/components/common/BaseButton.vue'
import ConfirmModal from '@/components/common/ConfirmModal.vue'
import MethodSelector from '@/components/common/MethodSelector.vue'
import ParamsSettings from '@/components/common/ParamsSettings.vue'
import { useTherapyStore } from '@/stores/therapy'
import { useDeviceStore } from '@/stores/device'

const router = useRouter()
const therapyStore = useTherapyStore()
const deviceStore = useDeviceStore()

onMounted(async () => {
  await therapyStore.fetchMethods()
  therapyStore.resetTherapy()
})

onUnmounted(async () => {
  if (therapyStore.status !== 'idle' && therapyStore.currentSessionId) {
    await therapyStore.stopTherapy()
  }
  therapyStore.resetTherapy()
})

const stepList = computed(() => [
  { title: '设备选择', status: 'completed' },
  { title: 'AI分析', status: 'completed' },
  { title: '理疗管理', status: 'current' }
])

const showMethodSelector = ref(false)
const showParamsSettings = ref(false)
const showFinishModal = ref(false)

const deviceName = computed(() => {
  const device = deviceStore.getSelectedDevice()
  return device ? device.name : '艾灸机器人'
})

const methodNames = computed(() => {
  return therapyStore.methods.map(m => `${m.name}(${m.duration}分钟)`).join(' / ')
})

const formattedTime = computed(() => {
  const seconds = therapyStore.remainingTime
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
})

const finishModalDescription = computed(() => {
  const currentRoundElapsed = therapyStore.currentRoundElapsed
  const total = therapyStore.totalElapsed + currentRoundElapsed
  
  const totalMins = Math.floor(total / 60)
  const totalSecs = total % 60
  const formattedTotal = `${totalMins.toString().padStart(2, '0')}:${totalSecs.toString().padStart(2, '0')}`
  
  const currentMins = Math.floor(currentRoundElapsed / 60)
  const currentSecs = currentRoundElapsed % 60
  const formattedCurrent = `${currentMins.toString().padStart(2, '0')}:${currentSecs.toString().padStart(2, '0')}`
  
  return `总计已进行 ${formattedTotal} | 本轮已进行 ${formattedCurrent}`
})

function generateTherapyReport() {
  const startTime = therapyStore.startTime
  const endTime = Date.now()
  const currentRoundElapsed = therapyStore.currentRoundElapsed
  const totalElapsedTime = therapyStore.totalElapsed + currentRoundElapsed
  const methods = therapyStore.methods
  const params = therapyStore.params
  const newTotalDuration = therapyStore.totalDuration
  
  const report = {
    startTime: startTime,
    endTime: endTime,
    duration: totalElapsedTime,
    methods: methods,
    params: params,
    completed: therapyStore.remainingTime === 0,
    statistics: {
      totalMethods: methods.length,
      totalDuration: newTotalDuration,
      currentRoundElapsed: currentRoundElapsed,
      totalElapsed: totalElapsedTime,
      remainingDuration: therapyStore.remainingTime,
      efficiency: totalElapsedTime > 0 ? ((totalElapsedTime / newTotalDuration) * 100).toFixed(1) + '%' : '0%'
    }
  }
  
  console.log('理疗数据统计报告：', report)
  
  return report
}

async function handleFinishConfirm() {
  await therapyStore.stopTherapy()
  generateTherapyReport()
  therapyStore.finishTherapy()
}

function openMethodSelector() {
  showMethodSelector.value = true
}

function onMethodConfirm() {
  if (therapyStore.status !== 'idle' && therapyStore.status !== 'completed') {
    therapyStore.updateMethodsWithAccumulation()
  }
  console.log('手法选择已确认')
}

function onParamsConfirm() {
  console.log('参数设置已确认')
}

function openParamsSettings() {
  showParamsSettings.value = true
}

async function startTherapy() {
  if (!therapyStore.currentSessionId) {
    const device = deviceStore.getSelectedDevice()
    const result = await therapyStore.createSession(
      device?.id,
      therapyStore.methods,
      therapyStore.params
    )
    if (!result.success) {
      console.error('创建理疗会话失败')
      return
    }
  }
  therapyStore.startTherapy()
}

function pauseTherapy() {
  therapyStore.pauseTherapy()
}

function resumeTherapy() {
  therapyStore.resumeTherapy()
}

function stopTherapy() {
  showFinishModal.value = true
}

function confirmFinish() {
  therapyStore.finishTherapy()
}

function goBack() {
  router.push('/ai-analysis')
}
</script>

<style scoped>
.therapy-page {
  min-height: 100vh;
  min-width: 1024px;
  background-image: url('@/assets/images/background.png');
  background-size: cover;
  background-position: center;
  overflow-x: hidden;
  box-sizing: border-box;
}

.therapy-page__header {
  padding: 16px 5%;
  display: flex;
  justify-content: space-between;
}

.back-button {
  background: rgba(232, 137, 76, 0.2);
  border-radius: 24px;
  display: inline-flex;
  align-items: center;
  width: 140px;
  height: 48px;
  font-size: var(--font-size-sm);
  color: rgba(183, 64, 24, 1);
}

.therapy-page__content {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0px 5%;
}

.therapy-page__camera {
  width: 100%;
}

.therapy-page__camera-view {
  width: 100%;
  height: 500px;
  background-color: var(--color-white);
  border-radius: var(--radius-medium);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--color-border);
  position: relative;
  overflow: hidden;
}

.therapy-page__camera-view svg {
  width: 64px;
  height: 64px;
  color: var(--color-text-light);
}

.therapy-page__timer {
  position: absolute;
  bottom: 12px;
  right: 12px;
  background-color: rgba(255, 255, 255, 0.9);
  padding: 10px 16px;
  border-radius: var(--radius-medium);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  z-index: 10;
}

.therapy-page__timer-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-light);
}

.therapy-page__timer-value {
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--color-primary);
}

.therapy-page__footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 5%;
}

.therapy-page__info {
  text-align: left;
}

.therapy-page__device-name {
  font-size: var(--font-size-base);
  font-weight: 600;
  margin-bottom: 2px;
}

.therapy-page__methods {
  font-size: var(--font-size-xs);
  color: var(--color-text-light);
}

.therapy-page__controls {
  display: flex;
  gap: 12px;
}

.action-button {
  border-radius: 50%;
  transition: all 0.3s ease;
  font-size: var(--font-size-sm);
  height: 100px;
  width: 100px;
}

.action-button__content {
  align-items: center;
  justify-content: center;
}

.btn-icon {
  width: 20px;
  height: 20px;
  margin-bottom: 4px;
  flex-shrink: 0;
}

.action-button--stop {
  background: linear-gradient(180deg, rgba(255, 255, 255, 1) 0%, rgba(219, 220, 220, 1) 100%);
  border: 1px solid rgba(219, 220, 220, 1);
  color: rgba(0, 0, 0, 1);
}

.remaining-time {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-primary);
}

.finish-modal-info {
  margin-bottom: 6px;
  font-size: var(--font-size-sm);
  color: var(--color-text);
}

.finish-modal-question {
  margin-top: 6px;
  font-size: var(--font-size-sm);
  color: var(--color-text);
}
</style>
