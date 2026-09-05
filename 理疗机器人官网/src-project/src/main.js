import { createApp } from 'vue'
import App from './App.vue'
import Router from './router/index.js'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import pinia from './store'
import 'bootstrap/dist/css/bootstrap.min.css'
import 'bootstrap'
import 'animate.css'
const app = createApp(App)
app.use(pinia)
app.use(Router).mount('#app')
//全局注册Element Icon
for (let iconName in ElementPlusIconsVue) {
  app.component(iconName, ElementPlusIconsVue[iconName])
}
