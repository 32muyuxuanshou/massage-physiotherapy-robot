<template>
  <button
    :class="['base-button', `base-button--${type}`, `base-button--${size}`, { 'is-disabled': disabled, 'is-loading': loading }]"
    :disabled="disabled || loading"
    @click="handleClick"
  >
    <span v-if="loading" class="base-button__loading">...</span>
    <span v-else class="base-button__content">
      <slot />
    </span>
  </button>
</template>

<script setup>
defineProps({
  type: {
    type: String,
    default: 'primary',
    validator: (v) => ['primary', 'secondary', 'ghost'].includes(v)
  },
  size: {
    type: String,
    default: 'medium',
    validator: (v) => ['small', 'medium', 'large'].includes(v)
  },
  disabled: {
    type: Boolean,
    default: false
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['click'])

function handleClick(e) {
  emit('click', e)
}
</script>

<style scoped>
.base-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--radius-full);
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.base-button--small {
  padding: 6px 12px;
  font-size: var(--font-size-xs);
}

.base-button--medium {
  padding: 10px 20px;
  font-size: var(--font-size-sm);
}

.base-button--large {
  padding: 12px 24px;
  font-size: var(--font-size-base);
}

.base-button--primary {
  background-color: var(--color-primary);
  color: var(--color-white);
}

.base-button--primary:hover:not(.is-disabled) {
  background-color: var(--color-primary-light);
}

.base-button--secondary {
  background-color: var(--color-primary-lighter);
  color: var(--color-text);
}

.base-button--ghost {
  background-color: transparent;
  color: var(--color-primary);
  border: 1px solid var(--color-primary);
}

.base-button.is-disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.base-button.is-loading {
  opacity: 0.8;
}
</style>
