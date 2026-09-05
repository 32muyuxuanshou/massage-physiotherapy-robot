<template>
  <BaseModal
    :visible="isVisible"
    :title="title"
    :width="width"
    :closable="false"
    :maskClosable="false"
    @update:modelValue="handleVisibilityChange"
    @close="handleClose"
  >
    <div class="confirm-modal-content">
      <div v-if="description" class="confirm-modal-description">
        <slot name="description">{{ description }}</slot>
      </div>
      <slot />
    </div>
    <template #footer>
      <div class="confirm-modal-footer">
        <BaseButton type="secondary" @click="handleCancel">
          {{ cancelText }}
        </BaseButton>
        <BaseButton :type="confirmType" @click="handleConfirm">
          {{ confirmText }}
        </BaseButton>
      </div>
    </template>
  </BaseModal>
</template>

<script setup>
import { ref, watch } from 'vue'
import BaseModal from './BaseModal.vue'
import BaseButton from './BaseButton.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: '确认'
  },
  width: {
    type: String,
    default: '400px'
  },
  confirmText: {
    type: String,
    default: '确认'
  },
  cancelText: {
    type: String,
    default: '取消'
  },
  confirmType: {
    type: String,
    default: 'primary'
  },
  description: {
    type: String,
    default: ''
  },
  onConfirm: {
    type: Function,
    default: null
  }
})

const emit = defineEmits(['update:modelValue', 'confirm', 'cancel'])

const isVisible = ref(props.modelValue)

watch(() => props.modelValue, (newVal) => {
  isVisible.value = newVal
})

function handleVisibilityChange(value) {
  isVisible.value = value
  emit('update:modelValue', value)
}

function handleClose() {
  emit('update:modelValue', false)
}

function handleConfirm() {
  if (props.onConfirm && typeof props.onConfirm === 'function') {
    props.onConfirm()
  }
  emit('update:modelValue', false)
  emit('confirm')
}

function handleCancel() {
  emit('update:modelValue', false)
  emit('cancel')
}
</script>

<style scoped>
.confirm-modal-content {
  text-align: center;
  font-size: var(--font-size-sm);
  color: var(--color-text);
}

.confirm-modal-description {
  margin-bottom: 12px;
  font-size: var(--font-size-xs);
  color: var(--color-text-light);
}

.confirm-modal-footer {
  justify-content: center;
  display: flex;
  width: 100%;
  gap: 12px;
}
</style>
