<template>
  <section class="hero-section" id="home">
    <div class="container"></div>
  </section>
</template>

<script setup></script>

<style scoped>
.hero-section {
  background: url('@/assets/images/main.png') center/cover no-repeat;
  color: white;
  padding: 100px 0;
  min-height: 100vh;
  display: flex;
  align-items: center;
}
@media (max-width: 768px) {
  .hero-section {
    min-height: 50vh;
  }
}
@media (max-width: 640px) {
  .hero-section {
    min-height: 40vh;
  }
}
</style>
