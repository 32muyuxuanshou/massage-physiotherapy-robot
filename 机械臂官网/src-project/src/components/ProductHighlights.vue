<!-- src/components/ProductHighlights.vue -->
<template>
  <section class="py-5 bg-light" id="services">
    <div class="container mt-5">
      <div style="margin: 0 auto">
        <div class="row mb-5">
          <div class="col text-center">
            <h2 class="display-5 fw-bold">产品亮点</h2>
          </div>
        </div>

        <!-- 产品亮点卡片 -->
        <div class="row d-flex flex-wrap justify-content-center" ref="iconRow">
          <div
            v-for="(item, index) in highlights"
            :key="index"
            class="col-lg-3 col-md-6 mb-4 product-card"
          >
            <HighlightCard
              :value="item.value"
              :label="item.label"
              :class="{
                'animate-fade-in': iconsVisible,
                'animation-delay-1': index === 1,
                'animation-delay-2': index === 2,
                'animation-delay-3': index === 3,
              }"
            />
          </div>
        </div>
        <div class="row mb-5 mt-5">
          <div class="col text-center">
            <h2 class="fs-2 gradient-text" :class="{ 'text-animate-fade-in': textVisible }">
              仿人形设计、极具安全性和灵活性
            </h2>
          </div>
        </div>
        <div class="row mb-5 align-items-center justify-content-center gap-5" ref="dynamicSection">
          <div
            class="col-md-3 d-flex align-items-center justify-content-center robot-image"
            :class="{ 'animate-slide-up': dynamicImageVisible }"
          >
            <img src="@/assets/images/robot_arm_1.png" alt="robot" class="img-fluid" />
          </div>
          <div class="col-md-4 robot-text" :class="{ 'animate-slide-left': dynamicTextVisible }">
            <div class="fs-3 fw-bold">解锁高动态</div>
            <div class="fs-5 text-muted">最大线速度10m/s，末端最大加速度40m/s²</div>
          </div>
        </div>

        <div class="row mb-5 align-items-center justify-content-center gap-5" ref="payloadSection">
          <div class="col-md-4 robot-text" :class="{ 'animate-slide-left': payloadTextVisible }">
            <div class="fs-3 fw-bold">实现大负载</div>
            <div class="fs-5 text-muted">额定负载3kg，峰值负载高达5kg</div>
          </div>
          <div
            class="col-md-3 d-flex align-items-center justify-content-center robot-image"
            :class="{ 'animate-slide-up': payloadImageVisible }"
          >
            <img src="@/assets/images/robot_arm_2.png" alt="robot" class="img-fluid" />
          </div>
        </div>
        <div class="row justify-content-center text-center mb-5 gy-4" style="margin-top: 6em">
          <div class="display-5 fw-bold">产品参数</div>
        </div>

        <ProductParams :params="params" />
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import HighlightCard from './HighlightCard.vue'
import ProductParams from './ProductParams.vue'

// 图标动画相关
const iconRow = ref(null)
const iconsVisible = ref(false)
const textVisible = ref(false)
const dynamicSection = ref(null)
const payloadSection = ref(null)
const dynamicImageVisible = ref(false)
const dynamicTextVisible = ref(false)
const payloadTextVisible = ref(false)
const payloadImageVisible = ref(false)

// 产品亮点数据
const highlights = [
  { value: '6', label: '独立自由度' },
  { value: '677mm', label: '有效执行半径' },
  { value: '3 KG', label: '额定负载' },
  { value: '2 mm', label: '重复定位精度' },
]

const params = [
  { name: '产品型号', x: 'J-Arm' },
  { name: '本体重量', x: '2.5KG' },
  { name: '重复定位精度', x: '0.02mm' },
  { name: '供电电压', x: '48V' },
  { name: '通讯方式', x: 'CAN2.0' },
  { name: '额定负载', x: '3KG' },
  { name: '自由度', x: '6' },
  { name: '有效执行半径', x: '677mm' },
  { name: '通信频率', x: '500hz' },
  { name: '控制器', x: 'PC工控机' },
  { name: '材质', x: '铝合金' },
]
let observer = null
let dynamicObserver = null
let payloadObserver = null

// 初始化滚动动画
const initScrollAnimation = () => {
  observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          // 所有元素同时开始动画，通过CSS延迟实现 staggered 效果
          iconsVisible.value = true

          // 计算最后一个卡片动画完成的时间
          // 动画持续时间: 0.8s
          // 最大延迟: 0.4s
          // 总时间: 0.8s + 0.4s = 1.2s
          setTimeout(() => {
            textVisible.value = true
          }, 500) // 1.2秒后显示文本

          observer.unobserve(entry.target)
        }
      })
    },
    {
      threshold: 0.3,
      rootMargin: '0px 0px -50px 0px',
    }
  )

  if (iconRow.value) {
    observer.observe(iconRow.value)
  }
  // 添加对新元素的观察
  if (dynamicSection.value) {
    dynamicObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            dynamicImageVisible.value = true
            setTimeout(() => {
              dynamicTextVisible.value = true
            }, 200)
            dynamicObserver.unobserve(entry.target)
          }
        })
      },
      {
        threshold: 0.3,
        rootMargin: '0px 0px -50px 0px',
      }
    )
    dynamicObserver.observe(dynamicSection.value)
  }

  if (payloadSection.value) {
    payloadObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            payloadTextVisible.value = true
            setTimeout(() => {
              payloadImageVisible.value = true
            }, 200)
            payloadObserver.unobserve(entry.target)
          }
        })
      },
      {
        threshold: 0.3,
        rootMargin: '0px 0px -50px 0px',
      }
    )
    payloadObserver.observe(payloadSection.value)
  }
}

onMounted(() => {
  setTimeout(() => {
    initScrollAnimation()
  }, 100)
})

onBeforeUnmount(() => {
  if (observer) {
    observer.disconnect()
  }
  if (dynamicObserver) {
    dynamicObserver.disconnect()
  }
  if (payloadObserver) {
    payloadObserver.disconnect()
  }
})
</script>

<style scoped>
.animate-fade-in {
  opacity: 1;
  transform: translateY(0);
}

.text-animate-fade-in {
  opacity: 1;
  transform: translateY(0);
}

/* 基础动画样式 */
.product-card > :not(.animate-fade-in) {
  opacity: 0;
  transform: translateY(30px);
  transition: all 0.8s ease;
}

/* 文本动画初始状态 */
.gradient-text {
  opacity: 0;
  transform: translateY(30px);
  transition: all 0.3s ease;
  color: #ff5a00;
  letter-spacing: 1px;
}

/* 文本动画完成状态 */
.gradient-text.text-animate-fade-in {
  opacity: 1;
  transform: translateY(0);
}

/* 延迟动画类 */
.animation-delay-1 {
  transition-delay: 0.2s;
}

.animation-delay-2 {
  transition-delay: 0.3s;
}

.animation-delay-3 {
  transition-delay: 0.4s;
}
.img-fluid {
  width: 100%;
  height: auto;
}
/* 图片从下往上淡入动画 */
.animate-slide-up {
  opacity: 1;
  transform: translateY(0);
  transition: all 0.6s ease;
}

/* 文字从左往右淡入动画 */
.animate-slide-left {
  opacity: 1;
  transform: translateX(0);
  transition: all 0.6s ease;
}

/* 图片初始状态 */
.robot-image:not(.animate-slide-up) {
  opacity: 0;
  transform: translateY(30px);
}

.robot-text:not(.animate-slide-left) {
  opacity: 0;
  transform: translateX(-30px);
}

.robot-image,
.robot-text {
  transition: all 0.6s ease;
}
</style>
