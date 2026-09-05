<!-- src/components/HighlightCard.vue -->
<template>
  <div class="card border-0 shadow-sm text-center p-4 h-100">
    <div class="fs-2 fw-bold mb-2">{{ value }}</div>
    <div class="text-muted small">{{ label }}</div>
  </div>
</template>

<script setup>
defineProps({
  value: {
    type: String,
    required: true,
  },
  label: {
    type: String,
    required: true,
  },
})
</script>

<style scoped>
.card {
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
}
</style>
