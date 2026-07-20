import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import Dashboard from './views/Dashboard.vue'
import StockDetail from './views/StockDetail.vue'
import Home from './views/Home.vue'

const routes = [
  { path: '/', component: Dashboard },
  { path: '/stock/:code', component: Dashboard },
  { path: '/requests', component: Home },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

createApp(App).use(router).mount('#app')
