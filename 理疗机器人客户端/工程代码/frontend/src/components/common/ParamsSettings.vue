<template>
  <BaseModal
    :visible="visible"
    @update:visible="$emit('update:visible', $event)"
    title="参数设置"
    width="1000px"
  >
    <div class="params-settings">
      <div class="params-settings__item">
        <div class="params-settings__label">
          <span class="params-settings__label-text">高度</span>
           <DurationSlider v-model="height" :min="0" :max="100" :step="20" labelType="circle" class="params-settings__slider" />
        </div>
       
      </div>

      <div class="params-settings__item">
        <div class="params-settings__label">
          <span class="params-settings__label-text">速度</span>
          <DurationSlider v-model="speed" :min="0" :max="100" :step="20" labelType="circle" class="params-settings__slider" />
        </div>
        
      </div>

      <div class="params-settings__item">
        <div class="params-settings__label">
          <span class="params-settings__label-text">力度</span>
          <DurationSlider v-model="intensity" :min="0" :max="5" :step="1" labelType="circle" class="params-settings__slider" />
        </div>
        
      </div>
    </div>
    <template #footer>
      <BaseButton type="primary" class="confirm-button" @click="confirmSettings">确认</BaseButton>
    </template>
  </BaseModal>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import BaseModal from './BaseModal.vue'
import BaseButton from './BaseButton.vue'
import DurationSlider from './DurationSlider.vue'
import { useTherapyStore } from '@/stores/therapy'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:visible', 'confirm'])

const therapyStore = useTherapyStore()

const height = ref(Number(therapyStore.params.height))
const speed = ref(Number(therapyStore.params.speed))
const intensity = ref(Number(therapyStore.params.intensity))

watch(() => props.visible, (newVal) => {
  if (newVal) {
    height.value = Number(therapyStore.params.height)
    speed.value = Number(therapyStore.params.speed)
    intensity.value = Number(therapyStore.params.intensity)
  }
})

function confirmSettings() {
  therapyStore.updateParams({
    height: Number(height.value),
    speed: Number(speed.value),
    intensity: Number(intensity.value)
  })
  emit('update:visible', false)
  emit('confirm')
}
</script>

<style scoped>
.params-settings {
  padding: 16px;
}

.params-settings__item {
  height: 60px;
  margin-bottom: 16px;
}

.params-settings__item:last-child {
  margin-bottom: 0;
}

.params-settings__label {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: center;
}

.params-settings__label-text {
  font-size: var(--font-size-base);
  font-weight: 700;
  color: var(--color-primary);
  margin-top: 24px;
  margin-right: 8px;
}

.params-settings__label-value {
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--color-primary);
}

.params-settings__slider {
  width: 90%;
}

.params-settings__slider :deep(.duration-slider) {
  width: 90%;
}

.confirm-button {
  width: 220px;
  height: 48px;
  font-size: var(--font-size-base);
  letter-spacing: 12px;
  text-align: center;
  text-indent: 12px;
}
</style>
