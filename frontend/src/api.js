const API_BASE = '/api'

// ─── Global Toast System ───────────────────────────────────────
// Emit toast events anywhere: window.dispatchEvent(new CustomEvent('fd:toast', { detail: { message, type, duration } }))

async function api(path, opts = {}) {
  try {
    const headers = { 'Content-Type': 'application/json', ...opts.headers }
    const res = await fetch(API_BASE + path, {
      headers,
      ...opts,
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      // 会话过期/未登录：交由全局处理（main.js 根据配置决定跳登录页还是提示）
      if (res.status === 401 && !path.startsWith('/auth/')) {
        window.dispatchEvent(new CustomEvent('fd:unauthorized', { detail: { path } }))
      }
      const msg = err.detail || `HTTP ${res.status}`
      window.dispatchEvent(new CustomEvent('fd:toast', { detail: { message: `请求失败: ${msg}`, type: 'error', duration: 5000 } }))
      throw new Error(msg)
    }
    return res.json()
  } catch (networkErr) {
    // Network / CORS / DNS failure — not an HTTP error response
    if (networkErr.name === 'TypeError' || !networkErr.message?.includes('HTTP')) {
      window.dispatchEvent(new CustomEvent('fd:toast', {
        detail: { message: '网络错误或后端未响应，请稍后重试', type: 'error', duration: 6000 }
      }))
    }
    throw networkErr
  }
}

export default {
  auth: {
    me: () => api('/auth/me'),
    config: () => api('/auth/config'),
    login: (username, password) => api('/auth/login', { method: 'POST', body: { username, password } }),
    logout: () => api('/auth/logout', { method: 'POST' }),
    changePassword: (oldPassword, newPassword) => api('/auth/change-password', { method: 'POST', body: { old_password: oldPassword, new_password: newPassword } }),
    updateConfig: (patch) => api('/auth/config', { method: 'PATCH', body: patch }),
    regenerateToken: () => api('/auth/token/regenerate', { method: 'POST' }),
    listUsers: () => api('/auth/users'),
    createUser: (username, password, role) => api('/auth/users', { method: 'POST', body: { username, password, role } }),
    deleteUser: (username) => api(`/auth/users/${encodeURIComponent(username)}`, { method: 'DELETE' }),
    resetUserPassword: (username, newPassword) => api(`/auth/users/${encodeURIComponent(username)}/password`, { method: 'POST', body: { new_password: newPassword } }),
  },
  scheduler: {
    status: () => api('/scheduler/status'),
  },
  tushare: {
    test: (token) => api('/tushare/test', { method: 'POST', body: { token } }),
  },
  requests: {
    list: () => api('/requests'),
    submit: (code, name, sector, note, type = 'full') => api('/requests', { method: 'POST', body: { code, name, sector, note, type } }),
    delete: (id) => api(`/requests/${id}`, { method: 'DELETE' }),
  },
  stocks: {
    list: () => api('/stocks'),
    get: (code) => api(`/stocks/${code}`),
    updateTags: (code, tags) => api(`/stocks/${code}/tags`, { method: 'PATCH', body: tags }),
    updateStatus: (code, status) => api(`/stocks/${code}/status`, { method: 'PATCH', body: { status } }),
    updateHoldings: (code, holdings) => api(`/stocks/${code}/holdings`, { method: 'PATCH', body: holdings }),
    addPriceMark: (code, mark) => api(`/stocks/${code}/price-marks`, { method: 'POST', body: mark }),
    deletePriceMark: (code, id) => api(`/stocks/${code}/price-marks/${id}`, { method: 'DELETE' }),
    listReports: (code) => api(`/stocks/${code}/reports`),
    getReport: (code, id) => api(`/stocks/${code}/reports/${id}`),
    deleteReport: (code, id) => api(`/stocks/${code}/reports/${id}`, { method: 'DELETE' }),
    getNotes: (code) => api(`/stocks/${code}/notes`),
    addNote: (code, content) => api(`/stocks/${code}/notes`, { method: 'POST', body: { content } }),
    deleteNote: (code, time) => api(`/stocks/${code}/notes/${encodeURIComponent(time)}`, { method: 'DELETE' }),
  },
  agent: {
    tasks: () => api('/agent/tasks'),
    get: (id) => api(`/agent/tasks/${id}`),
    claim: (id) => api(`/agent/tasks/${id}/claim`, { method: 'POST' }),
    complete: (id, data) => api(`/agent/tasks/${id}/complete`, { method: 'POST', body: data }),
    fail: (id, reason) => api(`/agent/tasks/${id}/fail`, { method: 'POST', body: { reason } }),
  },
  dashboard: {
    get: () => api('/dashboard'),
    refresh: () => api('/dashboard/refresh'),
  },
  prices: {
    refresh: () => api('/prices/refresh'),
  },
  anomalies: {
    listDates: () => api('/anomalies/dates'),
    getByDate: (date) => api(`/anomalies/${date}`),
    getWeekly: (date) => api(`/anomalies/weekly/${date}`),
    getLatest: () => api('/anomalies/latest'),
    scan: (date, sampleSize, minScore) => api('/anomalies/scan', { method: 'POST', body: { date, sample_size: sampleSize, min_score: minScore } }),
    addToDashboard: (code) => api(`/anomalies/${code}/add-to-dashboard`, { method: 'POST' }),
  },
  providers: {
    list: () => api('/providers'),
    links: (code) => api(`/providers/links/${encodeURIComponent(code)}`),
    setDefault: (provider) => api('/providers/default', { method: 'PATCH', body: { provider } }),
  },
  health: () => api('/health'),
  messages: {
    list: () => api('/messages'),
    send: (content, pow) => api('/messages', { method: 'POST', body: { content, pow } }),
    delete: (id) => api(`/messages/${id}`, { method: 'DELETE' }),
  },
  feedback: {
    get: (code) => api(`/stocks/${code}/feedback`),
    submit: (code, vote, comment, pow) => api(`/stocks/${code}/feedback`, { method: 'POST', body: { vote, comment, pow } }),
    withdraw: (code) => api(`/stocks/${code}/feedback`, { method: 'DELETE' }),
    remove: (code, username) => api(`/stocks/${code}/feedback/${encodeURIComponent(username)}`, { method: 'DELETE' }),
  },
  holdings: {
    list: () => api('/holdings'),
    get: (code) => api(`/holdings/${code}`),
    getTrades: (code) => api(`/holdings/${code}/trades`),
    addTrade: (code, trade) => api(`/holdings/${code}/trades`, { method: 'POST', body: trade }),
    deleteTrade: (code, tradeId) => api(`/holdings/${code}/trades/${tradeId}`, { method: 'DELETE' }),
    addAdjust: (code, adj) => api(`/holdings/${code}/adjust`, { method: 'POST', body: adj }),
  },
  ladder: {
    get: (code) => api(`/stocks/${code}/ladder`),
    put: (code, body) => api(`/stocks/${code}/ladder`, { method: 'PUT', body }),
    addLevel: (code, level) => api(`/stocks/${code}/ladder/levels`, { method: 'POST', body: level }),
    updateLevel: (code, id, patch) => api(`/stocks/${code}/ladder/levels/${id}`, { method: 'PATCH', body: patch }),
    deleteLevel: (code, id) => api(`/stocks/${code}/ladder/levels/${id}`, { method: 'DELETE' }),
    applyStrategy: (code, type, params) => api(`/stocks/${code}/ladder/strategy`, { method: 'POST', body: { type, params } }),
    clearStrategy: (code) => api(`/stocks/${code}/ladder/strategy`, { method: 'DELETE' }),
    clearAgent: (code) => api(`/agent/stocks/${code}/ladder`, { method: 'DELETE' }),
  },
}
