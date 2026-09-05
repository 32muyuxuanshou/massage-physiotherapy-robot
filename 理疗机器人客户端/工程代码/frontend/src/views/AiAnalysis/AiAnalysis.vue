<template>
  <div class="ai-analysis-page">
    <AppHeader />
    
    <div class="ai-analysis-page__header">
      <StepProgress :steps="stepList" />
      <BaseButton type="secondary" class="back-button" @click="goBack">
        上一步
      </BaseButton>
    </div>
    
    <main class="ai-analysis-page__content">
      <div class="ai-analysis-page__camera">
        <div class="ai-analysis-page__camera-view">
          <Camera v-if="!therapyStore.aiAnalysis.analyzed" />
          <div v-else class="ai-analysis-page__analyzed">
            <div class="ai-analysis-page__region" v-for="region in therapyStore.aiAnalysis.regions" :key="region">
              {{ region }}
            </div>
          </div>
          <p class="ai-analysis-page__camera-hint">
            {{ cameraHint }}
          </p>
        </div>
      </div>
    </main>
    
    <footer class="ai-analysis-page__footer">
      <div class="ai-analysis-page__actions">
        <BaseButton type="secondary" :class="['action-button', `action-button--${captureButtonState}`]" @click="captureImage" :loading="isCapturing">
          <span class="action-button__content">
            <Camera class="btn-icon" />
            {{ captureButtonText }}
          </span>
        </BaseButton>
        
        <BaseButton type="secondary" :class="['action-button', `action-button--${analyzeButtonState}`]" @click="startAnalysis" :disabled="analyzeButtonDisabled" :loading="isAnalyzing">
          <span class="action-button__content">
            <Sparkles class="btn-icon" />
            {{ analyzeButtonText }}
          </span>
        </BaseButton>
        
        <BaseButton type="secondary" :class="['action-button', `action-button--${methodButtonState}`]" @click="openMethodSelector" :disabled="methodButtonDisabled">
          <span class="action-button__content">
            <Settings class="btn-icon" />
            {{ methodButtonText }}
          </span>
        </BaseButton>
      </div>
      
      <BaseButton type="primary" size="large" :disabled="!canGoNext" @click="goNext">
        下一步
      </BaseButton>
    </footer>

    <MethodSelector
      v-model:visible="showMethodSelector"
      @confirm="confirmMethod"
    />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { Camera, Sparkles, Settings } from 'lucide-vue-next'
import AppHeader from '@/components/layout/AppHeader.vue'
import StepProgress from '@/components/layout/StepProgress.vue'
import BaseButton from '@/components/common/BaseButton.vue'
import MethodSelector from '@/components/common/MethodSelector.vue'
import { useTherapyStore } from '@/stores/therapy'

const router = useRouter()
const therapyStore = useTherapyStore()

const stepList = computed(() => [
  { title: '设备选择', status: 'completed' },
  { title: 'AI分析', status: 'current' },
  { title: '理疗管理', status: 'pending' }
])

const isCapturing = ref(false)
const isAnalyzing = ref(false)
const showMethodSelector = ref(false)

const cameraHint = computed(() => {
  if (isCapturing.value) return '正在采集...'
  if (isAnalyzing.value) return '正在分析...'
  if (!therapyStore.aiAnalysisPage.hasCaptured) return '请先采集图像'
  if (therapyStore.aiAnalysisPage.hasCaptured && !therapyStore.aiAnalysisPage.hasAnalyzed) return '等待智能分析'
  if (therapyStore.aiAnalysisPage.hasAnalyzed && !therapyStore.aiAnalysisPage.hasMethodSet) return '请设置理疗手法'
  if (therapyStore.aiAnalysisPage.hasCaptured && therapyStore.aiAnalysisPage.hasAnalyzed && therapyStore.aiAnalysisPage.hasMethodSet) return '可重新采集或分析'
  return '等待采集图像'
})

const canAnalyze = computed(() => {
  return therapyStore.aiAnalysis.modelData !== null && !isAnalyzing.value
})

const canGoNext = computed(() => {
  return therapyStore.aiAnalysis.analyzed && therapyStore.methods.length > 0 && therapyStore.aiAnalysisPage.hasMethodSet
})

const captureButtonText = computed(() => {
  return therapyStore.aiAnalysisPage.hasCaptured ? '再次采集' : '采集图像'
})

const analyzeButtonText = computed(() => {
  return therapyStore.aiAnalysisPage.hasAnalyzed ? '再次分析' : '智能分析'
})

const methodButtonText = computed(() => {
  return therapyStore.aiAnalysisPage.hasMethodSet ? '重设手法' : '设置手法'
})

