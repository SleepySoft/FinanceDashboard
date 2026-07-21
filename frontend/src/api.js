const API_BASE = '/api'

async function api(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...opts.headers }
  const res = await fetch(API_BASE + path, {
    headers,
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export default {
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
    getNotes: (code) => api(`/stocks/${code}/notes`),
    addNote: (code, content) => api(`/stocks/${code}/notes`, { method: 'POST', body: { content } }),
    getBriefs: (code) => api(`/stocks/${code}/briefs`),
    generateBrief: (code, auto = true) => api(`/stocks/${code}/briefs`, { method: 'POST', body: { auto } }),
    deleteBrief: (code, id) => api(`/stocks/${code}/briefs/${id}`, { method: 'DELETE' }),
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
  health: () => api('/health'),
  holdings: {
    list: () => api('/holdings'),
    get: (code) => api(`/holdings/${code}`),
    addTrade: (code, trade) => api(`/holdings/${code}/trades`, { method: 'POST', body: trade }),
    deleteTrade: (code, tradeId) => api(`/holdings/${code}/trades/${tradeId}`, { method: 'DELETE' }),
    addAdjust: (code, adj) => api(`/holdings/${code}/adjust`, { method: 'POST', body: adj }),
  },
}
