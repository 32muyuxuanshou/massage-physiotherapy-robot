<template>
  <BaseModal
    :visible="visible"
    @update:visible="$emit('update:visible', $event)"
    width="1000px"
    :showTitle="false"
  >
    <div class="method-selector">
      <div class="method-selector__header">
        <Settings class="method-selector__header-icon" />
        <span class="method-selector__header-title">选择理疗手法</span>
      </div>

      <div class="method-selector__list">
        <div
          v-for="method in methodOptions"
          :key="method.type"
          class="method-card"
          :class="{ 'is-selected': selectedMethods.some(m => m.type === method.type) }"
          @click="toggleMethod(method)"
        >
          <div class="method-card__icon-wrap">
            <img :src="method.icon" class="method-card__icon" />
          </div>
          <span class="method-card__name">{{ method.name }}</span>
        </div>
      </div>

      <div class="method-selector__duration">
        <DurationSlider v-model="selectedDuration" :min="0" :max="60" :step="10" :showTicks="true" :showMarks="true" labelType="clock"/>
      </div>

      <div class="method-selector__tags">
        <div
          v-for="method in selectedMethods"
          :key="method.type"
          class="method-tag"
        >
          <span class="method-tag__name">{{ method.name }}</span>
          <span class="method-tag__duration">{{ method.duration }}分钟</span>
          <span class="method-tag__close" @click="removeMethod(method.type)">
            <X class="method-tag__close-icon" />
          </span>
        </div>
      </div>
    </div>
    <template #footer>
      <div class="method-selector__footer">
        <BaseButton type="primary" class="confirm-button" @click="confirmMethod">
          确认
        </BaseButton>
      </div>
    </template>
  </BaseModal>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Settings, X } from 'lucide-vue-next'
import BaseModal from './BaseModal.vue'
import BaseButton from './BaseButton.vue'
import DurationSlider from './DurationSlider.vue'
import { useTherapyStore } from '@/stores/therapy'

import TuinaIcon from '@/assets/icons/推拿手法.svg'
import XueweiIcon from '@/assets/icons/点穴手法.svg'
import NiannieIcon from '@/assets/icons/揉捏手法.svg'
import PaidaIcon from '@/assets/icons/拍打手法.svg'

defineProps({
  visible: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:visible', 'confirm'])

const therapyStore = useTherapyStore()
const selectedDuration = ref(Number(30))

const methodOptions = [
  { type: 'tuina', name: '推拿手法', icon: TuinaIcon },
  { type: 'xuewei', name: '点穴疗法', icon: XueweiIcon },
  { type: 'niannie', name: '揉捏技法', icon: NiannieIcon },
  { type: 'paida', name: '拍打疗法', icon: PaidaIcon }
]

const selectedMethods = computed(() => therapyStore.methods)

function toggleMethod(method) {
  const existing = selectedMethods.value.find(m => m.type === method.type)
  if (existing) {
    therapyStore.removeMethod(method.type)
  } else {
    therapyStore.addMethod({
      type: method.type,
      name: method.name,
      duration: selectedDuration.value
    })
  }
}

function removeMethod(type) {
  therapyStore.removeMethod(type)
}

function confirmMethod() {
  emit('update:visible', false)
  emit('confirm')
}
</script>

<style scoped>
.method-selector {
  background: rgba(255, 253, 242, 1);
  padding: 0 3%;
  min-height: 320px;
}

.method-selector__header {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.method-selector__header-icon {
  width: 20px;
  height: 20px;
  color: var(--color-primary);
  margin-right: 6px;
}

.method-selector__header-title {
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--color-text);
}

.method-selector__list {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 12px;
  margin-bottom: 16px;
  align-items: center;
  justify-content: center;
}

.method-selector__list::-webkit-scrollbar {
  height: 4px;
}

.method-selector__list::-webkit-scrollbar-thumb {
  background: rgba(232, 137, 76, 0.3);
  border-radius: 2px;
}

.method-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  flex-shrink: 0;
}

.method-card__icon-wrap {
  width: 160px;
  height: 96px;
  padding: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--color-primary-lighter);
  border-radius: var(--radius-medium);
  overflow: hidden;
}

.method-card.is-selected .method-card__icon-wrap {
  background-color: var(--color-primary);
}

.method-card__icon {
  width: 100%;
  height: 100%;
  object-fit: contain;
  filter: none;
  transition: filter 0.2s ease;
}

.method-card.is-selected .method-card__icon {
  filter: brightness(0) invert(1);
}

.method-card__name {
  margin-top: 8px;
  font-size: var(--font-size-sm);
  color: var(--color-text);
}

.method-selector__duration {
  margin-bottom: 16px;
  margin-left: 3%;
  margin-right: 3%;
}

.method-selector__tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  min-height: 60px;
  padding: 24px 0 24px 0;
}

.method-tag {
  display: inline-flex;
  align-items: center;
  padding: 12px 12px;
  background-color: rgba(232, 137, 76, 0.1);
  border-radius: 16px;
  font-size: var(--font-size-sm);
  position: relative;
}

.method-tag__name {
  color: rgba(183, 64, 24, 1);
  font-weight: 600;
  font-size: var(--font-size-base);
  margin-right: 6px;
}

.method-tag__duration {
  color: rgba(232, 138, 77, 1);
  font-weight: 600;
  font-size: var(--font-size-base);
  margin-right: 4px;
}

.method-tag__close {
  position: absolute;
  top: -8px;
  right: -8px;
  width: 20px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(232, 137, 76, 1);
  border-radius: 50%;
  cursor: pointer;
}

.method-tag__close-icon {
  width: 14px;
  height: 14px;
  color: var(--color-white);
}

.method-selector__footer {
  justify-content: center;
  display: flex;
  width: 100%;
  gap: 12px;
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
