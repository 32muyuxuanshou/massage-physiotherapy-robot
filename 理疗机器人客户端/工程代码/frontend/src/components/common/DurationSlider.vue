<template>
  <div class="duration-slider">
    <div class="duration-slider__component">
      <div v-if="showTicks" class="duration-slider__ticks-row">
        <span v-for="tick in ticks" :key="tick"><span>{{ tick }}</span></span>
      </div>
      <div v-if="showMarks" class="duration-slider__marks-row">
        <span v-for="tick in ticks" :key="tick"><span>|</span></span>
      </div>
      <input type="range" v-model="modelValue" :min="min" :max="max" :step="step" class="duration-slider__input"
        :style="{ '--progress': progress + '%' }" />
    </div>
    <div class="duration-slider__label" :class="`duration-slider__label--${labelType}`">
      <template v-if="labelType === 'circle'">
        <div class="duration-slider__circle">
          <svg class="duration-slider__circle-svg" viewBox="0 0 36 36">
            <path
              class="duration-slider__circle-bg"
              d="M18 2.0845
                a 15.9155 15.9155 0 0 1 0 31.831
                a 15.9155 15.9155 0 0 1 0 -31.831"
            />
            <path
              class="duration-slider__circle-progress"
              :stroke-dasharray="`${progress}, 100`"
              d="M18 2.0845
                a 15.9155 15.9155 0 0 1 0 31.831
                a 15.9155 15.9155 0 0 1 0 -31.831"
            />
          </svg>
          <span class="duration-slider__circle-value">{{ modelValue }}</span>
        </div>
      </template>
      <template v-else-if="labelType === 'clock'">
        <div class="duration-slider__clock">
        <Clock class="duration-slider__icon" />
        <span class="duration-slider__value">{{ modelValue }}</span>
        <span class="duration-slider__unit">{{ unit }}</span>
        </div>

      </template>
      <template v-else>
        <span class="duration-slider__value duration-slider__value--simple">{{ modelValue }}</span>
        <span v-if="unit" class="duration-slider__unit">{{ unit }}</span>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Clock } from 'lucide-vue-next'

const props = defineProps({
  modelValue: {
    type: Number,
    default: 0
  },
  min: {
    type: Number,
    default: 0
  },
  max: {
    type: Number,
    default: 60
  },
  step: {
    type: Number,
    default: 10
  },
  unit: {
    type: String,
    default: 'min'
  },
  showTicks: {
    type: Boolean,
    default: true
  },
  showMarks: {
    type: Boolean,
    default: true
  },
  labelType: {
    type: String,
    default: 'default',
    validator: (value) => ['default', 'clock', 'circle'].includes(value)
  }
})

const emit = defineEmits(['update:modelValue'])

const progress = computed(() => {
  if (props.max <= props.min) return 0
  return ((props.modelValue - props.min) / (props.max - props.min)) * 100
})

const ticks = computed(() => {
  const result = []
  for (let i = props.min; i <= props.max; i += props.step) {
    result.push(i)
  }
  return result
})

const modelValue = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', Number(val))
})
</script>

<style scoped>
.duration-slider {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 60px;
}

.duration-slider__component {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.duration-slider__ticks-row {
  display: flex;
  justify-content: space-between;
  width: 100%;
}

.duration-slider__ticks-row span {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(232, 138, 77, 1);
  font-size: var(--font-size-xs);
}

.duration-slider__marks-row {
  display: flex;
  justify-content: space-between;
  width: 100%;
}

.duration-slider__marks-row span {
  width: 24px;
  height: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(232, 138, 77, 1);
}

.duration-slider__input {
  width: 100%;
  height: 6px;
  -webkit-appearance: none;
  appearance: none;
  background: linear-gradient(to right, rgba(232, 138, 77, 1) 0%, rgba(232, 138, 77, 1) var(--progress, 0%), rgba(200, 201, 202, 1) var(--progress, 0%), rgba(200, 201, 202, 1) 100%);
  border-radius: 3px;
  outline: none;
}

.duration-slider__input::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--color-primary);
  cursor: pointer;
  border: 9px solid rgba(255, 251, 236, 1);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
}

.duration-slider__input::-moz-range-thumb {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--color-primary);
  cursor: pointer;
  border: 6px solid rgba(255, 251, 236, 1);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
}

.duration-slider__label {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  min-width: 60px;
}

.duration-slider__label--circle {
  min-width: auto;
}

.duration-slider__label--default {
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.duration-slider__value--simple {
  font-size: var(--font-size-lg);
}

.duration-slider__icon {
  width: 18px;
  height: 18px;
  color: rgba(183, 64, 24, 1);
  margin-right: 6px;
}

.duration-slider__value {
  font-size: var(--font-size-xl);
  font-weight: 600;
  color: rgba(183, 64, 24, 1);
  min-width: 28px;
  text-align: right;
}

.duration-slider__unit {
  font-size: var(--font-size-xs);
  color: var(--color-primary-light);
  margin-top: 8px;
}

.duration-slider__circle {
  position: relative;
  width: 48px;
  height: 48px;
  margin-top: 18px;
}

.duration-slider__circle-svg {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}

.duration-slider__circle-bg {
  fill: none;
  stroke: rgba(200, 201, 202, 1);
  stroke-width: 3;
}

.duration-slider__circle-progress {
  fill: none;
  stroke: var(--color-primary);
  stroke-width: 3;
  stroke-linecap: round;
  transition: stroke-dasharray 0.3s ease;
}

.duration-slider__circle-value {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-primary);
}

.duration-slider__clock {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-top: 18px;
}
</style>
