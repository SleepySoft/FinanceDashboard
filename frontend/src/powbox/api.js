/**
 * powbox/api.js — POW 后端接口封装。
 * 复用到其它项目时只需确认后端 powbox 路由的挂载前缀。
 */
const API_PREFIX = '/api/pow'

async function post(path, body) {
  const res = await fetch(API_PREFIX + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`)
  return data
}

async function get(path) {
  const res = await fetch(API_PREFIX + path)
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`)
  return data
}

export function fetchChallenge(scope) {
  return post('/challenge', { scope })
}

export function fetchPowConfig() {
  return get('/config')
}
