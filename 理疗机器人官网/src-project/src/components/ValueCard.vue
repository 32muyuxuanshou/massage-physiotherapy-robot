<!-- ValueCard.vue -->
<template>
  <div class="value-card">
    <div class="image-container">
      <img :src="imageUrl" :alt="title" />
    </div>
    <div class="content-wrapper">
      <h2 class="title">{{ title }}</h2>
      <p class="subtitle">{{ subtitle }}</p>
      <div class="features">
        <div v-for="(feature, index) in features" :key="index" class="feature-item">
          <div class="icon">
            <i :class="feature.icon"></i>
          </div>
          <div class="text">
            <h3>{{ feature.title }}</h3>
            <p>{{ feature.description }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    required: true,
  },
  subtitle: {
    type: String,
    required: true,
  },
  imageUrl: {
    type: String,
    required: true,
  },
  features: {
    type: Array,
    required: true,
    default: () => [],
  },
})
</script>

<style scoped>
.value-card {
  display: flex;
  width: 100%;
  height: 100%;
  background-color: #f8f9fa;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
}

.image-container {
  flex: 1;
  overflow: hidden;
}

.image-container img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.content-wrapper {
  flex: 1;
  padding: 40px;
  background-color: white;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.title {
  font-size: 2rem;
  font-weight: bold;
  margin-bottom: 10px;
  color: #333;
}

.subtitle {
  font-size: 1rem;
  color: #666;
  margin-bottom: 30px;
  opacity: 0.8;
}

.features {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.feature-item {
  display: flex;
  align-items: flex-start;
  gap: 15px;
}

.icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f0f0f0;
  border-radius: 50%;
  flex-shrink: 0;
}

.text h3 {
  font-size: 1.1rem;
  margin: 0 0 8px 0;
  color: #333;
}

.text p {
  font-size: 0.9rem;
  color: #666;
  margin: 0;
}

@media (max-width: 1200px) {
  .value-card {
    flex-direction: column;
  }

  .image-container {
    height: 300px;
  }

  .content-wrapper {
    padding: 30px;
  }
}
</style>
