<template>
  <section class="feature-carousel position-relative vh-100" id="products">
    <!-- 水平轮播图（仅图片轮播） -->
    <el-carousel
      ref="carouselRef"
      arrow="never"
      indicator-position="none"
      height="100%"
      direction="horizontal"
      :autoplay="false"
      @change="handleCarouselChange"
      class="horizontal-carousel w-100"
    >
      <el-carousel-item v-for="(item, index) in featureItems" :key="index">
        <div class="image-container h-100 w-100">
          <img class="image h-100 w-100 object-fit-cover" :src="item.img" :alt="item.text" />
        </div>
      </el-carousel-item>
    </el-carousel>

    <!-- 固定的文字内容 -->
    <div
      class="content-wrapper container position-absolute top-0 start-50 translate-middle-x w-100"
    >
      <div class="top-wrapper">
        <h2 class="display-5 mb-4 fw-bold">功能丰富</h2>
        <p class="display-5">轻松适配各类理疗场景</p>
        <p class="fs-5 text-muted mb-5">
          适配按摩、艾灸、磁震波、内源热能、筋膜再生宝等理疗末端，
          切换自如，满足特定应用场景同时提供个性化服务，让用户拥有别致体验。
        </p>
      </div>
      <div class="features-list d-flex flex-column gap-2 position-absolute">
        <div
          v-for="(item, index) in featureItems"
          :key="index"
          class="feature-item"
          :class="{ active: currentIndex === index }"
          @click="switchToItem(index)"
          style="cursor: pointer"
        >
          <span class="feature-text d-block mb-3">{{ item.text }}</span>
          <el-progress
            :stroke-width="5"
            :percentage="getProgressPercentage(index)"
            :show-text="false"
            :color="currentIndex === index ? '#000' : '#ccc'"
          />
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const carouselRef = ref(null)
const currentIndex = ref(0)
const progress = ref(0)
let timer = null

const featureItems = ref([
  {
    text: '按摩',
    img: 'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/shockwave.png',
  },
  {
    text: '磁震波',
    img: 'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/massage.png',
  },
  {
    text: '矩阵艾灸',
    img: 'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/aijiu.png',
  },
  {
    text: '射频',
    img: 'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/rf.png',
  },
  {
    text: '内源热能',
    img: 'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/hotstone.png',
  },
  {
    text: '筋膜再生宝',
    img: 'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/massage.png',
  },
])

// 计算进度条百分比
const getProgressPercentage = (index) => {
  if (index === currentIndex.value) {
    return progress.value
  } else if (index < currentIndex.value) {
    return 0
  } else {
    return 0
  }
}

// 处理轮播图变化
const handleCarouselChange = (index) => {
  currentIndex.value = index
}

// 添加切换到指定项的函数
const switchToItem = (index) => {
  // 更新当前索引
  currentIndex.value = index
  // 重置进度条
  progress.value = 0
  // 切换轮播图到对应项
  carouselRef.value.setActiveItem(index)
  // 重启定时器以保持同步
  startTimer()
}
// 启动定时器
const startTimer = () => {
  // 先清理现有的定时器
  if (timer) {
    clearInterval(timer.progressTimer)
    clearInterval(timer.switchTimer)
  }

  let progressTimer = null
  let switchTimer = null

  progressTimer = setInterval(() => {
    if (progress.value < 100) {
      progress.value += 1
    }
  }, 50) // 100 * 50ms = 5000ms 到达100%

  switchTimer = setInterval(() => {
    if (progress.value >= 100) {
      progress.value = 0
      currentIndex.value = (currentIndex.value + 1) % featureItems.value.length
      carouselRef.value.setActiveItem(currentIndex.value)
    }
  }, 5500) // 每5.5秒切换一次图片 确保有足够时间看到100%

  // 保存定时器引用以便清理
  timer = {
    progressTimer,
    switchTimer,
  }
}

onMounted(() => {
  startTimer()
})

onBeforeUnmount(() => {
  if (timer) {
    clearInterval(timer.progressTimer)
    clearInterval(timer.switchTimer)
  }
})
</script>

<style scoped>
.feature-carousel {
  position: relative;
}
.horizontal-carousel {
  width: 100%;
  height: 100vh;
}
.container {
  width: 100%;
  margin: 0 auto;
  position: relative;
  display: flex;
  flex-direction: column;
}
.content-wrapper {
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 100%;
  height: 100%;
}
.image-container {
  height: 100%;
  width: 100%;
}
.image {
  height: 100%;
  width: 100%;
}
.top-wrapper {
  padding-top: 5%;
  width: 50%;
}
.features-list {
  width: 200px;
  flex-direction: column;
  bottom: 10%;
  left: 16px;
  position: absolute;
  justify-content: center;
}

.feature-item {
  cursor: pointer;
}
.feature-item.active {
  color: #000;
}

.feature-item:not(.active) {
  color: #ccc;
}
@media screen and (max-width: 990px) {
  .top-wrapper {
    width: 80%;
    padding-top: 5%;
  }
  .features-list {
    bottom: 5%;
  }
}
</style>
