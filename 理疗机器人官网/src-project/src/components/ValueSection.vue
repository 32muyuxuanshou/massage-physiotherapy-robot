<!-- ValueSection.vue -->
<template>
  <section class="value-section" id="value">
    <div class="container">
      <el-carousel
        ref="carouselRef"
        class="carousel"
        direction="vertical"
        :autoplay="false"
        @change="handleCarouselChange"
      >
        <!-- 商家价值 -->
        <el-carousel-item>
          <ValueCard
            :title="'商家价值'"
            :subtitle="'以科技力量，为行业带来深度变革'"
            :image-url="'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/merchants.png'"
            :features="businessFeatures"
          />
        </el-carousel-item>

        <!-- 用户价值 -->
        <el-carousel-item>
          <ValueCard
            :title="'用户价值'"
            :subtitle="'以细腻匠心，提供高品质理疗服务'"
            :image-url="'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/user.png'"
            :features="userFeatures"
          />
        </el-carousel-item>
      </el-carousel>
    </div>
  </section>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import ValueCard from './ValueCard.vue'

const carouselRef = ref(null)
const currentIndex = ref(0)

// 商家价值特征
const businessFeatures = [
  {
    icon: 'bi bi-activity',
    title: '探索1+N服务品项',
    description: '通用理疗机器人可适配多样的功能末端，为门店带来更丰富的品项和服务内容。',
  },
  {
    icon: 'bi bi-people',
    title: '节省30%人力成本',
    description: '人机结合的服务模型降低对资深理疗师的依赖，聚焦提供更多情绪价值。',
  },
  {
    icon: 'bi bi-speedometer',
    title: '提升70%服务效率',
    description: '1位理疗师搭配机器人可同时服务3位用户，提高门店服务效率实现降本增效。',
  },
  {
    icon: 'bi bi-shield-check',
    title: '保持100%服务标准',
    description: '24小时遵循标准化服务品质，降低因经验差异、情绪变化，体力波动等对理疗水平的影响。',
  },
]

// 用户价值特征
const userFeatures = [
  {
    icon: 'bi bi-layer-forward',
    title: '丰富理疗末端',
    description: '满足不同人群多样化理疗需求，提供更加贴心与全面的健康解决方案。',
  },
  {
    icon: 'bi bi-hand-thumbs-up',
    title: '专业理疗手法',
    description: '精准的视觉识别与精确的力控把握，带来深度且富有层次的疗愈体验。',
  },
  {
    icon: 'bi bi-heart-pulse',
    title: '舒心理疗体验',
    description: '通过模拟学习还原大师手法，并可自由调节力度、温度等，实现最优体验。',
  },
  {
    icon: 'bi bi-file-medical',
    title: '个性化健康报告',
    description: '收集用户反馈与喜好，建立个性化健康档案，以提供更贴心的服务。',
  },
]

// 处理轮播图变化
const handleCarouselChange = (index) => {
  currentIndex.value = index
}

// 处理鼠标滚轮事件
const handleWheel = (event) => {
  if (!carouselRef.value) return

  const carouselElement = carouselRef.value.$el
  const rect = carouselElement.getBoundingClientRect()

  // 只有当轮播图在屏幕中间区域时才拦截滚轮事件
  const windowHeight = window.innerHeight
  const elementCenter = rect.top + rect.height / 2
  const isInView = elementCenter > windowHeight * 0.25 && elementCenter < windowHeight * 0.75

  if (isInView) {
    // 检查是否在边界位置
    const isAtTop = currentIndex.value === 0 && event.deltaY < 0
    const isAtBottom = currentIndex.value === 1 && event.deltaY > 0

    if (!isAtTop && !isAtBottom) {
      event.preventDefault()

      setTimeout(() => {
        if (event.deltaY > 0) {
          // 向下滚动，切换到下一张
          if (currentIndex.value < 1) {
            carouselRef.value.setActiveItem(currentIndex.value + 1)
          }
        } else {
          // 向上滚动，切换到上一张
          if (currentIndex.value > 0) {
            carouselRef.value.setActiveItem(currentIndex.value - 1)
          }
        }
      }, 500)
    }
  }
}

onMounted(() => {
  window.addEventListener('wheel', handleWheel, { passive: false })
})

onBeforeUnmount(() => {
  window.removeEventListener('wheel', handleWheel)
})
</script>

<style scoped>
.value-section {
  padding: 100px 0;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}

.container {
  width: 100%;
  max-width: 100%;
  margin: 0 auto;
}

::v-deep(.el-carousel__container) {
  height: 100%;
}
/* 大屏幕（≥992px）使用50vh */
@media (min-width: 1200px) {
  .carousel {
    height: 60vh !important;
  }
}

@media (max-width: 1200px) {
  .value-section {
    padding: 50px 0;
  }
  .carousel {
    height: 100vh !important;
  }
}
</style>
