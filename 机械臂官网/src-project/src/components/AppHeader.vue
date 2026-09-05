<template>
  <nav
    class="navbar navbar-expand-lg navbar-dark fixed-top transition-colors duration-300 ease-in-out"
    :class="{ 'bg-dark-animate': !isTop || isHover || isMenuOpen }"
    @mouseenter="isHover = true"
    @mouseleave="isHover = false"
  >
    <div class="container">
      <a class="navbar-brand" href="#"> <i class="bi bi-building me-2"></i>公司名称 </a>
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

            <!-- 下拉菜单 -->
            <div
              v-if="item.subItems && item.subItems.length > 0"
              class="dropdown-menu fullscreen-dropdown"
              :class="{
                show: activeDropdown === item.name,
                'animate-show': activeDropdown === item.name,
                'animate-hide': activeDropdown !== item.name && transitioning,
              }"
              @mouseenter="cancelCloseDropdown()"
              @mouseleave="closeDropdown()"
            >
              <div class="container">
                <div class="row">
                  <div class="col-12">
                    <div class="dropdown-content">
                      <div
                        class="dropdown-item-container"
                        v-for="subItem in item.subItems"
                        :key="subItem.name"
                      >
                        <a
                          :href="subItem.link"
                          class="dropdown-item"
                          @click="subItem.action ? subItem.action() : navigateTo(subItem.link)"
                        >
                          <h6 v-if="subItem.title" class="dropdown-title">{{ subItem.title }}</h6>
                          <span>{{ subItem.name }}</span>
                          <p v-if="subItem.description" class="dropdown-description">
                            {{ subItem.description }}
                          </p>
                        </a>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </li>
          <li class="nav-item me-4">
            <a
              class="nav-link contact-link"
              :class="{ active: '/contact' === currentPath }"
              href="/contact"
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
    name: '机械臂',
    link: '/',
    subItems: [
      // {
      //   name: '工业机械臂',
      //   link: '/industrial-arm',
      //   title: '产品系列',
      //   description: '适用于重工业环境的高精度机械臂',
      // },
      // {
      //   name: '服务机械臂',
      //   link: '/service-arm',
      //   title: '产品系列',
      //   description: '面向商业服务场景的灵活机械臂',
      // },
      // {
      //   name: '教育机械臂',
      //   link: '/education-arm',
      //   title: '产品系列',
      //   description: '专为教学和研究设计的入门级机械臂',
      // },
    ],
  },
  // {
  //   name: '机器人',
  //   link: '/robots',
  //   subItems: [
  //     {
  //       name: '移动机器人',
  //       link: '/mobile-robots',
  //       title: '自主导航',
  //       description: '具备自主导航能力的智能移动机器人',
  //     },
  //     {
  //       name: '人形机器人',
  //       link: '/humanoid-robots',
  //       title: '仿生设计',
  //       description: '高度仿生的人形机器人解决方案',
  //     },
  //   ],
  // },
  // { name: '文档中心', link: '/services' },
  // { name: '开源社区', link: '/team' },
  // { name: '关于我们', link: '/about' },
  // { name: '服务与支持', link: '/support' },
])

// 计算当前路径
const currentPath = computed(() => window.location.pathname)

// 其他逻辑保持不变...
const isTop = ref(true)
const isHover = ref(false)
const activeDropdown = ref('')
const transitioning = ref(false)
const closeTimeout = ref(null)
const isMenuOpen = ref(false)

const toggleMenu = () => {
  isMenuOpen.value = !isMenuOpen.value
}

const openDropdown = (itemName) => {
  if (closeTimeout.value) {
    clearTimeout(closeTimeout.value)
    closeTimeout.value = null
  }
  transitioning.value = true
  activeDropdown.value = itemName
}

const scheduleCloseDropdown = () => {
  closeTimeout.value = setTimeout(() => {
    closeDropdown()
  }, 300)
}

const cancelCloseDropdown = () => {
  if (closeTimeout.value) {
    clearTimeout(closeTimeout.value)
    closeTimeout.value = null
  }
}

const closeDropdown = () => {
  if (closeTimeout.value) {
    clearTimeout(closeTimeout.value)
    closeTimeout.value = null
  }
  transitioning.value = true
  activeDropdown.value = ''
  setTimeout(() => {
    transitioning.value = false
  }, 300)
}

const navigateTo = (path) => {
  window.location.href = path
}

const handleScroll = () => {
  isTop.value = window.scrollY === 0
  if (window.scrollY > 0) {
    closeDropdown()
  }
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
}

/* 添加过渡动画的背景色 */
.navbar {
  background-color: transparent !important;
  z-index: 1030;
}

.navbar.bg-dark-animate {
  background-color: #272727 !important;
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

/* 全屏下拉菜单样式 */
.fullscreen-dropdown {
  position: fixed;
  top: 100%;
  left: 0;
  width: 100vw;
  background-color: #272727;
  border: none;
  border-radius: 0;
  margin-top: 0;
  padding: 20px 0;
  z-index: 1020;
  opacity: 0;
  transform: translateY(-10px);
  transition:
    opacity 0.3s ease,
    transform 0.3s ease;
  pointer-events: none;
}

.fullscreen-dropdown.animate-show {
  opacity: 1;
  transform: translateY(0);
  pointer-events: auto;
}

.fullscreen-dropdown.animate-hide {
  opacity: 0;
  transform: translateY(-10px);
  pointer-events: none;
}

.dropdown-content {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
}

.dropdown-item-container {
  flex: 1 1 auto;
  min-width: 250px;
}

.dropdown-item {
  display: block;
  padding: 15px 20px;
  color: #fff;
  text-decoration: none;
  border-radius: 4px;
  transition: background-color 0.2s ease;
}

.dropdown-item:hover {
  background-color: rgba(255, 255, 255, 0.1);
  text-decoration: none;
  color: #fff;
}

.dropdown-title {
  color: #17a2b8;
  margin-bottom: 5px;
  font-size: 0.875rem;
  text-transform: uppercase;
}

.dropdown-description {
  margin: 5px 0 0;
  font-size: 0.875rem;
  color: #aaa;
  line-height: 1.4;
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
