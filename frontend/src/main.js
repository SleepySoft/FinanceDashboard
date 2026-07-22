import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import Dashboard from './views/Dashboard.vue'
import StockDetail from './views/StockDetail.vue'
import Home from './views/Home.vue'
import Holdings from './views/Holdings.vue'
import AnomalyBoard from './views/AnomalyBoard.vue'

const routes = [
  { path: '/', component: Dashboard },
  { path: '/stock/:code', component: StockDetail },
  { path: '/requests', component: Home },
  { path: '/holdings', component: Holdings },
  { path: '/anomalies', component: AnomalyBoard },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

createApp(App).use(router).mount('#app')
