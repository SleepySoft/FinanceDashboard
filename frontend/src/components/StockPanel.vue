<template>
  <div class="stock-panel">
    <!-- Header -->
    <div v-if="!embedded" class="panel-header card">
      <div class="title-row compact">
        <div class="header-main">
          <span class="header-code">{{ meta.code }}</span>
          <span class="header-name">{{ meta.name }}</span>
          <span v-if="meta.sector" class="header-sector">· {{ meta.sector }}</span>
          <span :class="['dim-badge-sm', 'dim-' + dim('quality')]">质</span>
          <span :class="['dim-badge-sm', 'dim-' + dim('valuation')]">估</span>
          <span :class="['dim-badge-sm', 'dim-' + dim('timing')]">时</span>
          <span :class="['dim-badge-sm', 'dim-' + dim('risk')]">险</span>
        </div>
        <div class="actions">
          <select v-model="statusForm.status" @change="updateStatus" title="投资状态">
            <option value="tracking">🔭 跟踪中</option>
            <option value="bullish">看好</option>
            <option value="neutral">观望</option>
            <option value="waiting">伺机</option>
            <option value="avoid">回避</option>
            <option value="no_interest">无兴趣</option>
            <option value="blacklist">黑名单</option>
            <option value="archive">📁 归档</option>
          </select>
          <button :class="['tag-toggle', { active: tagForm.watchlist }]" @click="toggleWatchlist">
            {{ tagForm.watchlist ? '已关注' : '关注' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Info Bar (for embedded mode) -->
    <div v-else class="info-bar card">
      <div class="info-main">
        <span class="info-price" :class="priceClass(meta.change_pct)">
          {{ meta.last_price != null ? '¥' + meta.last_price.toFixed(2) : '--' }}
        </span>
        <span v-if="meta.change_pct != null" class="info-pct" :class="priceClass(meta.change_pct)">
          {{ meta.change_pct > 0 ? '+' : '' }}{{ meta.change_pct.toFixed(2) }}%
        </span>
        <span :class="['status-tag', 'status-' + (meta.status || 'neutral')]">
          {{ statusLabel(meta.status) }}
        </span>
        <span v-if="meta.tags?.watchlist" class="watch-tag">已关注</span>
      </div>
      <div class="info-dims">
        <span :class="['dim-badge', 'dim-' + dim('quality')]">质</span>
        <span :class="['dim-badge', 'dim-' + dim('valuation')]">估</span>
        <span :class="['dim-badge', 'dim-' + dim('timing')]">时</span>
        <span :class="['dim-badge', 'dim-' + dim('risk')]">险</span>
        <span :class="['verdict-badge', 'verdict-' + (meta.dimensions?.verdict || meta.overall)]">
          {{ verdictLabel }}
        </span>
      </div>
    </div>

    <!-- Analysis Sections -->
    <div class="analysis-grid">
      <!-- Fundamental Analysis -->
      <div class="analysis-card card">
        <div class="analysis-header" @click="showFund = !showFund">
          <div class="analysis-title">
            <span class="analysis-icon">📊</span>
            <div>
              <h3>基本面分析</h3>
              <p class="analysis-status" :class="{ expired: meta.cache?.fundamental?.expired }">
                {{ fundamentalStatus }}
              </p>
            </div>
          </div>
          <div class="header-right">
            <button v-if="!readonly" class="primary" @click.stop="analyze('fundamental')" :disabled="analyzing.fundamental">
              {{ analyzing.fundamental ? '分析中...' : '重新分析' }}
            </button>
            <span class="collapse-btn">{{ showFund ? '▼' : '▶' }}</span>
          </div>
        </div>

        <div class="analysis-content" v-show="showFund">
          <div v-if="fundamentalReports.length > 0">
            <div class="report-latest" v-if="fundamentalContent">
              <div class="report-badge-row">
                <span class="timeline-badge badge-fund">基本面</span>
                <span class="report-time">{{ fmtDateTime(fundamentalReports[0]?.created_at) }}</span>
                <span class="timeline-latest">最新</span>
              </div>
              <div class="report-body" v-html="renderMarkdown(fundamentalContent)"></div>
            </div>
            <div class="older-versions" v-if="fundamentalReports.length > 1">
              <div class="older-toggle" @click.stop="showFundHistory = !showFundHistory">
                <span>{{ showFundHistory ? '▼' : '▶' }} 历史版本 ({{ fundamentalReports.length - 1 }})</span>
              </div>
              <div v-show="showFundHistory" class="timeline-collapsed">
                <div
                  v-for="(r, idx) in fundamentalReports.slice(1)"
                  :key="r.id"
                  class="timeline-collapsed-item"
                  @click.stop="toggleFundVersion(idx + 1)"
                >
                  <div class="tci-header">
                    <span class="tci-dot"></span>
                    <span class="tci-time">{{ fmtDateTime(r.created_at) }}</span>
                    <span :class="['timeline-badge', r.type === 'full' ? 'badge-full' : 'badge-fund']">
                      {{ r.type === 'full' ? '综合' : '基本面' }}
                    </span>
                  </div>
                  <div class="tci-body" v-show="fundExpandedIndex === idx + 1" v-html="renderMarkdown(fundVersionContent)"></div>
                </div>
              </div>
            </div>
          </div>
          <div class="empty" v-else>暂无基本面分析报告</div>
        </div>
      </div>

      <!-- Technical Analysis -->
      <div class="analysis-card card">
        <div class="analysis-header" @click="showTech = !showTech">
          <div class="analysis-title">
            <span class="analysis-icon">📈</span>
            <div>
              <h3>技术面分析</h3>
              <p class="analysis-status" :class="{ expired: meta.cache?.technical?.expired }">
                {{ technicalStatus }}
              </p>
            </div>
          </div>
          <div class="header-right">
            <button v-if="!readonly" class="primary" @click.stop="analyze('technical')" :disabled="analyzing.technical">
              {{ analyzing.technical ? '分析中...' : '重新分析' }}
            </button>
            <span class="collapse-btn">{{ showTech ? '▼' : '▶' }}</span>
          </div>
        </div>

        <div class="analysis-content" v-show="showTech">
          <div v-if="technicalReports.length > 0">
            <div class="report-latest" v-if="technicalContent">
              <div class="report-badge-row">
                <span class="timeline-badge badge-tech">技术面</span>
                <span class="report-time">{{ fmtDateTime(technicalReports[0]?.created_at) }}</span>
                <span class="timeline-latest">最新</span>
              </div>
              <div class="report-body" v-html="renderMarkdown(technicalContent)"></div>
            </div>
            <div class="older-versions" v-if="technicalReports.length > 1">
              <div class="older-toggle" @click.stop="showTechHistory = !showTechHistory">
                <span>{{ showTechHistory ? '▼' : '▶' }} 历史版本 ({{ technicalReports.length - 1 }})</span>
              </div>
              <div v-show="showTechHistory" class="timeline-collapsed">
                <div
                  v-for="(r, idx) in technicalReports.slice(1)"
                  :key="r.id"
                  class="timeline-collapsed-item"
                  @click.stop="toggleTechVersion(idx + 1)"
                >
                  <div class="tci-header">
                    <span class="tci-dot"></span>
                    <span class="tci-time">{{ fmtDateTime(r.created_at) }}</span>
                    <span :class="['timeline-badge', r.type === 'full' ? 'badge-full' : 'badge-tech']">
                      {{ r.type === 'full' ? '综合' : '技术面' }}
                    </span>
                  </div>
                  <div class="tci-body" v-show="techExpandedIndex === idx + 1" v-html="renderMarkdown(techVersionContent)"></div>
                </div>
              </div>
            </div>
          </div>
          <div class="empty" v-else>暂无技术面分析报告</div>
        </div>
      </div>
    </div>

    <!-- Price Marks -->
    <div class="card">
      <div class="section-header">
        <h3>📌 价格标记</h3>
      </div>
      <div class="price-marks">
        <div v-for="m in meta.price_marks" :key="m.id" class="price-mark">
          <span :class="['mark-label', 'mark-' + m.type]">{{ m.label }}</span>
          <span class="mark-price">¥{{ m.price.toFixed(2) }}</span>
          <span v-if="meta.last_price != null" :class="['mark-diff', diffClass(meta.last_price - m.price)]">
            {{ meta.last_price >= m.price ? '+' : '' }}{{ (meta.last_price - m.price).toFixed(2) }}
            ({{ ((meta.last_price - m.price) / m.price * 100).toFixed(1) }}%)
          </span>
          <button v-if="!readonly" class="ghost" style="padding:2px 8px;font-size:12px" @click.stop="removeMark(m.id)">×</button>
        </div>
      </div>
      <div v-if="meta.price_marks?.length === 0" class="empty" style="margin-bottom:12px">暂无价格标记</div>
      <div v-if="!readonly" class="add-mark">
        <div class="preset-labels">
          <span class="preset-label" @click="newMark.label = '目标买入'; newMark.type = 'target_buy'">目标买入</span>
          <span class="preset-label" @click="newMark.label = '止损'; newMark.type = 'stop_loss'">止损</span>
          <span class="preset-label" @click="newMark.label = '止盈'; newMark.type = 'take_profit'">止盈</span>
          <span class="preset-label" @click="newMark.label = '加仓'; newMark.type = 'add'">加仓</span>
          <span class="preset-label" @click="newMark.label = '减仓'; newMark.type = 'reduce'">减仓</span>
          <span class="preset-label" @click="newMark.label = '标记'; newMark.type = 'mark'">标记</span>
        </div>
        <div class="add-mark-row">
          <input v-model="newMark.label" placeholder="标签（可自定义）" style="flex:1" />
          <div class="price-input-group">
            <button class="ghost price-shortcut" @click="fillPrice(-0.1)">-10%</button>
            <button class="ghost price-shortcut" @click="fillPrice(0)">当前</button>
            <button class="ghost price-shortcut" @click="fillPrice(0.1)">+10%</button>
            <input v-model.number="newMark.price" placeholder="价格" type="number" step="0.01" style="width:100px" />
          </div>
          <button class="primary" @click="addMark" :disabled="!newMark.label || !newMark.price">添加</button>
        </div>
      </div>
    </div>

    <!-- Daily Briefs -->
    <div class="card briefs-card">
      <div class="briefs-header" @click="showBriefs = !showBriefs">
        <div class="briefs-title">
          <span class="briefs-icon">📋</span>
          <div>
            <h3>交易日简评</h3>
            <p class="briefs-count">{{ briefs.length }} 条记录</p>
          </div>
        </div>
        <div class="header-right">
          <button v-if="!readonly" class="primary" @click.stop="generateBrief" :disabled="generatingBrief || todayBriefExists">
            {{ generatingBrief ? '生成中...' : (todayBriefExists ? '今日已评' : '生成今日简评') }}
          </button>
          <span class="collapse-btn">{{ showBriefs ? '▼' : '▶' }}</span>
        </div>
      </div>
      
      <div v-show="showBriefs" class="briefs-content">
        <div v-if="displayBriefs.length > 0" class="briefs-timeline">
          <div v-for="b in displayBriefs" :key="b.id" class="brief-item">
            <div class="brief-date-line">
              <span class="brief-dot"></span>
              <span class="brief-date-text">{{ b.date }}</span>
              <span :class="['brief-pct', b.change_pct > 0 ? 'up' : 'down']">
                {{ b.change_pct > 0 ? '+' : '' }}{{ b.change_pct?.toFixed(2) }}%
              </span>
            </div>
            <div class="brief-body">
              <div class="brief-meta">
                <span class="brief-price">收 ¥{{ b.price?.toFixed(2) }}</span>
              </div>
              <div class="brief-text">{{ b.content }}</div>
            </div>
          </div>
        </div>
        <div v-if="briefs.length > 5 && !showAllBriefs" class="briefs-more" @click="showAllBriefs = true">
          ▼ 还有 {{ briefs.length - 5 }} 条记录
        </div>
        <div v-if="briefs.length === 0" class="empty">暂无交易日简评</div>
      </div>
    </div>

    <!-- Holdings -->
    <div class="card holdings-card">
      <div class="holdings-header" @click="showHoldings = !showHoldings">
        <div class="holdings-title">
          <span class="holdings-icon">📦</span>
          <div>
            <h3>持仓记录</h3>
            <p v-if="holdingsData.summary" class="holdings-count">
              {{ holdingsData.summary.total_quantity }}股 @ ¥{{ holdingsData.summary.avg_cost.toFixed(2) }}
              <span v-if="holdingsData.summary.realized_pnl > 0" class="t-profit">已落袋 +{{ holdingsData.summary.realized_pnl.toFixed(0) }}</span>
            </p>
            <p v-else class="holdings-count">暂无持仓记录</p>
          </div>
        </div>
        <span class="collapse-btn">{{ showHoldings ? '▼' : '▶' }}</span>
      </div>
      <div v-show="showHoldings" class="holdings-content">
        <div v-if="holdingsData.trades?.length > 0">
          <!-- Summary -->
          <div v-if="holdingsData.summary" class="holdings-summary">
            <div class="hs-row">
              <span class="hs-label">持仓</span>
              <span class="hs-value">{{ holdingsData.summary.total_quantity }}股 @ ¥{{ holdingsData.summary.avg_cost.toFixed(2) }}</span>
            </div>
            <div class="hs-row">
              <span class="hs-label">市值</span>
              <span class="hs-value">¥{{ ((meta.last_price || 0) * holdingsData.summary.total_quantity).toFixed(0) }}</span>
              <span v-if="holdingsData.summary.total_quantity > 0 && meta.last_price" :class="['hs-pnl', meta.last_price >= holdingsData.summary.avg_cost ? 'up' : 'down']">
                {{ meta.last_price >= holdingsData.summary.avg_cost ? '+' : '' }}{{ ((meta.last_price - holdingsData.summary.avg_cost) * holdingsData.summary.total_quantity).toFixed(0) }}
                ({{ (((meta.last_price - holdingsData.summary.avg_cost) / holdingsData.summary.avg_cost) * 100).toFixed(1) }}%)
              </span>
            </div>
            <div v-if="holdingsData.summary.realized_pnl > 0" class="hs-row">
              <span class="hs-label">已落袋</span>
              <span class="hs-value t-profit">+{{ holdingsData.summary.realized_pnl.toFixed(0) }}</span>
            </div>
          </div>
          <!-- Trades table -->
          <div class="trades-table-wrap">
            <table class="trades-table">
              <thead>
                <tr>
                  <th>日期</th>
                  <th>类型</th>
                  <th>价格</th>
                  <th>数量</th>
                  <th>手续费</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="t in holdingsData.trades" :key="t.id">
                  <td>{{ t.date }}</td>
                  <td :class="t.type === 'buy' ? 'up' : 'down'">{{ t.type === 'buy' ? '买入' : '卖出' }}</td>
                  <td>¥{{ t.price.toFixed(2) }}</td>
                  <td>{{ t.quantity }}</td>
                  <td>{{ t.fee?.toFixed(2) || '-' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <div v-else class="empty">暂无交易记录</div>
      </div>
    </div>

    <!-- Notes -->
    <div class="card notes-card">
      <h3>📝 随想笔记</h3>
      <div v-if="!readonly" class="note-input">
        <textarea v-model="newNote" rows="3" placeholder="记录你的想法..."></textarea>
        <button class="primary" @click="addNote" :disabled="!newNote.trim()">保存</button>
      </div>
      <div class="notes-list">
        <div v-for="n in notes" :key="n.time" class="note-item">
          <div class="note-time">{{ n.time }}</div>
          <div class="note-content">{{ n.content }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import api from '../api.js'

const props = defineProps({
  code: { type: String, required: true },
  embedded: { type: Boolean, default: false },
  readonly: { type: Boolean, default: false }
})

const meta = ref({ cache: { fundamental: {}, technical: {} }, price_marks: [], reports: [] })
const notes = ref([])
const analyzing = ref({ fundamental: false, technical: false })

const fundamentalContent = ref('')
const technicalContent = ref('')
const fundVersionContent = ref('')
const techVersionContent = ref('')

const showFund = ref(true)
const showTech = ref(true)
const showFundHistory = ref(false)
const showTechHistory = ref(false)
const fundExpandedIndex = ref(-1)
const techExpandedIndex = ref(-1)

const tagForm = ref({ watchlist: false })
const statusForm = ref({ status: 'neutral' })
const newMark = ref({ label: '', price: null, type: 'mark' })
const newNote = ref('')

const briefs = ref([])
const showBriefs = ref(false)
const showAllBriefs = ref(false)
const generatingBrief = ref(false)

const holdingsData = ref({ trades: [], summary: null })
const showHoldings = ref(false)

const todayBriefExists = computed(() => {
  const today = new Date().toISOString().slice(0, 10)
  return briefs.value.some(b => b.date === today)
})

const displayBriefs = computed(() => {
  if (showAllBriefs.value) return briefs.value
  return briefs.value.slice(0, 5)
})

const fundamentalReports = computed(() =>
  (meta.value.reports || [])
    .filter(r => r.type === 'fundamental' || r.type === 'full')
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
)

const technicalReports = computed(() =>
  (meta.value.reports || [])
    .filter(r => r.type === 'technical' || r.type === 'full')
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
)

const fundamentalStatus = computed(() => {
  const c = meta.value.cache?.fundamental
  if (!c?.last) return '未分析'
  return c.expired ? `已过期（${fmtDate(c.last)}）` : `有效（${fmtDate(c.last)}）`
})

const technicalStatus = computed(() => {
  const c = meta.value.cache?.technical
  if (!c?.last) return '未分析'
  return c.expired ? `已过期（${fmtDate(c.last)}）` : `有效（${fmtDate(c.last)}）`
})

const verdictLabel = computed(() => {
  const v = meta.value.dimensions?.verdict || meta.value.overall
  const map = { green: '看好', yellow: '观望', red: '回避', none: '-' }
  return map[v] || '-'
})

function dim(key) {
  const dims = meta.value.dimensions || meta.value.tags || {}
  return dims[key] || 'none'
}

function priceClass(pct) {
  if (pct == null) return ''
  return pct >= 0 ? 'up' : 'down'
}

function diffClass(diff) {
  return diff >= 0 ? 'up' : 'down'
}

function statusLabel(status) {
  const map = { tracking: '🔭 跟踪中', bullish: '看好', neutral: '观望', waiting: '伺机', avoid: '回避', no_interest: '无兴趣', blacklist: '黑名单', archive: '📁 归档' }
  return map[status] || '观望'
}

async function load() {
  const data = await api.stocks.get(props.code)
  meta.value = data
  tagForm.value = { watchlist: data.tags?.watchlist || false }
  statusForm.value = { status: data.status || 'neutral' }
  briefs.value = data.daily_briefs || []
  const n = await api.stocks.getNotes(props.code)
  notes.value = n.notes
  // Load holdings
  try {
    const h = await api.holdings.get(props.code)
    if (h.has_data) {
      holdingsData.value.summary = h.summary
    }
    const t = await api.holdings.getTrades(props.code)
    holdingsData.value.trades = t.trades || []
  } catch (e) {
    holdingsData.value = { trades: [], summary: null }
  }
  await loadLatestFundamental()
  await loadLatestTechnical()
}

async function loadLatestFundamental() {
  const reps = fundamentalReports.value
  if (reps.length === 0) { fundamentalContent.value = ''; return }
  try {
    const data = await api.stocks.getReport(props.code, reps[0].id)
    fundamentalContent.value = data.content
  } catch (e) { fundamentalContent.value = '' }
}

async function loadLatestTechnical() {
  const reps = technicalReports.value
  if (reps.length === 0) { technicalContent.value = ''; return }
  try {
    const data = await api.stocks.getReport(props.code, reps[0].id)
    technicalContent.value = data.content
  } catch (e) { technicalContent.value = '' }
}

async function toggleFundVersion(idx) {
  if (fundExpandedIndex.value === idx) { fundExpandedIndex.value = -1; return }
  fundExpandedIndex.value = idx
  const reps = fundamentalReports.value
  if (idx >= reps.length) return
  try {
    const data = await api.stocks.getReport(props.code, reps[idx].id)
    fundVersionContent.value = data.content
  } catch (e) { fundVersionContent.value = '加载失败' }
}

async function toggleTechVersion(idx) {
  if (techExpandedIndex.value === idx) { techExpandedIndex.value = -1; return }
  techExpandedIndex.value = idx
  const reps = technicalReports.value
  if (idx >= reps.length) return
  try {
    const data = await api.stocks.getReport(props.code, reps[idx].id)
    techVersionContent.value = data.content
  } catch (e) { techVersionContent.value = '加载失败' }
}

async function updateStatus() {
  await api.stocks.updateStatus(props.code, statusForm.value.status)
}

async function toggleWatchlist() {
  const newVal = !tagForm.value.watchlist
  tagForm.value.watchlist = newVal
  await api.stocks.updateTags(props.code, { watchlist: newVal })
}

async function analyze(type) {
  analyzing.value[type] = true
  try {
    const task = await api.requests.submit(props.code, meta.value.name, meta.value.sector, '', type)
    const poll = setInterval(async () => {
      const tasks = await api.agent.tasks()
      const t = tasks.find(x => x.id === task.id)
      if (!t || t.status === 'completed' || t.status === 'failed') {
        clearInterval(poll)
        analyzing.value[type] = false
        await load()
      }
    }, 3000)
  } catch (e) {
    analyzing.value[type] = false
    alert('提交分析请求失败: ' + e.message)
  }
}

async function addMark() {
  await api.stocks.addPriceMark(props.code, newMark.value)
  newMark.value = { label: '', price: null, type: 'mark' }
  await load()
}

async function removeMark(id) {
  await api.stocks.deletePriceMark(props.code, id)
  await load()
}

async function addNote() {
  await api.stocks.addNote(props.code, newNote.value)
  newNote.value = ''
  await load()
}

async function generateBrief() {
  if (todayBriefExists.value) return
  generatingBrief.value = true
  try {
    const res = await api.stocks.generateBrief(props.code)
    if (res.brief) {
      briefs.value.unshift(res.brief)
      briefs.value.sort((a, b) => b.date.localeCompare(a.date))
    } else {
      alert(res.message || '今日无显著变化，已跳过')
    }
  } catch (e) {
    alert('生成简评失败: ' + e.message)
  } finally {
    generatingBrief.value = false
  }
}

function renderMarkdown(md) {
  if (!md) return ''
  return md
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/^\|(.+)\|$/gim, (match) => {
      const cells = match.split('|').filter(c => c.trim()).map(c => `<td>${c.trim()}</td>`).join('')
      return `<tr>${cells}</tr>`
    })
    .replace(/(<tr>.*<\/tr>\n?)+/g, '<table style="border-collapse:collapse;margin:10px 0;width:100%">$&</table>')
    .replace(/\n/g, '<br>')
}

function fillPrice(offset) {
  const base = newMark.value.price || meta.value.last_price
  if (base == null) return
  newMark.value.price = Number((base * (1 + offset)).toFixed(2))
}

function fmtDate(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
}

function fmtDateTime(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}

watch(() => props.code, load)
onMounted(load)
</script>

<style scoped>
.stock-panel { display: flex; flex-direction: column; gap: 12px; }

/* Header */
.panel-header { margin-bottom: 0; }
.title-row { display: flex; justify-content: space-between; align-items: center; }
.title-row.compact { align-items: center; margin-bottom: 0; }

.header-main { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.header-code { font-size: 15px; font-weight: 600; color: #60a5fa; }
.header-name { font-size: 16px; font-weight: 600; color: #e2e8f0; }
.header-sector { font-size: 12px; color: #64748b; }

.dim-badge-sm { display: inline-block; padding: 1px 5px; border-radius: 3px; font-size: 11px; font-weight: 600; }
.dim-green { background: #064e3b; color: #34d399; }
.dim-yellow { background: #713f12; color: #fbbf24; }
.dim-red { background: #7f1d1d; color: #f87171; }
.dim-none { background: #334155; color: #64748b; }

.actions { display: flex; gap: 10px; align-items: center; }
.tag-toggle { padding: 6px 14px; border-radius: 6px; border: 1px solid #475569; background: transparent; color: #94a3b8; font-size: 13px; cursor: pointer; }
.tag-toggle.active { background: #fbbf24; color: #1e293b; border-color: #fbbf24; }

/* Info bar (embedded) */
.info-bar { display: flex; justify-content: space-between; align-items: center; padding: 12px 14px; gap: 10px; flex-wrap: wrap; }
.info-main { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.info-price { font-size: 24px; font-weight: 700; }
.info-pct { font-size: 13px; font-weight: 500; }
.status-tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }
.status-tracking { background: #1e3a5f; color: #60a5fa; }
.status-bullish { background: #064e3b; color: #34d399; }
.status-neutral { background: #713f12; color: #fbbf24; }
.status-avoid { background: #7f1d1d; color: #f87171; }
.status-no_interest { background: #334155; color: #94a3b8; }
.status-blacklist { background: #000000; color: #f87171; }
.status-waiting { background: #3d2c12; color: #fbbf24; }
.status-archive { background: #334155; color: #94a3b8; }
.watch-tag { display: inline-block; padding: 1px 6px; border-radius: 4px; background: #fbbf24; color: #1e293b; font-size: 10px; font-weight: 600; }
.info-dims { display: flex; gap: 4px; flex-wrap: wrap; }
.dim-badge { display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.verdict-badge { display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.verdict-green { background: #064e3b; color: #34d399; }
.verdict-yellow { background: #713f12; color: #fbbf24; }
.verdict-red { background: #7f1d1d; color: #f87171; }
.verdict-none { background: #334155; color: #64748b; }

/* Analysis */
.analysis-grid { display: flex; flex-direction: column; gap: 12px; }
.analysis-card h3 { font-size: 16px; margin-bottom: 2px; }
.analysis-header { display: flex; justify-content: space-between; align-items: center; cursor: pointer; padding-bottom: 14px; transition: background 0.15s; }
.analysis-header:hover { background: #1e293b; }
.analysis-title { display: flex; align-items: center; gap: 12px; pointer-events: none; }
.analysis-icon { font-size: 24px; }
.analysis-status { font-size: 12px; color: #64748b; margin-top: 2px; }
.analysis-status.expired { color: #f87171; }
.analysis-content { min-height: 40px; }
.empty { color: #475569; font-size: 13px; padding: 12px 0; text-align: center; }

.header-right { display: flex; align-items: center; gap: 10px; pointer-events: auto; }
.collapse-btn { font-size: 14px; color: #64748b; cursor: pointer; padding: 4px; min-width: 20px; text-align: center; }
.collapse-btn:hover { color: #e2e8f0; }

/* Report */
.report-latest { margin-bottom: 16px; }
.report-badge-row { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
.report-time { font-size: 12px; color: #94a3b8; }
.report-body { line-height: 1.8; font-size: 14px; }
.report-body h1 { font-size: 18px; font-weight: 700; margin: 16px 0 10px; color: #e2e8f0; }
.report-body h2 { font-size: 15px; font-weight: 600; margin: 14px 0 8px; color: #94a3b8; border-bottom: 1px solid #334155; padding-bottom: 4px; }
.report-body h3 { font-size: 13px; font-weight: 600; margin: 10px 0 6px; color: #60a5fa; }
.report-body strong { color: #e2e8f0; }
.report-body table { width: 100%; margin: 10px 0; font-size: 12px; }
.report-body td { padding: 5px 8px; border: 1px solid #334155; }
.report-body tr:first-child td { background: #1e293b; font-weight: 600; }

.older-versions { border-top: 1px solid #334155; padding-top: 12px; }
.older-toggle { display: flex; align-items: center; gap: 8px; padding: 8px 12px; background: #0f172a; border-radius: 6px; cursor: pointer; font-size: 13px; color: #94a3b8; transition: background 0.15s; }
.older-toggle:hover { background: #1e293b; }
.timeline-collapsed { margin-top: 10px; }
.timeline-collapsed-item { margin-bottom: 8px; }
.tci-header { display: flex; align-items: center; gap: 10px; padding: 8px 12px; background: #0f172a; border: 1px solid #334155; border-radius: 6px; cursor: pointer; font-size: 13px; transition: all 0.15s; }
.tci-header:hover { background: #1e293b; border-color: #475569; }
.tci-dot { width: 8px; height: 8px; border-radius: 50%; background: #475569; flex-shrink: 0; }
.tci-time { color: #94a3b8; }
.tci-body { padding: 12px; border: 1px solid #334155; border-top: none; border-radius: 0 0 6px 6px; font-size: 14px; line-height: 1.8; }

.timeline-badge { font-size: 11px; padding: 1px 8px; border-radius: 4px; font-weight: 500; }
.badge-fund { background: #1e3a5f; color: #60a5fa; }
.badge-tech { background: #3f2c1d; color: #fbbf24; }
.badge-full { background: #14532d; color: #34d399; }
.timeline-latest { font-size: 11px; padding: 1px 8px; border-radius: 4px; background: #3b82f6; color: white; font-weight: 500; }

/* Price marks */
.price-marks { margin-bottom: 12px; }
.price-mark { display: flex; align-items: center; gap: 10px; padding: 6px 0; border-bottom: 1px solid #334155; flex-wrap: wrap; }
.price-mark:last-child { border-bottom: none; }
.mark-label { padding: 2px 10px; border-radius: 4px; font-size: 12px; font-weight: 500; }
.mark-target_buy { background: #064e3b; color: #34d399; }
.mark-stop_loss { background: #7f1d1d; color: #f87171; }
.mark-take_profit { background: #1e3a5f; color: #60a5fa; }
.mark-add { background: #064e3b; color: #34d399; }
.mark-reduce { background: #7f1d1d; color: #f87171; }
.mark-mark { background: #334155; color: #94a3b8; }
.mark-price { font-size: 14px; font-weight: 600; }
.mark-diff { font-size: 12px; font-weight: 500; }
.up { color: #f87171; }
.down { color: #34d399; }

.section-header { margin-bottom: 12px; }
.section-header h3 { margin: 0; }

.preset-labels { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.preset-label { display: inline-block; padding: 4px 12px; border-radius: 6px; background: #1e293b; color: #94a3b8; font-size: 12px; cursor: pointer; border: 1px solid #334155; transition: all 0.15s; }
.preset-label:hover { background: #334155; color: #e2e8f0; }
.add-mark-row { display: flex; gap: 8px; align-items: center; }

.price-input-group { display: flex; align-items: center; gap: 4px; }
.price-shortcut { padding: 2px 6px; font-size: 12px; border-radius: 4px; }

/* Notes */
.notes-card { margin-top: 0; }
.note-input { display: flex; gap: 10px; margin-bottom: 16px; }
.note-input textarea { flex: 1; resize: vertical; }
.notes-list { max-height: 400px; overflow-y: auto; }
.note-item { padding: 12px 0; border-bottom: 1px solid #334155; }
.note-time { font-size: 12px; color: #64748b; margin-bottom: 4px; }
.note-content { font-size: 14px; line-height: 1.6; white-space: pre-wrap; }

/* Briefs */
.briefs-card { margin-top: 0; }
.briefs-header { display: flex; justify-content: space-between; align-items: center; cursor: pointer; padding-bottom: 14px; transition: background 0.15s; }
.briefs-header:hover { background: #1e293b; }
.briefs-title { display: flex; align-items: center; gap: 12px; pointer-events: none; }
.briefs-icon { font-size: 22px; }
.briefs-count { font-size: 12px; color: #64748b; margin-top: 2px; }
.briefs-content { padding-top: 4px; }
.briefs-timeline { position: relative; padding-left: 16px; }
.briefs-timeline::before {
  content: '';
  position: absolute;
  left: 5px;
  top: 4px;
  bottom: 4px;
  width: 1px;
  background: #334155;
}
.brief-item { position: relative; margin-bottom: 16px; padding-left: 12px; }
.brief-item:last-child { margin-bottom: 0; }
.brief-date-line { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; position: relative; }
.brief-dot { width: 7px; height: 7px; border-radius: 50%; background: #64748b; position: absolute; left: -14px; top: 6px; flex-shrink: 0; }
.brief-date-text { font-size: 13px; color: #94a3b8; font-weight: 500; }
.brief-pct { font-size: 12px; font-weight: 600; }
.brief-body { padding-left: 4px; }
.brief-meta { display: flex; gap: 10px; margin-bottom: 2px; }
.brief-price { font-size: 12px; color: #64748b; }
.brief-text { font-size: 14px; line-height: 1.6; color: #e2e8f0; }
.briefs-more { text-align: center; padding: 10px; font-size: 13px; color: #64748b; cursor: pointer; border-top: 1px dashed #334155; margin-top: 8px; transition: color 0.15s; }
.briefs-more:hover { color: #94a3b8; }

/* Holdings */
.holdings-card { margin-top: 0; }
.holdings-header { display: flex; justify-content: space-between; align-items: center; cursor: pointer; padding-bottom: 14px; transition: background 0.15s; }
.holdings-header:hover { background: #1e293b; }
.holdings-title { display: flex; align-items: center; gap: 12px; pointer-events: none; }
.holdings-icon { font-size: 22px; }
.holdings-count { font-size: 12px; color: #64748b; margin-top: 2px; }
.holdings-content { padding-top: 4px; }
.holdings-summary { background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 10px 14px; margin-bottom: 12px; }
.hs-row { display: flex; align-items: center; gap: 10px; padding: 4px 0; flex-wrap: wrap; }
.hs-label { font-size: 12px; color: #94a3b8; min-width: 40px; }
.hs-value { font-size: 14px; font-weight: 600; color: #e2e8f0; }
.hs-pnl { font-size: 13px; font-weight: 600; }
.trades-table-wrap { overflow-x: auto; }
.trades-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.trades-table th { text-align: left; padding: 8px 10px; border-bottom: 1px solid #334155; color: #94a3b8; font-weight: 500; }
.trades-table td { padding: 8px 10px; border-bottom: 1px solid #1e293b; }
.trades-table tr:last-child td { border-bottom: none; }
.t-profit { color: #fbbf24; font-weight: 600; }

/* Mobile */
@media (max-width: 640px) {
  .add-mark { flex-direction: column; align-items: stretch; gap: 8px; }
  .preset-labels { flex-wrap: wrap; }
  .add-mark-row { flex-direction: column; }
  .add-mark-row input, .add-mark-row select, .add-mark-row button { width: 100% !important; }

  .title-row { flex-direction: column; gap: 10px; }
  .title-row.compact { flex-direction: column; align-items: stretch; }
  .header-main { gap: 6px; }
  .header-name { font-size: 15px; }
  .actions { flex-wrap: wrap; }
  .analysis-header { flex-direction: column; gap: 8px; align-items: stretch; padding-bottom: 12px; }
  .analysis-header button { width: 100%; }
  .header-right { width: 100%; justify-content: space-between; }

  .report-badge-row { gap: 6px; }
  .report-body { font-size: 13px; }
  .report-body h1 { font-size: 16px; }
  .report-body h2 { font-size: 14px; }
  .report-body table { font-size: 11px; }
  .report-body td { padding: 4px 6px; }

  .older-toggle { padding: 10px; font-size: 12px; }
  .tci-header { padding: 10px; font-size: 12px; }
  .tci-body { font-size: 13px; padding: 10px; }

  .note-input { flex-direction: column; }
  .note-input button { width: 100%; }
  .notes-list { max-height: 300px; }
  .price-input-group { flex-wrap: wrap; justify-content: flex-end; }
  .price-shortcut { flex: 1; min-width: 50px; }

  .briefs-header { flex-direction: column; gap: 8px; align-items: stretch; padding-bottom: 12px; }
  .briefs-header button { width: 100%; }
  .briefs-timeline { padding-left: 12px; }
  .brief-item { padding-left: 8px; }
  .brief-text { font-size: 13px; }
  .brief-dot { left: -12px; }
  .mark-diff { font-size: 11px; }

  .info-bar { padding: 10px 12px; }
  .info-price { font-size: 20px; }
}
</style>
