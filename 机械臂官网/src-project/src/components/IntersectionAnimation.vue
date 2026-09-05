<!-- src/components/IntersectionAnimation.vue -->
<template>
  <div ref="animationContainer" :class="containerClass" :data-animation="animationType">
    <slot :animated="elementVisible"></slot>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  animationType: {
    type: String,
    default: 'fade-up', // fade-up, slide-left, slide-right 等
  },
  delay: {
    type: Number,
    default: 0,
  },
  threshold: {
    type: Number,
    default: 0.3,
  },
  rootMargin: {
    type: String,
    default: '0px 0px -50px 0px',
  },
})

const elementVisible = ref(false)
const animationContainer = ref(null)
let observer = null

const getAnimationClass = () => {
  const classMap = {
    'fade-up': 'animate-fade-up',
    'slide-left': 'animate-slide-left',
    'slide-right': 'animate-slide-right',
    'slide-up': 'animate-slide-up',
  }
  return classMap[props.animationType] || 'animate-fade-up'
}

const containerClass = ref('')

onMounted(() => {
  containerClass.value = getAnimationClass()

  observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          if (props.delay > 0) {
            setTimeout(() => {
              elementVisible.value = true
            }, props.delay)
          } else {
            elementVisible.value = true
          }
          observer.unobserve(entry.target)
        }
      })
    },
    {
      threshold: props.threshold,
      rootMargin: props.rootMargin,
    }
  )

  if (animationContainer.value) {
    observer.observe(animationContainer.value)
  }
})

onBeforeUnmount(() => {
  if (observer) {
    observer.disconnect()
  }
})
</script>

<style scoped>
/* 初始状态 */
.animate-fade-up:not(.visible) {
  opacity: 0;
  transform: translateY(30px);
  transition: all 0.6s ease;
}

.animate-slide-left:not(.visible) {
  opacity: 0;
  transform: translateX(-30px);
  transition: all 0.6s ease;
}

.animate-slide-right:not(.visible) {
  opacity: 0;
  transform: translateX(30px);
  transition: all 0.6s ease;
}

.animate-slide-up:not(.visible) {
  opacity: 0;
  transform: translateY(30px);
  transition: all 0.6s ease;
}

/* 动画完成状态 */
.animate-fade-up.visible,
.animate-slide-left.visible,
.animate-slide-right.visible,
.animate-slide-up.visible {
  opacity: 1;
  transform: translate(0);
}
</style>
