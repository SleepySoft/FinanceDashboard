import { ref, watch, onMounted, onUnmounted } from 'vue'

// sessionStorage 状态工具：用于在手机切后台被浏览器刷新后恢复页面上下文。
// key 统一加 fd: 前缀，避免与其它应用冲突。
const PREFIX = 'fd:'

export function readState(key, fallback) {
  try {
    const raw = sessionStorage.getItem(PREFIX + key)
    if (raw == null) return fallback
    return JSON.parse(raw)
  } catch {
    return fallback
  }
}

export function writeState(key, value) {
  try {
    sessionStorage.setItem(PREFIX + key, JSON.stringify(value))
  } catch {
    // 隐私模式/配额不足时静默降级，不影响正常使用
  }
}

export function removeState(key) {
  try {
    sessionStorage.removeItem(PREFIX + key)
  } catch {
    // ignore
  }
}

// 与 sessionStorage 双向同步的 ref（支持对象/数组/标量）
export function usePersistentRef(key, fallback) {
  const state = ref(readState(key, fallback))
  watch(state, (value) => writeState(key, value), { deep: true })
  return state
}

// 与 sessionStorage 同步的 Set（存储为数组，刷新后还原折叠/展开状态）
export function usePersistentSet(key, fallback = []) {
  const state = ref(new Set(readState(key, fallback)))
  watch(state, (value) => writeState(key, Array.from(value)), { deep: true })
  return state
}

// 滚动位置保存/恢复：滚动时节流保存，切后台或页面卸载时立即保存。
// 组件数据加载完成后调用 restore() 回到上次位置。
export function useScrollRestore(key) {
  let saveTimer = null

  function saveScroll() {
    writeState(key, window.scrollY)
  }

  function onScroll() {
    if (saveTimer) return
    saveTimer = setTimeout(() => {
      saveTimer = null
      saveScroll()
    }, 200)
  }

  function onVisibilityChange() {
    if (document.visibilityState === 'hidden') saveScroll()
  }

  function restore() {
    const y = readState(key, null)
    if (typeof y === 'number' && y > 0) {
      window.scrollTo(0, y)
    }
  }

  onMounted(() => {
    window.addEventListener('scroll', onScroll, { passive: true })
    document.addEventListener('visibilitychange', onVisibilityChange)
    window.addEventListener('pagehide', saveScroll)
  })
  onUnmounted(() => {
    window.removeEventListener('scroll', onScroll)
    document.removeEventListener('visibilitychange', onVisibilityChange)
    window.removeEventListener('pagehide', saveScroll)
    if (saveTimer) {
      clearTimeout(saveTimer)
      saveTimer = null
    }
  })

  return { restore, save: saveScroll }
}
