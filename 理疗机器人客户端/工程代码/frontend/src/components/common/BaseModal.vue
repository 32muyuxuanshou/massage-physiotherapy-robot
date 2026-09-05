<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="modalVisible" class="base-modal" @click="handleMaskClick">
        <div class="base-modal__content" :style="{ width: width }" @click.stop>
          <div v-if="title || closable" class="base-modal__header">
            <h3 class="base-modal__title">{{ title }}</h3>
            <span v-if="closable" class="base-modal__close" @click="handleClose">×</span>
          </div>
          <div class="base-modal__body">
            <slot />
          </div>
          <div v-if="$slots.footer" class="base-modal__footer">
            <slot name="footer" />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: ''
  },
  width: {
    type: String,
    default: '480px'
  },
  closable: {
    type: Boolean,
    default: true
  },
  maskClosable: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['update:modelValue', 'update:visible', 'close'])

const modalVisible = computed({
  get() {
    return props.visible
  },
  set(value) {
    emit('update:modelValue', value)
    emit('update:visible', value)
  }
})

function handleClose() {
  emit('update:modelValue', false)
  emit('update:visible', false)
  emit('close')
}

function handleMaskClick() {
  if (props.maskClosable) {
    handleClose()
  }
}
</script>

<style scoped>
.base-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.base-modal__content {
  background-color: var(--color-white);
  border-radius: var(--radius-medium);
  max-width: 90vw;
  max-height: 90vh;
  overflow: auto;
}

.base-modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: rgba(255, 253, 242, 1);
}

.base-modal__title {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text);
}

.base-modal__close {
  font-size: 20px;
  color: var(--color-text-light);
  cursor: pointer;
  transition: color 0.2s;
}

.base-modal__close:hover {
  color: var(--color-text);
}

.base-modal__body {
  padding: 20px;
  background: rgba(255, 253, 242, 1);
}

.base-modal__footer {
  padding: 12px 20px;
  background: rgba(255, 253, 242, 1);
  justify-content: center;
  width: 100%;
  gap: 12px;
  display: flex;
}


.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

</style>
