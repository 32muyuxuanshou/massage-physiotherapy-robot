<template>
  <section class="feature-carousel position-relative vh-100">
    <!-- 水平轮播图（仅图片轮播） -->
    <el-carousel
      ref="carouselRef"
      arrow="never"
      height="100%"
      indicator-position="none"
      direction="horizontal"
      :interval="5000"
      :autoplay="true"
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
      <div class="features-list d-flex gap-3 position-absolute w-100">
        <div
          v-for="(item, index) in featureItems"
          :key="index"
          class="feature-item flex-grow-1 text-center fw-bold fs-5"
          :class="{ active: currentIndex === index }"
          @click="switchToItem(index)"
        >
          <span class="feature-text d-block mb-3">{{ item.text }}</span>
        </div>
      </div>
      <div class="carousel-desc">
        <span class="d-block mb-3" :style="{ color: currentIndex === 0 ? '#fff' : '#000' }">{{
          featureItems[currentIndex]?.desc || ''
        }}</span>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue'

const carouselRef = ref(null)
const currentIndex = ref(0)

const featureItems = ref([
  {
    text: '穴位识别',
    img: 'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/competitiveness1.png',
    desc: '前沿视觉算法精准识别74个穴位，重构3D人体模型的同时确保每一次施力都准确无误。',
  },
  {
    text: '精准力控',
    img: 'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/competitiveness2.png',
    desc: '独特的力控算法赋予机器人末端柔顺特性，力控精度达0.1N，保障人体舒适与安全和谐相融。',
  },
  {
    text: '多元交互',
    img: 'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/competitiveness3.png',
    desc: '支持语音、Pad、小程序等交互方式，操控便捷，提供沉浸式的理疗体验。',
  },
  {
    text: '健康档案',
    img: 'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/competitiveness4.png',
    desc: '机器人可以根据用户的情况及理疗师建议定制个性化的理疗方案，并根据理疗数据和反馈建立个人健康档案。',
  },
  {
    text: '安全防护',
    img: 'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/competitiveness5.png',
    desc: '机器人通过国家CR认证，拥有独立RSC设计和双通道冗余监控，多重安全测试与应急处理满足完全人机安全交互标准。',
  },
])

// 处理轮播图变化
const handleCarouselChange = (index) => {
  currentIndex.value = index
}

// 添加切换到指定项的函数
const switchToItem = (index) => {
  // 更新当前索引
  currentIndex.value = index
  // 切换轮播图到对应项
  carouselRef.value.setActiveItem(index)
}
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

.features-list {
  bottom: 93px;
  left: 16px;
  position: absolute;
  justify-content: center;
}

.carousel-desc {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.feature-item {
  cursor: pointer;
  border-bottom: 2px solid #9f9f9f;
}
.feature-item.active:first-child {
  color: #fff;
  border-bottom: 2px solid #fff;
}
.feature-item.active {
  color: #000;
  position: relative;
  border-bottom: 2px solid #000;
}
.feature-item.active::before {
  content: '';
  position: absolute;
  bottom: -10px;
  left: 50%;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-left: 8px solid transparent;
  border-right: 8px solid transparent;
  border-top: 8px solid #000;
  display: block;
}
.feature-item:first-child.active::before {
  border-top-color: #fff;
}
.feature-item:not(.active) {
  color: #9f9f9f;
}
@media (max-width: 640px) {
  .feature-item.active::before {
    bottom: -8px;
  }
}
</style>
