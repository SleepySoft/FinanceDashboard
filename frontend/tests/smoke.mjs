/**
 * 冒烟测试：启动前后端（如未运行）→ 无头 Chrome 打开 Dashboard →
 * 断言股票卡片渲染成功且无任何页面级 JS 错误。
 *
 * 针对性防线：2026-07 "autoTimer 未声明"事故——挂载期 ReferenceError
 * 毒化 Vue 调度器，导致全站渲染冻结。此类 bug 只有真实浏览器能发现。
 *
 * 用法：npm run smoke
 * 退出码：0 通过 / 1 失败
 */
import { chromium } from 'playwright-core'
import { spawn } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const FRONTEND_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const BACKEND_DIR = path.resolve(FRONTEND_DIR, '..', 'backend')
const FRONTEND_URL = process.env.SMOKE_FRONTEND_URL || 'http://localhost:5173'
const BACKEND_URL = process.env.SMOKE_BACKEND_URL || 'http://localhost:8010'
const SMOKE_USERNAME = process.env.SMOKE_USERNAME || 'admin'
const SMOKE_PASSWORD = process.env.SMOKE_PASSWORD || 'SleepySoft@299792458'

const children = []

function log(...args) {
  console.log('[smoke]', ...args)
}

async function isUp(url) {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(2000) })
    return res.ok
  } catch {
    return false
  }
}

async function waitFor(url, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (await isUp(url)) return true
    await new Promise(r => setTimeout(r, 500))
  }
  return false
}

function startServer(name, command, args, cwd, env = {}) {
  log(`启动 ${name}: ${command} ${args.join(' ')}`)
  const child = spawn(command, args, {
    cwd,
    env: { ...process.env, ...env },
    stdio: ['ignore', 'pipe', 'pipe'],
    shell: process.platform === 'win32',
  })
  child.stdout.on('data', d => process.stdout.write(`[${name}] ${d}`))
  child.stderr.on('data', d => process.stdout.write(`[${name}:err] ${d}`))
  children.push(child)
  return child
}

async function ensureServers() {
  if (await isUp(`${BACKEND_URL}/api/auth/config`)) {
    log('后端已在运行，复用')
  } else {
    const python = path.join(BACKEND_DIR, 'venv', 'Scripts', 'python.exe')
    startServer('backend', python, ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8010'], BACKEND_DIR, {
      FD_ADMIN_USERNAME: SMOKE_USERNAME,
      FD_ADMIN_PASSWORD: SMOKE_PASSWORD,
    })
    if (!(await waitFor(`${BACKEND_URL}/api/auth/config`))) {
      throw new Error('后端启动超时')
    }
  }
  if (await isUp(FRONTEND_URL)) {
    log('前端已在运行，复用')
  } else {
    startServer('frontend', 'npx', ['vite'], FRONTEND_DIR, {
      VITE_PORT: new URL(FRONTEND_URL).port || '5173',
    })
    if (!(await waitFor(FRONTEND_URL))) {
      throw new Error('前端启动超时')
    }
  }
}

async function assertDashboard(page, data) {
  const expected = (data.stocks || []).length
  log(`API 返回 ${expected} 只股票`)
  if (expected === 0) {
    throw new Error('API 返回 0 只股票——数据层异常，请检查后端与 data/ 目录')
  }

  // 核心断言：数据到达后，DOM 必须渲染出股票卡片（默认分组视图，组默认折叠）
  await page.waitForSelector('.stock-card', { state: 'attached', timeout: 15000 })
  const cardCount = await page.locator('.stock-card').count()
  log(`渲染出 ${cardCount} 张股票卡片`)
  if (cardCount === 0) {
    throw new Error('API 有数据但未渲染出任何股票卡片——渲染管线异常')
  }

  // 展开第一个分组，卡片必须可见（验证折叠/展开的响应式更新）
  await page.locator('.sector-header').first().click()
  await page.waitForSelector('.stock-card:visible', { timeout: 5000 })

  // 交互性抽查：切换到列表视图，表格必须出现（验证响应式更新活着）
  await page.getByRole('button', { name: '列表', exact: true }).click()
  await page.waitForSelector('table tbody tr', { timeout: 5000 })
  const rows = await page.locator('table tbody tr').count()
  log(`列表视图渲染 ${rows} 行`)
  if (rows === 0) throw new Error('切换列表视图后无数据行——响应式更新失效')
}

