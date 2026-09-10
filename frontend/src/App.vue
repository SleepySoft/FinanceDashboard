<template>
  <div id="app">
    <!-- 全局错误提示 -->
    <div class="toast-container">
      <TransitionGroup name="toast">
        <div v-for="t in toasts" :key="t.id" class="toast" :class="t.type">
          {{ t.message }}
        </div>
      </TransitionGroup>
    </div>

    <!-- 全局顶部栏：登录状态 / 设置入口 -->
    <div v-if="$route.path !== '/login'" class="topbar">
      <router-link to="/" class="topbar-logo">FinanceDashboard</router-link>
      <div class="topbar-nav">
        <router-link to="/" class="nav-link">看板</router-link>
        <router-link to="/requests" class="nav-link">待分析</router-link>
        <router-link to="/holdings" class="nav-link">持仓</router-link>
        <router-link to="/anomalies" class="nav-link">异动</router-link>
        <router-link to="/strategies" class="nav-link">策略</router-link>
        <router-link to="/backtest" class="nav-link">回测</router-link>
      </div>
      <div class="topbar-right">
        <span v-if="isAuthenticated" class="topbar-user">{{ user }}<span v-if="!isAdmin" class="topbar-role">只读</span></span>
        <span v-else-if="config.allow_anonymous_read" class="topbar-readonly" title="当前为只读模式，登录后可修改">只读浏览</span>
        <router-link v-if="isAuthenticated" to="/messages" class="topbar-link">消息</router-link>
        <router-link v-if="isAuthenticated" to="/settings" class="topbar-link">设置</router-link>
        <button v-if="isAuthenticated" class="topbar-btn" @click="doLogout">退出</button>
        <router-link v-else to="/login" class="topbar-link primary">登录</router-link>
      </div>
    </div>
    <main>
      <!-- 按 path 复用组件，避免切换股票时复用旧组件导致参数/状态错乱 -->
      <router-view :key="$route.path" />
    </main>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import auth from './composables/useAuth.js'
import { ref, onMounted, onUnmounted } from 'vue'

const router = useRouter()
const isAuthenticated = auth.isAuthenticated
const isAdmin = auth.isAdmin
const user = auth.user
const config = auth.config

// ─── Toast State ──────────────────────────────────────────────
const toasts = ref([])
let toastId = 0

function addToast(message, type = 'info', duration = 4000) {
  const id = ++toastId
  toasts.value.push({ id, message, type, duration })
  setTimeout(() => {
    toasts.value = toasts.value.filter(t => t.id !== id)
  }, duration)
}

let toastHandler = null
onMounted(() => {
  toastHandler = (e) => {
    const d = e.detail || {}
    addToast(d.message, d.type || 'info', d.duration || 4000)
  }
  window.addEventListener('fd:toast', toastHandler)
})
onUnmounted(() => {
  if (toastHandler) window.removeEventListener('fd:toast', toastHandler)
})

async function doLogout() {
  await auth.logout()
  if (router.currentRoute.value.path !== '/login') {
    router.push('/login')
  }
}
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0b1120; color: #e2e8f0; min-height: 100vh; }
#app { max-width: 1200px; margin: 0 auto; padding: 8px 16px 16px; }

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 0 8px;
  margin-bottom: 8px;
  border-bottom: 1px solid #1e293b;
}
.topbar-logo {
  font-size: 15px;
  font-weight: 700;
  color: #60a5fa;
  text-decoration: none;
  white-space: nowrap;
}
.topbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}
.topbar-nav {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
  justify-content: center;
}
.nav-link {
  color: #94a3b8;
  text-decoration: none;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 13px;
  border: 1px solid transparent;
}
.nav-link:hover, .nav-link.router-link-active {
  color: #e2e8f0;
  background: #1e293b;
  border-color: #334155;
}
.topbar-user {
  color: #94a3b8;
}
.topbar-role {
  margin-left: 6px;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.15);
  color: #94a3b8;
}
.topbar-readonly {
  color: #fbbf24;
  font-size: 12px;
  padding: 2px 8px;
  border: 1px solid rgba(251, 191, 36, 0.35);
  border-radius: 999px;
}
.topbar-link {
  color: #94a3b8;
  text-decoration: none;
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid #334155;
}
.topbar-link:hover {
  color: #e2e8f0;
  border-color: #475569;
}
.topbar-link.primary {
  color: #60a5fa;
  border-color: #1e3a5f;
  background: #1e3a5f;
}
.topbar-btn {
  background: transparent;
  border: 1px solid #334155;
  color: #94a3b8;
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 13px;
}
.topbar-btn:hover {
  color: #f87171;
  border-color: #7f1d1d;
}

.nav { padding: 8px 0 4px; margin-bottom: 8px; border-bottom: 1px solid #334155; }
.logo { font-size: 16px; font-weight: 700; color: #60a5fa; text-decoration: none; }

.card { background: #151e2e; border: 1px solid #334155; border-radius: 10px; padding: 20px; margin-bottom: 16px; }
h3 { font-size: 15px; font-weight: 600; margin-bottom: 12px; }
input, textarea, select { background: #0f172a; border: 1px solid #475569; color: #e2e8f0; padding: 8px 12px; border-radius: 6px; font-size: 14px; outline: none; }
input:focus, textarea:focus, select:focus { border-color: #3b82f6; }
button { cursor: pointer; border: none; border-radius: 6px; font-size: 13px; padding: 8px 16px; transition: opacity 0.15s; }
button:disabled { opacity: 0.5; cursor: not-allowed; }
button.primary { background: #3b82f6; color: white; }
button.ghost { background: transparent; color: #94a3b8; border: 1px solid #475569; }
button.danger { background: #dc2626; color: white; }

.tag { display: inline-block; padding: 2px 10px; border-radius: 4px; font-size: 12px; font-weight: 500; }
.tag-green { background: #064e3b; color: #34d399; }
.tag-yellow { background: #713f12; color: #fbbf24; }
.tag-red { background: #7f1d1d; color: #f87171; }
.tag-none { background: #334155; color: #94a3b8; }

/* ─── Toast Notifications ────────────────────────────────────── */
.toast-container {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 360px;
  pointer-events: none;
}
.toast {
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  color: white;
  box-shadow: 0 4px 12px rgba(0,0,0,0.4);
  pointer-events: auto;
  word-break: break-word;
}
.toast.error {
  background: #7f1d1d;
  border: 1px solid #dc2626;
}
.toast.info {
  background: #1e3a5f;
  border: 1px solid #3b82f6;
}
.toast.success {
  background: #064e3b;
  border: 1px solid #34d399;
}

/* Toast enter/leave transitions */
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(100%);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(100%);
}

@media (max-width: 640px) {
  #app { padding: 6px 10px 10px; }
  .card { padding: 14px; margin-bottom: 10px; }
  .nav { padding: 6px 0 2px; margin-bottom: 6px; }
  .logo { font-size: 14px; }
  .toast-container {
    right: 10px;
    left: 10px;
    max-width: none;
  }
}
</style>
