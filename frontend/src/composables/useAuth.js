import { ref, computed } from 'vue'
import api from '../api.js'

/**
 * 全局登录状态与权限配置（单例）。
 * - isAuthenticated: 当前是否有有效登录会话
 * - canWrite: 是否有写权限（未登录只读模式下为 false）
 * - config.allow_anonymous_read: false=完全锁定，未登录看不到数据；true=未登录只读
 */
const user = ref(null)
const config = ref({ allow_anonymous_read: false, session_ttl_hours: 168 })
const bootstrapped = ref(false)
let bootstrapPromise = null

async function bootstrap(force = false) {
  if (bootstrapped.value && !force) return
  if (bootstrapPromise) return bootstrapPromise
  bootstrapPromise = (async () => {
    try {
      const [me, cfg] = await Promise.all([api.auth.me(), api.auth.config()])
      user.value = me.authenticated ? me.user : null
      config.value = { ...config.value, ...cfg }
    } catch {
      user.value = null
    } finally {
      bootstrapped.value = true
      bootstrapPromise = null
    }
  })()
  return bootstrapPromise
}

const isAuthenticated = computed(() => !!user.value)
const canWrite = computed(() => isAuthenticated.value)

async function login(username, password) {
  await api.auth.login(username, password)
  await bootstrap(true)
  return user.value
}

async function logout() {
  try {
    await api.auth.logout()
  } catch {
    // 忽略登出异常，本地状态照常清空
  }
  user.value = null
  await bootstrap(true)
}

async function changePassword(oldPassword, newPassword) {
  return api.auth.changePassword(oldPassword, newPassword)
}

async function updateConfig(patch) {
  const cfg = await api.auth.updateConfig(patch)
  config.value = { ...config.value, ...cfg }
  return config.value
}

export default {
  user,
  config,
  bootstrapped,
  isAuthenticated,
  canWrite,
  bootstrap,
  login,
  logout,
  changePassword,
  updateConfig,
}
