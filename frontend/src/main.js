import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import Dashboard from './views/Dashboard.vue'
import StockDetail from './views/StockDetail.vue'
import Home from './views/Home.vue'
import Holdings from './views/Holdings.vue'
import AnomalyBoard from './subsystems/anomaly/views/AnomalyBoard.vue'
import Login from './views/Login.vue'
import Settings from './views/Settings.vue'
import StrategyLibrary from './subsystems/backtest/views/StrategyLibrary.vue'
import Backtest from './subsystems/backtest/views/Backtest.vue'
import auth from './composables/useAuth.js'

const routes = [
  { path: '/', component: Dashboard },
  { path: '/stock/:code', component: StockDetail },
  { path: '/requests', component: Home },
  { path: '/holdings', component: Holdings },
  { path: '/anomalies', component: AnomalyBoard },
  { path: '/strategies', component: StrategyLibrary },
  { path: '/backtest', component: Backtest },
  { path: '/login', component: Login },
  { path: '/settings', component: Settings },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

// 全局登录守卫：
// - 未登录且配置为「完全锁定」时，除 /login 外一律跳转登录页
// - 未登录但配置为「只读」时，允许浏览所有页面（写操作在前端隐藏/后端拒绝）
router.beforeEach(async (to) => {
  await auth.bootstrap()
  if (to.path === '/login') {
    if (auth.isAuthenticated.value) return { path: '/' }
    return true
  }
  if (!auth.isAuthenticated.value && !auth.config.value.allow_anonymous_read) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  return true
})

// 运行时 401（会话过期等）：锁定模式下统一回登录页；只读模式保持原地，由调用方提示
window.addEventListener('fd:unauthorized', async () => {
  await auth.bootstrap(true)
  if (!auth.isAuthenticated.value && !auth.config.value.allow_anonymous_read) {
    router.push({ path: '/login' })
  }
})

// 跨页面跳转时回到顶部；各页面内部会在数据加载完成后恢复自己保存的滚动位置
router.afterEach((to, from) => {
  if (to.path !== from.path) {
    window.scrollTo(0, 0)
  }
})

const app = createApp(App)
app.use(router)
auth.bootstrap().finally(() => app.mount('#app'))
