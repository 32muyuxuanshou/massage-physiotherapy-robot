<template>
  <div class="step-progress">
    <div 
      v-for="(step, index) in steps" 
      :key="index"
      class="step-progress__item"
    >
      <div 
        class="step-progress__dot"
        :class="{ 
          'is-completed': step.status === 'completed',
          'is-current': step.status === 'current'
        }"
      >
        <span class="step-progress__dot-inner"></span>
      </div>
      <span 
        class="step-progress__title"
        :class="{ 
          'is-completed': step.status === 'completed',
          'is-current': step.status === 'current'
        }"
      >
        {{ step.title }}
      </span>
      <div 
        v-if="index < steps.length - 1" 
        class="step-progress__line"
        :class="{ 'is-completed': step.status === 'completed' }"
      />
    </div>
  </div>
</template>

<script setup>
defineProps({
  steps: {
    type: Array,
    required: true,
    validator: (arr) => arr.every(s => ['title', 'status'].every(k => k in s))
  }
})
</script>

<style scoped>
.step-progress {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  height: 48px;
}

.step-progress__item {
  display: flex;
  align-items: center;
}

.step-progress__dot {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 1px solid var(--color-text-light);
  position: relative;
  transition: all 0.3s ease;
}

.step-progress__dot-inner {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.step-progress__dot.is-completed {
  border-color: var(--color-primary);
}

.step-progress__dot.is-completed .step-progress__dot-inner {
  background-color: var(--color-primary);
}

.step-progress__dot.is-current {
  border-color: var(--color-primary);
  animation: pulse 1.5s ease-in-out infinite;
}

.step-progress__dot.is-current .step-progress__dot-inner {
  background-color: var(--color-primary);
  animation: dot-pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(var(--color-primary-rgb), 0.4);
  }
  50% {
    box-shadow: 0 0 0 6px rgba(var(--color-primary-rgb), 0);
  }
}

@keyframes dot-pulse {
  0%, 100% {
    transform: translate(-50%, -50%) scale(1);
    opacity: 1;
  }
  50% {
    transform: translate(-50%, -50%) scale(0.8);
    opacity: 0.7;
  }
}

.step-progress__title {
  margin-left: 6px;
  font-size: var(--font-size-xs);
  color: var(--color-text-light);
}

.step-progress__title.is-completed,
.step-progress__title.is-current {
  color: var(--color-text);
  font-weight: 500;
}

.step-progress__line {
  width: 100px;
  height: 2px;
  background-image: repeating-linear-gradient(
    90deg,
    var(--color-text-light) 0,
    var(--color-text-light) 5px,
    transparent 5px,
    transparent 10px
  );
  background-size: 10px 2px;
  background-repeat: repeat-x;
  background-position: center;
  position: relative;
  margin: 0 6px;
}

.step-progress__line.is-completed {
  background-image: repeating-linear-gradient(
    90deg,
    var(--color-primary) 0,
    var(--color-primary) 5px,
    transparent 5px,
    transparent 10px
  );
}

.step-progress__line::after {
  content: '';
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  border-left: 5px solid var(--color-text-light);
  border-top: 3px solid transparent;
  border-bottom: 3px solid transparent;
}

.step-progress__line.is-completed::after {
  border-left-color: var(--color-primary);
}
</style>
