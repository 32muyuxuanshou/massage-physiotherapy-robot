import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      name: 'home',
      path: '/',
      component: HomeView,
    },
  ],
})
router.beforeEach((to, from) => {
  console.log(to, from)

  // if(to.meta.requireAuth) {
  //     let token = localStorage.getItem('auth-system-token');
  //     let isLogin = localStorage.getItem('auth-system-login');
  //     if(!token||!isLogin){
  //         return {
  //             path: '/login'
  //         }
  //     }
  // }
})

export default router
