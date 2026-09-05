<template>
  <div id="app">
    <AppHeader />
    <main>
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { RouterView } from 'vue-router'
import AppHeader from './components/AppHeader.vue'
</script>

<style>
:root {
  --primary-color: #2c3e50;
  --secondary-color: #3498db;
  --accent-color: #e74c3c;
}

/* 全局样式 */
.service-card {
  transition: transform 0.3s;
  border: none;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  height: 100%;
}

.service-card:hover {
  transform: translateY(-5px);
}

@media (max-width: 768px) {
  .hero-section {
    padding: 60px 0;
    text-align: center;
  }
}
</style>
