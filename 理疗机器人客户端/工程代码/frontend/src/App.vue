<template>
  <router-view />
  <div id="desktop-close-container">
    <button v-if="!showCloseBtn" class="arrow-btn" @click="showCloseBtn = true">&#8249;</button>
    <div v-else class="close-panel">
      <button class="close-btn" @click="triggerClose">X 关闭应用</button>
      <button class="collapse-btn" @click="showCloseBtn = false">&#8250;</button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const showCloseBtn = ref(false);

const closeWindow = () => {
  if (window.pywebview?.api?.close_window) {
    window.pywebview.api.close_window();
  }
};

const triggerClose = () => {
  closeWindow();
};
</script>

<style>
#desktop-close-container {
  position: fixed;
  top: 8px;
  right: 8px;
  z-index: 99999;
}
.arrow-btn {
  width: 20px;
  height: 32px;
  background: rgba(0, 0, 0, 0.4);
  color: #fff;
  border: none;
  border-radius: 4px 0 0 4px;
  cursor: pointer;
  font-size: 14px;
}
.arrow-btn:hover {
  background: rgba(0, 0, 0, 0.6);
}
.close-panel {
  display: flex;
  align-items: center;
  gap: 4px;
}
.close-btn {
  padding: 8px 12px;
  background: #e74c3c;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}
.close-btn:hover {
  background: #c0392b;
}
.collapse-btn {
  width: 20px;
  height: 32px;
  background: rgba(0, 0, 0, 0.3);
  color: #fff;
  border: none;
  border-radius: 0 4px 4px 0;
  cursor: pointer;
  font-size: 14px;
}
.collapse-btn:hover {
  background: rgba(0, 0, 0, 0.5);
}
</style>
