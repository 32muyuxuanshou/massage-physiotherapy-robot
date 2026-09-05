import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes = [
  {
    path: '/',
    redirect: '/login'
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login/Login.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/home',
    name: 'Home',
    component: () => import('@/views/Home/Home.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/ai-analysis',
    name: 'AiAnalysis',
    component: () => import('@/views/AiAnalysis/AiAnalysis.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/therapy-management',
    name: 'TherapyManagement',
    component: () => import('@/views/TherapyManagement/TherapyManagement.vue'),
    meta: { requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const userStore = useUserStore()
  
  if (to.meta.requiresAuth && !userStore.isLoggedIn) {
    next('/login')
  } else if (to.path === '/login' && userStore.isLoggedIn) {
    next('/home')
  } else {
    next()
  }
})

export default router
