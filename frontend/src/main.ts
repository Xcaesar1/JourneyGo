import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import { Button, Checkbox, ConfigProvider, DatePicker, Empty, Form, Input, InputNumber, Layout, Modal, Select, Spin, TimePicker } from 'ant-design-vue'
import 'ant-design-vue/dist/reset.css'
import '@fontsource/outfit/latin-300.css'
import '@fontsource/outfit/latin-400.css'
import '@fontsource/outfit/latin-500.css'
import '@fontsource/outfit/latin-600.css'
import '@fontsource/outfit/latin-700.css'
import '@fontsource/outfit/latin-800.css'
import '@fontsource/outfit/latin-900.css'
import './styles/global.css'
import App from './App.vue'
import Landing from './views/Landing.vue'
import { i18n } from './i18n'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'Landing',
      component: Landing
    },
    {
      path: '/history',
      name: 'Memories',
      component: () => import('./views/Memories.vue')
    },
    {
      path: '/result',
      name: 'Result',
      component: () => import('./views/Result.vue')
    }
  ],
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    if (to.path === '/' && from.path === '/history') return false
    if (to.path === '/history') return false
    return { top: 0 }
  }
})

const app = createApp(App)

app.use(router)
for (const component of [Button, Checkbox, ConfigProvider, DatePicker, Empty, Form, Input, InputNumber, Layout, Modal, Select, Spin, TimePicker]) {
  app.use(component)
}
app.use(i18n)

app.mount('#app')

