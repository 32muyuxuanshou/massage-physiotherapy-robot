<template>
  <section class="py-5 bg-light" id="services">
    <div class="container mt-5">
      <div style="margin: 0 auto">
        <div class="row mb-5">
          <div class="col text-center">
            <h2 class="display-5 fw-bold gradient-text">高效灵活 精准可靠</h2>
          </div>
        </div>

        <!-- 图标行 -->
        <div class="row justify-content-center g-5 mb-5" ref="iconRow">
          <!-- 开发图标 -->
          <div
            class="col-auto text-center animate__animated"
            :class="{ 'animate__animated animate__fadeInLeft': iconsVisible[1] }"
            :style="{ animationDelay: iconsVisible[1] ? '0.3s' : '0s' }"
          >
            <div class="icon-container">
              <svg
                t="1758874255755"
                class="icon"
                viewBox="0 0 1024 1024"
                version="1.1"
                xmlns="http://www.w3.org/2000/svg"
                p-id="4628"
                width="16"
                height="16"
              >
                <path
                  d="M256 512l81.6 108.8a32 32 0 0 1-51.2 38.4l-96-128a31.968 31.968 0 0 1 0-38.4l96-128a32 32 0 0 1 51.2 38.4L256 512z m414.4 108.8a32 32 0 0 0 51.2 38.4l96-128a31.968 31.968 0 0 0 0-38.4l-96-128a32 32 0 0 0-51.2 38.4L752 512l-81.6 108.8z m-167.168 26.144a32 32 0 1 1-62.464-13.888l64-288a32 32 0 1 1 62.464 13.888l-64 288z"
                  p-id="4629"
                  fill="#ff5a00"
                ></path>
                <path
                  d="M160 144a32 32 0 0 0-32 32v688a32 32 0 0 0 32 32h688a32 32 0 0 0 32-32V176a32 32 0 0 0-32-32H160z m0-64h688a96 96 0 0 1 96 96v688a96 96 0 0 1-96 96H160a96 96 0 0 1-96-96V176a96 96 0 0 1 96-96z"
                  p-id="4630"
                  fill="#ff5a00"
                ></path>
              </svg>
              <p class="mt-2 icon-label">开发</p>
            </div>
          </div>

          <!-- 数据图标 -->
          <div
            class="col-auto text-center animate__animated"
            :class="{ 'animate__animated animate__fadeInLeft': iconsVisible[2] }"
            :style="{ animationDelay: iconsVisible[2] ? '0.5s' : '0s' }"
          >
            <div class="icon-container">
              <svg
                t="1758874447377"
                class="icon"
                viewBox="0 0 1024 1024"
                version="1.1"
                xmlns="http://www.w3.org/2000/svg"
                p-id="11361"
                id="mx_n_1758874447377"
                width="16"
                height="16"
              >
                <path
                  d="M512 0C229.831111 0 0 229.831111 0 512S229.831111 1024 512 1024 1024 794.168889 1024 512 794.168889 0 512 0z m0 68.266667C741.831111 68.266667 932.977778 245.76 953.457778 471.04c-147.911111-63.715556-316.302222-9.102222-482.417778 43.235556-152.462222 47.786667-295.822222 93.297778-400.497778 38.684444-2.275556-13.653333-2.275556-27.306667-2.275555-40.96C68.266667 266.24 266.24 68.266667 512 68.266667z m0 887.466666c-202.524444 0-373.191111-136.533333-425.528889-320.853333 31.857778 9.102222 63.715556 13.653333 97.848889 13.653333 97.848889 0 204.8-34.133333 309.475556-68.266666 163.84-52.337778 332.231111-104.675556 461.937777-31.857778-20.48 227.555556-211.626667 407.324444-443.733333 407.324444z"
                  fill="#ff5a00"
                  p-id="11362"
                ></path>
              </svg>
              <p class="mt-2 icon-label">数据</p>
            </div>
          </div>

          <!-- 教育图标 -->
          <div
            class="col-auto text-center animate__animated"
            :class="{ 'animate__animated animate__fadeInLeft': iconsVisible[2] }"
            :style="{ animationDelay: iconsVisible[2] ? '0.5s' : '0s' }"
          >
            <div class="icon-container">
              <svg
                t="1758874554068"
                class="icon"
                viewBox="0 0 1120 1024"
                version="1.1"
                xmlns="http://www.w3.org/2000/svg"
                p-id="12624"
                width="16"
                height="16"
              >
                <path
                  d="M1081.372587 410.809524c24.821143-14.679773 39.220767-37.483848 39.220767-62.641169s-14.231536-47.961396-39.220767-62.641168l-455.801347-268.942405C588.311511-5.490907 532.281843-5.490907 494.854025 16.528752L39.220767 285.527187c-24.989232 14.679773-39.220767 37.483848-39.220767 62.641168s14.231536 47.961396 39.220767 62.641169l121.920557 72.054152 1.344712 365.98579a118.838925 118.838925 0 0 0 71.213708 108.585496A799.095121 799.095121 0 0 0 554.69371 1023.998207a778.812381 778.812381 0 0 0 343.181715-79.394039 95.250435 95.250435 0 0 0 53.004066-84.044502l2.913542-374.110091zM538.333047 90.207765a53.172155 53.172155 0 0 1 43.92726 0l437.031408 257.736471-437.031408 257.736472a53.172155 53.172155 0 0 1-43.92726 0L233.419596 426.161653a42.750636 42.750636 0 0 0-16.808901-10.029311L101.24561 348.168355z m326.877082 769.455427a8.852687 8.852687 0 0 1-4.818552 8.012242A684.906658 684.906658 0 0 1 554.69371 938.440904a713.593848 713.593848 0 0 1-286.815869-59.447477 33.281623 33.281623 0 0 1-19.666413-30.480139l-1.288682-315.054822 247.931279 146.629641a137.832983 137.832983 0 0 0 130.885304 0l241.992135-142.819623z"
                  p-id="12625"
                  fill="#ff5a00"
                ></path>
                <path
                  d="M1076.441976 453.672219a42.750636 42.750636 0 0 0-42.750636 42.750637v370.748311a42.806666 42.806666 0 0 0 85.557302 0V496.422856a42.806666 42.806666 0 0 0-42.806666-42.750637z"
                  p-id="12626"
                  fill="#ff5a00"
                ></path>
              </svg>
              <p class="mt-2 icon-label">教育</p>
            </div>
          </div>

          <!-- 赛事图标 -->
          <div
            class="col-auto text-center animate__animated"
            :class="{ 'animate__animated animate__fadeInLeft': iconsVisible[3] }"
            :style="{ animationDelay: iconsVisible[3] ? '0.7s' : '0s' }"
          >
            <div class="icon-container">
              <svg
                t="1758874586054"
                class="icon"
                viewBox="0 0 1024 1024"
                version="1.1"
                xmlns="http://www.w3.org/2000/svg"
                p-id="9298"
                width="16"
                height="16"
              >
                <path
                  d="M845.913043 489.73913c0 134.92313-221.540174 244.869565-311.652173 244.869566v89.043478h155.826087c19.322435 0 44.521739 21.414957 44.521739 44.521739v111.304348c0 17.830957-26.690783 44.521739-44.521739 44.521739H311.652174c-17.830957 0-44.521739-26.690783-44.521739-44.521739v-111.304348c0-22.105043 23.507478-44.521739 44.521739-44.521739h155.826087v-89.043478c-87.885913 0-289.391304-111.616-289.391304-244.869566-101.977043-7.301565-178.086957-75.642435-178.086957-178.086956V178.086957c0-44.655304 22.127304-89.043478 66.782609-89.043479h111.304348V66.782609c0-44.655304 22.127304-66.782609 66.782608-66.782609h534.26087c44.655304 0 66.782609 22.127304 66.782608 66.782609v22.260869h89.043479c44.655304 0 89.043478 48.350609 89.043478 93.005913V311.652174c0 102.934261-76.8 171.497739-178.086957 178.086956zM178.086957 155.826087H89.043478c-8.993391 0-22.26087 13.267478-22.260869 22.26087v133.565217c0 66.137043 47.304348 103.357217 111.304348 111.304348V155.826087z m178.086956 734.608696c-8.993391 0-22.26087 13.267478-22.26087 22.260869v22.26087s15.60487 20.769391 29.317566 20.769391c58.368 0 224.345043 1.491478 282.334608 1.491478 13.534609 0 22.26087-22.26087 22.26087-22.260869v-22.26087c0-8.993391-13.267478-22.26087-22.26087-22.260869H356.173913zM779.130435 89.043478c0-8.993391-7.279304-21.882435-22.26087-22.260869H267.130435c-8.993391 0-22.26087 13.267478-22.26087 22.260869v333.913044c0 160.990609 119.140174 236.944696 255.755131 236.944695C635.458783 659.901217 779.130435 583.94713 779.130435 422.956522V89.043478z m178.086956 89.043479c0-8.993391-13.245217-22.26087-22.260869-22.26087h-89.043479v267.130435c64.022261-7.94713 111.304348-45.167304 111.304348-111.304348V178.086957zM622.124522 407.618783l18.031304 110.235826a24.264348 24.264348 0 0 1-35.661913 25.110261l-92.93913-51.289044-92.939131 51.289044a24.219826 24.219826 0 1 1-35.617391-25.06574l18.031304-110.235826-76.132174-77.957565a24.175304 24.175304 0 0 1 13.668174-40.759652l104.269913-15.872 46.859131-99.59513a24.197565 24.197565 0 0 1 43.809391 0l46.814609 99.59513 104.269913 15.872a24.153043 24.153043 0 0 1 13.668174 40.71513l-76.132174 77.957566z m-61.818435-88.731826a24.064 24.064 0 0 1-18.231652-13.579131l-30.408348-64.712348-30.430609 64.712348a24.130783 24.130783 0 0 1-18.231652 13.579131l-70.500174 10.77426 51.801044 52.958609c5.36487 5.498435 7.813565 13.200696 6.566956 20.747131l-11.976348 73.149217 61.017044-33.658435a24.130783 24.130783 0 0 1 23.440695 0l61.017044 33.658435-11.976348-73.149217a24.041739 24.041739 0 0 1 6.566957-20.747131l51.823304-52.958609-70.477913-10.77426z"
                  fill="#ff5a00"
                  p-id="9299"
                ></path>
              </svg>
              <p class="mt-2 icon-label">赛事</p>
            </div>
          </div>
        </div>
        <div class="row justify-content-center mb-5 mt-5">
          <div
            class="col-auto text-center"
            :class="{ 'animate__animated animate__fadeInLeft': iconsVisible[3] }"
            :style="{ animationDelay: iconsVisible[3] ? '0.7s' : '0s' }"
          >
            <h2 class="display-5 fw-bold color-text">双重灵活选择</h2>
          </div>
        </div>
        <div class="row justify-content-between text-center">
          <div class="col-md-6">
            <h2 class="color-text">灵活流畅</h2>
            <h4 class="fs-5 fw-bold">A1 X</h4>
            <p class="fs-5">末端球形关节，模拟人类手腕的灵活性</p>
            <p class="fs-5">数据采集高效，操作轨迹流畅。</p>
            <img
              src="https://galaxea-ai.com/_next/image?url=%2Fimages%2Fproducts%2FA1XY%2Fcolorful_arm_left.png&w=3840&q=75"
              class="img-fluid"
              alt="robot2"
            />
          </div>
          <div class="col-md-6">
            <h2 class="color-text">紧凑轻巧</h2>
            <h4 class="fw-bold">A1 Y</h4>
            <p class="fs-5">末端紧凑轻巧，低惯量设计</p>
            <p class="fs-5">操作范围广，狭窄空间轻松穿越。</p>
            <img
              src="https://galaxea-ai.com/_next/image?url=%2Fimages%2Fproducts%2FA1XY%2Fcolorful_arm_right.png&w=3840&q=75"
              class="img-fluid"
              alt="robot2"
            />
          </div>
        </div>
        <div class="row justify-content-between align-items-center mt-5">
          <!-- 左侧标题 -->
          <div class="col-md-6 text-center">
            <div class="fs-2 fw-bold">了解一下 A1XY</div>
          </div>

          <!-- 右侧数字列表 -->
          <div class="col-md-6 d-flex flex-wrap justify-content-center">
            <!-- 第一行 -->
            <div class="text-center w-50" style="min-width: 120px">
              <div class="fs-3 fw-bold text-desc">6</div>
              <div class="small text-muted">独立自由度</div>
            </div>

            <div class="text-center w-50" style="min-width: 120px">
              <div class="fs-3 fw-bold text-desc">4.2 KG</div>
              <div class="small text-muted">机械臂自重</div>
            </div>

            <!-- 第二行 -->
            <div class="text-center w-50 mt-5" style="min-width: 120px">
              <div class="fs-3 fw-bold text-desc">5 KG</div>
              <div class="small text-muted">最大负载</div>
            </div>

            <div class="text-center w-50 mt-5" style="min-width: 120px">
              <div class="fs-3 fw-bold text-desc">0.1 mm</div>
              <div class="small text-muted">重复定位精度</div>
            </div>
          </div>
        </div>
        <div class="row justify-content-around align-items-center mt-5 mb-5">
          <div class="col-md-5 card text-center h-100 p-0 card-animation">
            <img
              src="https://galaxea-ai.com/_next/image?url=%2Fimages%2Fproducts%2FA1XY%2Fcontrol.png&w=1080&q=75"
              class="card-img-top"
              alt=""
            />
            <div class="card-body">
              <h5 class="card-title">高精度控制</h5>
              <p class="card-text small">
                重复定位精度±0.1mm， 在复杂轨迹运动中保持毫秒级响应稳定性。 （以实际测量为准）
              </p>
            </div>
          </div>
          <div class="col-md-5 card text-center h-100 p-0 card-position card-animation">
            <img
              src="https://galaxea-ai.com/_next/image?url=%2Fimages%2Fproducts%2FA1XY%2Flight_design.png&w=1080&q=75"
              class="card-img-top"
              alt=""
            />
            <div class="card-body">
              <h5 class="card-title">高精度控制</h5>
              <p class="card-text small">
                重复定位精度±0.1mm， 在复杂轨迹运动中保持毫秒级响应稳定性。 （以实际测量为准）
              </p>
            </div>
          </div>
        </div>
        <div
          class="row justify-content-around align-items-stretch mb-5 gy-4"
          style="margin-top: 6em"
        >
          <div class="col-md-3 d-flex justify-content-center p-0">
            <div class="card w-100 border-0 card-animation">
              <div class="card-body d-flex flex-column justify-content-center p-4 card-container">
                <h5 class="card-title fw-bold">开放生态</h5>
                <p class="card-text small text-muted">
                  支持快速转换多种末端执行器，满足不同场景下的多样化需求。
                </p>
              </div>
            </div>
          </div>

          <div class="col-md-7 d-flex justify-content-center p-0">
            <div class="card w-100 border-0 card-animation">
              <img
                src="https://galaxea-ai.com/_next/image?url=%2Fimages%2Fproducts%2FA1XY%2Fmultipy_color.png&w=1080&q=75"
                class="card-img-top w-100 object-fit-cover"
                alt="多色机械臂"
              />
              <div class="card-body d-flex flex-column justify-content-center p-4 card-container">
                <h5 class="card-title fw-bold">定制专属个性</h5>
                <p class="card-text small text-muted">支持多配色DIY，打造独一无二的专属风格。</p>
              </div>
            </div>
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
import ProductParams from './ProductParams.vue'