async function assertStockModal(page, canWrite) {
  const firstRow = page.locator('table tbody tr').first()
  const stockCode = await firstRow.locator('.cell-code').textContent()
  let notesRequestCount = 0
  await page.route('**/api/stocks/*/notes', route => {
    notesRequestCount++
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: notesRequestCount === 1
        ? '{broken json'
        : JSON.stringify({ notes: [{ time: '2099-09-03 12:34', content: '价格快照测试', price: 12.34 }] }),
    })
  })
  await firstRow.click()
  await page.waitForSelector('.modal-content', { timeout: 10000 })

  const editAreaCount = await page.locator('.modal-content .timeline-note-input').count()
  if ((editAreaCount > 0) !== canWrite) {
    throw new Error(canWrite ? '登录后股票弹窗仍为只读' : '匿名只读模式暴露了编辑控件')
  }
  if (!page.url().includes(`stock=${encodeURIComponent(stockCode)}`)) {
    throw new Error('股票弹窗未同步到 URL，刷新后将无法恢复')
  }

  await page.setViewportSize({ width: 390, height: 844 })
  const savedScroll = await page.locator('.modal-body').evaluate(element => {
    element.scrollTop = Math.min(300, element.scrollHeight - element.clientHeight)
    element.dispatchEvent(new Event('scroll'))
    return element.scrollTop
  })
  await page.waitForTimeout(300)
  await page.reload({ waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.modal-content', { timeout: 15000 })
  await page.getByText('¥12.34', { exact: true }).waitFor({ timeout: 10000 })

  const priceColumnXs = await page.locator('.timeline-record-price').evaluateAll(elements =>
    elements.map(element => Math.round(element.getBoundingClientRect().x)),
  )
  if (priceColumnXs.length < 2 || Math.max(...priceColumnXs) - Math.min(...priceColumnXs) > 1) {
    throw new Error(`时间线价格列未对齐: ${priceColumnXs.join(', ')}`)
  }

  if (savedScroll > 0) {
    await page.waitForFunction(
      expected => globalThis.document.querySelector('.modal-body')?.scrollTop >= expected - 5,
      savedScroll,
      { timeout: 10000 },
    )
  }
  const restoredCode = await page.locator('.modal-code').textContent()
  if (restoredCode !== stockCode) throw new Error('手机尺寸刷新后恢复到了错误的股票弹窗')
  log(`股票弹窗权限与移动端恢复通过: ${stockCode}`)
}

async function main() {
  await ensureServers()

  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  const pageErrors = []
  try {
    const page = await browser.newPage()
    page.on('pageerror', err => pageErrors.push(`pageerror: ${err.message}`))
    page.on('console', msg => {
      if (msg.type() === 'error') pageErrors.push(`console.error: ${msg.text()}`)
    })

    const cfgRes = await fetch(`${BACKEND_URL}/api/auth/config`)
    const cfg = await cfgRes.json()
    const needsLogin = !cfg.allow_anonymous_read
    log(needsLogin ? '未登录访问被锁定，走 UI 登录流程' : '未登录只读模式，直接进入看板')

    let canWrite = false
    if (needsLogin) {
      const dashboardResponse = page.waitForResponse(
        res => res.url().includes('/api/dashboard') && res.ok(),
        { timeout: 20000 },
      )
      log(`打开 ${FRONTEND_URL}/#/login`)
      await page.goto(`${FRONTEND_URL}/#/login`, { waitUntil: 'domcontentloaded' })
      await page.waitForSelector('input[autocomplete="username"]', { timeout: 10000 })
      await page.fill('input[autocomplete="username"]', SMOKE_USERNAME)
      await page.fill('input[type="password"]', SMOKE_PASSWORD)
      await page.click('button[type="submit"]')

      let res = null
      try {
        res = await dashboardResponse
      } catch {
        // 未等到 dashboard 响应：可能是登录失败，取页面错误提示给出可读信息
      }
      if (!res) {
        const loginError = await page
          .waitForSelector('.login-error', { state: 'attached', timeout: 3000 })
          .catch(() => null)
        const errText = loginError ? await loginError.textContent() : ''
        throw new Error(`登录失败（${errText || '超时'}）。请确认后端账号为 ${SMOKE_USERNAME}，密码为 ${SMOKE_PASSWORD}，或先开启未登录只读模式`)
      }
      const data = await res.json()
      await assertDashboard(page, data)
      canWrite = true
    } else {
      log(`打开 ${FRONTEND_URL}/#/`)
      const dashboardResponse = page.waitForResponse(
        res => res.url().includes('/api/dashboard') && res.ok(),
        { timeout: 20000 },
      )
      await page.goto(`${FRONTEND_URL}/#/`, { waitUntil: 'domcontentloaded' })
      const res = await dashboardResponse
      const data = await res.json()
      await assertDashboard(page, data)
    }

    await assertStockModal(page, canWrite)

    if (pageErrors.length > 0) {
      throw new Error(`页面存在 JS 错误:\n${pageErrors.join('\n')}`)
    }

    log('✅ 冒烟测试通过')
  } finally {
    await browser.close()
  }
}

function cleanup() {
  for (const child of children) {
    try { child.kill() } catch { /* ignore */ }
  }
}

main()
  .then(() => { cleanup(); process.exit(0) })
  .catch(err => {
    console.error('[smoke] ❌ 失败:', err.message)
    cleanup()
    process.exit(1)
  })
