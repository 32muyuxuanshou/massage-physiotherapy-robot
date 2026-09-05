<template>
  <nav
    class="navbar navbar-expand-lg navbar-dark fixed-top transition-colors duration-300 ease-in-out"
    :class="{ 'bg-dark-animate': !isTop || isHover || isMenuOpen }"
    @mouseenter="isHover = true"
    @mouseleave="isHover = false"
  >
    <div class="container">
      <button
        class="navbar-toggler"
        type="button"
        data-bs-toggle="collapse"
        data-bs-target="#navbarNav"
        @click="toggleMenu"
      >
        <span class="navbar-toggler-icon"></span>
      </button>
      <div class="collapse navbar-collapse" id="navbarNav">
        <ul class="navbar-nav ms-auto">
          <li
            class="nav-item me-4"
            v-for="item in navItems"
            :key="item.name"
            @mouseenter="openDropdown(item.name)"
            @mouseleave="scheduleCloseDropdown()"
          >
            <a
              class="nav-link"
              :class="{ active: item.link === currentPath }"
              @click="navigateTo(item.link)"
              :href="item.link"
            >
              {{ item.name }}
            </a>
          </li>
          <!-- 在小屏幕的折叠菜单中显示联系我们 -->
          <li class="nav-item me-4 d-lg-none">
            <a class="nav-link" :class="{ active: '#contact' === currentPath }" href="#contact">
              联系我们
            </a>
          </li>
        </ul>
      </div>

      <a class="navbar-brand" href="#"> <i class="bi bi-building me-2"></i>颐本科技 </a>

      <!-- 在大屏幕上显示联系我们 -->
      <div class="navbar-collapse d-none d-lg-block">
        <ul class="navbar-nav ms-auto">
          <li class="nav-item me-4">
            <a
              class="nav-link contact-link"
              :class="{ active: '#contact' === currentPath }"
              href="#contact"
            >
              联系我们
            </a>
          </li>
        </ul>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
// 导航数据（移除 active 字段）
const navItems = ref([
  {
    name: '价值',
    link: '#value',
  },
  {
    name: '产品',
    link: '#products',
  },
  {
    name: '场景',
    link: '#scenarios',
  },
])

// 计算当前路径
const currentPath = computed(() => window.location.pathname)

// 其他逻辑保持不变...
const isTop = ref(true)
const isHover = ref(false)
const closeTimeout = ref(null)
const isMenuOpen = ref(false)

const toggleMenu = () => {
  isMenuOpen.value = !isMenuOpen.value
}
const navigateTo = (path) => {
  // 如果是锚点链接，则滚动到对应位置
  if (path.startsWith('#')) {
    const targetElement = document.querySelector(path)
    if (targetElement) {
      targetElement.scrollIntoView({
        behavior: 'smooth',
      })
    }
  } else {
    // 保持原有的页面跳转功能
    window.location.href = path
  }
}

const handleScroll = () => {
  isTop.value = window.scrollY === 0
}

onMounted(() => {
  window.addEventListener('scroll', handleScroll)
  handleScroll()
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', handleScroll)
  if (closeTimeout.value) {
    clearTimeout(closeTimeout.value)
  }
})
</script>

<style scoped>
.navbar-brand {
  font-weight: bold;
  font-size: 1.5rem;
  flex: 1;
  text-align: center;
}
.navbar-collapse {
  flex-grow: 0;
}
/* 添加过渡动画的背景色 */
.navbar {
  background-color: transparent !important;
  z-index: 1030;
}

.navbar.bg-dark-animate {
  background-color: #1a1a1a66 !important;
}

/* 确保过渡效果应用于背景色 */
.transition-colors {
  transition-property: background-color, border-color, color, fill, stroke;
  transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  transition-duration: 300ms;
}

.duration-300 {
  transition-duration: 300ms;
}

.ease-in-out {
  transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
}

.contact-link {
  background-color: #ff5a00;
  color: #fff;
  border-radius: 5px;
  width: 100px;
  text-align: center;
}

/* 在小屏幕上隐藏下拉菜单 */
@media (max-width: 991.98px) {
  .fullscreen-dropdown {
    display: none !important;
  }
}
</style>