// 图标动画相关
const iconRow = ref(null)
const iconsVisible = ref([false, false, false, false])
let observer = null
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
// 初始化滚动动画
const initScrollAnimation = () => {
  // 创建交叉观察器
  observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          // 元素进入视口时触发动画
          iconsVisible.value = [true, true, true, true]
          // 停止观察
          observer.unobserve(entry.target)
        }
      })
    },
    {
      threshold: 0.3, // 当30%的元素可见时触发，提高触发灵敏度
      rootMargin: '0px 0px -50px 0px', // 底部提前50px触发
    }
  )

  // 开始观察图标行
  if (iconRow.value) {
    observer.observe(iconRow.value)
  }
}

onMounted(() => {
  // 使用 setTimeout 确保 DOM 已完全渲染
  setTimeout(() => {
    initScrollAnimation()
  }, 100)
})

onBeforeUnmount(() => {
  // 清理观察器
  if (observer) {
    observer.disconnect()
  }
})
</script>

<style scoped>
/* 确保初始状态隐藏元素 */
.col-auto {
  opacity: 0;
  transform: translateX(-20px);
}

/* 动画类 */
.animate__fadeInLeft {
  animation: fadeInLeft 0.6s ease-out forwards;
}

@keyframes fadeInLeft {
  from {
    opacity: 0;
    transform: translateX(-20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}
/* 渐变色文本样式 */
.gradient-text {
  background: linear-gradient(90deg, #ff5a00 20.61%, #fff);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  font-weight: bold;
  letter-spacing: 1px;
}

.color-text {
  background: #ff5a00;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  font-weight: bold;
  letter-spacing: 1px;
}
.text-desc {
  color: #689ab6;
}

/* 图标容器样式 */
.icon-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 1.5rem;
  border-radius: 10px;
  transition: transform 0.3s ease;
}

.icon-container:hover {
  transform: translateY(-5px);
}

/* 图标标签样式 */
.icon-label {
  color: #333;
  font-weight: 500;
  margin-bottom: 0;
  font-size: 1rem;
}

/* SVG图标样式 */
svg {
  width: 60px;
  height: 60px;
  margin-bottom: 0.5rem;
}
/* 确保初始状态隐藏元素 */
.animate__animated {
  opacity: 0;
}

/* 动画完成后显示元素 */
.animate__fadeInLeft {
  animation-name: fadeInLeft;
  animation-duration: 0.6s;
  animation-fill-mode: both;
}

/* 如果需要，可以调整动画延迟 */
.col-auto {
  animation-delay: calc(var(--item-index) * 0.2s);
}

.card-position {
  position: relative;
  top: 2rem;
}
.card-img-top {
  height: 300px;
  object-fit: cover;
  width: 100%;
}
.card-animation {
  border-radius: 25px;
  /* 添加阴影 */
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
  /* 添加过渡效果 */
  transition: transform 0.3s ease;
  overflow: hidden;
}

.card-animation:hover {
  transform: translateY(-10px);
}
.card-container {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 100%;
}
.row-style {
  display: flex;
  height: 100%;
}

/* 响应式调整 */
@media (max-width: 768px) {
  .gradient-text {
    font-size: 2rem;
  }

  .icon-container {
    padding: 1rem;
  }

  .icon-label {
    font-size: 0.9rem;
  }
}
</style>
