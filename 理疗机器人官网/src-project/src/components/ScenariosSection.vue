<template>
  <section class="position-relative vh-100" id="scenarios">
    <div class="py-5">
      <div class="text-center mb-5">
        <h2 class="fs-1 fw-bold">丰富的应用场景</h2>
        <p class="text-muted fs-6">覆盖多类应用场景，提供多样功能服务，满足多种理疗需求。</p>
      </div>

      <!-- 第一行：从右往左滚动 -->
      <div class="carousel-container d-flex overflow-hidden">
        <div class="carousel-track">
          <div v-for="item in firstRowItems" :key="item.id" class="carousel-items">
            <img :src="item.src" :alt="item.label" class="img-fluid rounded" />
            <div class="carousel-label">{{ item.label }}</div>
          </div>
        </div>
      </div>

      <!-- 第二行：从左往右滚动 -->
      <div class="carousel-container d-flex overflow-hidden">
        <div class="carousel-track reverse">
          <div v-for="item in secondRowItems" :key="item.id" class="carousel-items">
            <img :src="item.src" :alt="item.label" class="img-fluid rounded" />
            <div class="carousel-label">{{ item.label }}</div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
const firstRowItems = [
  {
    id: 1,
    src: 'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/scenes4.png',
    label: '美容院',
  },
  {
    id: 2,
    src: 'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/scenes1.png',
    label: '健身房',
  },
  {
    id: 3,
    src: 'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/scenes2.png',
    label: '理疗室',
  },
  {
    id: 4,
    src: 'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/scenes3.png',
    label: '中医馆',
  },
  // 重复第一组以实现无缝衔接
  {
    id: 5,
    src: 'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/scenes4.png',
    label: '美容院',
  },
  {
    id: 6,
    src: 'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/scenes1.png',
    label: '健身房',
  },
  {
    id: 7,
    src: 'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/scenes2.png',
    label: '理疗室',
  },
  {
    id: 8,
    src: 'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/scenes3.png',
    label: '中医馆',
  },
]

const secondRowItems = [
  {
    id: 1,
    src: 'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/scenes8.png',
    label: '智慧社区',
  },
  {
    id: 2,
    src: 'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/scenes5.png',
    label: '康养酒店',
  },
  {
    id: 3,
    src: 'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/scenes6.png',
    label: '养老院',
  },
  {
    id: 4,
    src: 'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/scenes7.png',
    label: '运动康复中心',
  },
  // 重复第二组以实现无缝衔接
  {
    id: 5,
    src: 'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/scenes8.png',
    label: '智慧社区',
  },
  {
    id: 6,
    src: 'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/scenes5.png',
    label: '康养酒店',
  },
  {
    id: 7,
    src: 'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/scenes6.png',
    label: '养老院',
  },
  {
    id: 8,
    src: 'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/scenes7.png',
    label: '运动康复中心',
  },
]
</script>

<style scoped>
.carousel-container {
  width: 100%;
  height: 300px;
  position: relative;
  overflow: hidden;
}

.carousel-track {
  display: flex;
  height: 100%;
  animation: scroll-left 40s linear infinite;
  will-change: transform;
}

.carousel-track.reverse {
  animation: scroll-right 40s linear infinite;
}

/* 关键修改：使用固定的像素宽度而不是百分比 */
.carousel-items {
  flex: 0 0 380px; /* 固定宽度，确保3.5张图片正好填满屏幕 */
  height: 250px;
  position: relative;
  overflow: hidden;
  border-radius: 8px;
  margin-right: 24px; /* 固定的间距 */
  flex-shrink: 0;
}

/* 精确的动画计算：移动4张图片的宽度（因为重复了4个唯一项目） */
@keyframes scroll-left {
  0% {
    transform: translateX(0);
  }
  100% {
    /* 移动距离 = 4张图片 × (图片宽度 + 间距) */
    transform: translateX(calc(-4 * (380px + 24px)));
  }
}

@keyframes scroll-right {
  0% {
    transform: translateX(calc(-4 * (380px + 24px)));
  }
  100% {
    transform: translateX(0);
  }
}

.carousel-items img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.carousel-label {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background-color: rgba(0, 0, 0, 0.5);
  color: white;
  padding: 8px;
  text-align: center;
  font-size: 0.9rem;
  opacity: 0.9;
}

/* 响应式调整 */
@media (max-width: 1200px) {
  .carousel-items {
    flex: 0 0 320px;
  }

  @keyframes scroll-left {
    0% {
      transform: translateX(0);
    }
    100% {
      transform: translateX(calc(-4 * (320px + 24px)));
    }
  }

  @keyframes scroll-right {
    0% {
      transform: translateX(calc(-4 * (320px + 24px)));
    }
    100% {
      transform: translateX(0);
    }
  }
}

@media (max-width: 768px) {
  .carousel-items {
    flex: 0 0 280px;
  }

  @keyframes scroll-left {
    0% {
      transform: translateX(0);
    }
    100% {
      transform: translateX(calc(-4 * (280px + 16px)));
    }
  }

  @keyframes scroll-right {
    0% {
      transform: translateX(calc(-4 * (280px + 16px)));
    }
    100% {
      transform: translateX(0);
    }
  }
}
</style>
