<template>
  <div class="base-input" :class="{ 'is-focused': focused, 'has-error': error }">
    <span v-if="prefixIcon" class="base-input__icon base-input__icon--prefix">
      <slot name="prefix" />
    </span>
    <input
      class="base-input__field"
      :type="inputType"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      @input="handleInput"
      @focus="handleFocus"
      @blur="handleBlur"
    />
    <span v-if="suffixIcon" class="base-input__icon base-input__icon--suffix">
      <slot name="suffix" />
    </span>
  </div>
  <span v-if="error" class="base-input__error">{{ error }}</span>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  type: {
    type: String,
    default: 'text'
  },
  placeholder: {
    type: String,
    default: ''
  },
  disabled: {
    type: Boolean,
    default: false
  },
  prefixIcon: {
    type: Boolean,
    default: false
  },
  suffixIcon: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue'])

const focused = ref(false)
const showPassword = ref(false)

const inputType = computed(() => {
  if (props.type === 'password') {
    return showPassword.value ? 'text' : 'password'
  }
  return props.type
})

const hideDefaultSuffix = computed(() => {
  return props.type === 'password'
})

function handleInput(e) {
  emit('update:modelValue', e.target.value)
}

function handleFocus() {
  focused.value = true
}

function handleBlur() {
  focused.value = false
}

function handleTogglePassword() {
  if (props.type === 'password') {
    showPassword.value = !showPassword.value
  }
}
</script>

<style scoped>
.base-input {
  display: flex;
  align-items: center;
  background-color: var(--color-primary-lighter);
  border-radius: var(--radius-full);
  padding: 0 20px;
  transition: all 0.2s ease;
}

.base-input.is-focused {
  box-shadow: 0 0 0 2px var(--color-primary);
}

.base-input.has-error {
  box-shadow: 0 0 0 2px var(--color-error);
}

.base-input__field {
  flex: 1;
  border: none;
  background: transparent;
  padding: 10px 0;
  font-size: var(--font-size-sm);
  color: var(--color-text);
  outline: none;
}

.base-input__field::placeholder {
  color: var(--color-text-light);
}

.base-input__field:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.base-input__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-light);
}

.base-input__icon--prefix {
  margin-right: 6px;
}

.base-input__icon--suffix {
  margin-left: 6px;
  cursor: pointer;
}

.base-input__icon--suffix.is-hidden {
  display: none;
}

.base-input__error {
  display: block;
  margin-top: 4px;
  font-size: var(--font-size-xs);
  color: var(--color-error);
}
</style>