const captureButtonState = computed(() => {
  if (isCapturing.value) return 'loading'
  if (therapyStore.aiAnalysisPage.hasCaptured) return 'completed'
  return 'default'
})

const analyzeButtonState = computed(() => {
  if (!therapyStore.aiAnalysisPage.hasCaptured) return 'pending'
  if (isAnalyzing.value) return 'loading'
  if (therapyStore.aiAnalysisPage.hasAnalyzed) return 'completed'
  return 'default'
})

const methodButtonState = computed(() => {
  if (!therapyStore.aiAnalysisPage.hasAnalyzed) return 'pending'
  if (therapyStore.aiAnalysisPage.hasMethodSet) return 'completed'
  return 'default'
})

const analyzeButtonDisabled = computed(() => {
  return !therapyStore.aiAnalysisPage.hasCaptured || isAnalyzing.value
})

const methodButtonDisabled = computed(() => {
  return !therapyStore.aiAnalysisPage.hasAnalyzed
})

async function captureImage() {
  try {
    therapyStore.setAiAnalysisPage({ hasAnalyzed: false, hasMethodSet: false })
    isCapturing.value = true
    
    // 调用后端 API
    const result = await therapyStore.captureImage()
    
    if (result.success) {
      therapyStore.setAiAnalysis({
        modelData: result.data,
        analyzed: false,
        regions: []
      })
      therapyStore.setAiAnalysisPage({ hasCaptured: true })
    } else {
      console.error('采集图像失败:', result.message)
    }
  } catch (error) {
    console.error('采集图像失败:', error)
  } finally {
    isCapturing.value = false
  }
}

async function startAnalysis() {
  try {
    isAnalyzing.value = true
    
    // 调用后端 API 进行 AI 分析
    const captureId = therapyStore.aiAnalysis.modelData?.id
    if (!captureId) {
      console.error('没有采集图像，无法分析')
      return
    }
    
    const result = await therapyStore.analyzeImage(captureId)
    
    if (result.success) {
      therapyStore.setAiAnalysis({
        modelData: result.data,
        analyzed: true,
        regions: result.data.body_parts ? JSON.parse(result.data.body_parts) : []
      })
      therapyStore.setAiAnalysisPage({ hasAnalyzed: true })
    } else {
      console.error('AI分析失败:', result.message)
    }
  } catch (error) {
    console.error('AI分析失败:', error)
  } finally {
    isAnalyzing.value = false
  }
}

function openMethodSelector() {
  showMethodSelector.value = true
}

function confirmMethod() {
  therapyStore.setAiAnalysisPage({ hasMethodSet: true })
}

function goNext() {
  router.push('/therapy-management')
}

function goBack() {
  router.push('/home')
}
</script>

<style scoped>
.ai-analysis-page {
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

.ai-analysis-page__header {
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

.ai-analysis-page__content {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0px 5%;
}

.ai-analysis-page__camera {
  width: 100%;
}

.ai-analysis-page__camera-view {
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

.ai-analysis-page__camera-view svg {
  width: 64px;
  height: 64px;
  color: var(--color-text-light);
}

.ai-analysis-page__analyzed {
  display: flex;
  gap: 12px;
  padding: 16px;
  flex-wrap: wrap;
}

.ai-analysis-page__region {
  padding: 10px 20px;
  background-color: rgba(230, 138, 79, 0.2);
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-medium);
  color: var(--color-primary);
  font-size: var(--font-size-sm);
}

.ai-analysis-page__camera-hint {
  position: absolute;
  bottom: 12px;
  left: 12px;
  color: var(--color-text-light);
  font-size: var(--font-size-xs);
}

.ai-analysis-page__footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 5%;
}

.ai-analysis-page__footer :deep(.base-button--primary) {
  width: 180px;
  height: 48px;
  font-size: var(--font-size-base);
}

.ai-analysis-page__actions {
  display: flex;
  gap: 12px;
}

.btn-icon {
  width: 18px;
  height: 18px;
  margin-right: 6px;
  flex-shrink: 0;
}

.action-button {
  border-radius: 24px;
  transition: all 0.3s ease;
  font-size: var(--font-size-sm);
  height: 48px;
  width: 140px;
}

.action-button__content {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.action-button--default {
  background: rgba(232, 137, 76, 1);
  color: white;
}

.action-button--pending {
  background: linear-gradient(180deg, rgba(255, 255, 255, 1) 0%, rgba(219, 220, 220, 1) 100%);
  border: 1px solid rgba(219, 220, 220, 1);
  color: rgba(0, 0, 0, 1);
}

.action-button--completed {
  background: rgba(232, 137, 76, 0.2);
  color: rgba(183, 64, 24, 1);
}

.action-button--loading {
  background: rgba(232, 137, 76, 1);
}
</style>
