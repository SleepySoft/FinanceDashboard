<template>
  <div v-if="show" class="modal-overlay" @click.self="close">
    <div class="modal-content" :class="{ mobile: isMobile }">
      <div class="modal-header">
        <div class="modal-title-row">
          <span class="modal-code">{{ stock.code }}</span>
          <span class="modal-name">{{ stock.name }}</span>
          <span v-if="stock.sector" class="modal-sector">· {{ stock.sector }}</span>
        </div>
        <button class="modal-close" @click="close">✕</button>
      </div>

      <div class="modal-body">
        <!-- Price & Status Row -->
        <div class="top-bar">
          <div class="price-block">
            <span class="modal-price" :class="priceClass(full.change_pct)">
              {{ full.last_price != null ? '¥' + full.last_price.toFixed(2) : '--' }}
            </span>
            <span v-if="full.change_pct != null" class="price-pct" :class="priceClass(full.change_pct)">
              {{ full.change_pct > 0 ? '+' : '' }}{{ full.change_pct.toFixed(2) }}%
            </span>
          </div>
          <div class="status-block">
            <span :class="['status-badge', 'status-' + (full.status || 'neutral')]">
              {{ statusLabel(full.status) }}
            </span>
            <span v-if="full.tags?.watchlist" class="watch-badge">已关注</span>
          </div>
          <div class="modal-dims">
            <span :class="['dim-badge', 'dim-' + dim('quality')]">质</span>
            <span :class="['dim-badge', 'dim-' + dim('valuation')]">估</span>
            <span :class="['dim-badge', 'dim-' + dim('timing')]">时</span>
            <span :class="['dim-badge', 'dim-' + dim('risk')]">险</span>
            <span :class="['verdict-badge', 'verdict-' + (full.dimensions?.verdict || full.overall)]">
              {{ verdictLabel }}
            </span>
          </div>
        </div>

        <!-- Price Marks -->
        <div v-if="full.price_marks?.length > 0" class="section">
          <div class="section-title">📌 价格标记</div>
          <div class="marks-list">
            <div v-for="m in full.price_marks" :key="m.id" class="mark-row">
              <span :class="['mark-label', 'mark-' + m.type]">{{ m.label }}</span>
              <span class="mark-price">¥{{ m.price.toFixed(2) }}</span>
              <span v-if="full.last_price != null" :class="['mark-diff', diffClass(full.last_price - m.price)]">
                {{ full.last_price >= m.price ? '+' : '' }}{{ (full.last_price - m.price).toFixed(2) }}
                ({{ full.last_price >= m.price ? '+' : '' }}{{ ((full.last_price - m.price) / m.price * 100).toFixed(1) }}%)
              </span>
            </div>
          </div>
        </div>

        <!-- Reports -->
        <div v-if="loading" class="loading">加载中...</div>
        <div v-else-if="reports.length > 0" class="section">
          <div class="section-title">📊 分析报告</div>
          <div class="report-list">
            <div
              v-for="(r, idx) in reports"
              :key="r.id"
              class="report-section"
            >
              <div class="report-header-bar" @click="toggleReport(idx)">
                <div class="report-meta">
                  <span :class="['report-badge', 'badge-' + r.type]">{{ badgeText(r.type) }}</span>
                  <span class="report-time">{{ fmtDateTime(r.created_at) }}</span>
                  <span v-if="idx === 0" class="report-latest-tag">最新</span>
                </div>
                <span class="collapse-btn">{{ expanded[idx] ? '▼' : '▶' }}</span>
              </div>
              <div v-show="expanded[idx]" class="report-body" v-html="renderMarkdown(reportContents[r.id])"></div>
            </div>
          </div>
        </div>

        <!-- Daily Briefs -->
        <div v-if="briefs.length > 0" class="section">
          <div class="section-title">📋 交易日简评</div>
          <div class="briefs-list">
            <div v-for="b in displayBriefs" :key="b.id" class="brief-item">
              <div class="brief-header">
                <span class="brief-date">{{ b.date }}</span>
                <span :class="['brief-pct', b.change_pct > 0 ? 'up' : 'down']">
                  {{ b.change_pct > 0 ? '+' : '' }}{{ b.change_pct?.toFixed(2) }}%
                </span>
                <span class="brief-price">收 ¥{{ b.price?.toFixed(2) }}</span>
              </div>
              <div class="brief-text">{{ b.content }}</div>
            </div>
          </div>
        </div>

        <!-- Notes -->
        <div v-if="notes.length > 0" class="section">
          <div class="section-title">📝 随想笔记</div>
          <div class="notes-list">
            <div v-for="n in notes.slice(0, 5)" :key="n.time" class="note-item">
              <div class="note-time">{{ n.time }}</div>
              <div class="note-content">{{ n.content }}</div>
            </div>
          </div>
        </div>

        <!-- Actions -->
        <div class="modal-actions">
          <router-link :to="'/stock/' + stock.code" class="btn-primary" @click="close">
            进入完整页面 →
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import api from '../api.js'

const props = defineProps({
  show: Boolean,
  stock: { type: Object, default: () => ({}) }
})
const emit = defineEmits(['close'])

const isMobile = computed(() => window.innerWidth <= 768)

const full = ref({})
const loading = ref(false)
const reports = ref([])
const reportContents = ref({})
const expanded = ref([])
const briefs = ref([])
const notes = ref([])

watch(() => props.show, async (visible) => {
  if (!visible) {
    full.value = {}
    reports.value = []
    reportContents.value = {}
    expanded.value = []
    briefs.value = []
    notes.value = []
    return
  }
  const code = props.stock.code
  if (!code) return
  loading.value = true
  try {
    const data = await api.stocks.get(code)
    full.value = data
    // Reports
    const reps = (data.reports || [])
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
      .slice(0, 3)
    reports.value = reps
    expanded.value = reps.map((_, i) => i === 0)
    for (let i = 0; i < reps.length; i++) {
      if (expanded.value[i]) {
        await loadReportContent(code, reps[i].id)
      }
    }
    // Briefs
    briefs.value = (data.daily_briefs || [])
      .sort((a, b) => b.date.localeCompare(a.date))
      .slice(0, 3)
    // Notes
    const n = await api.stocks.getNotes(code)
    notes.value = (n.notes || []).slice(0, 5)
  } catch (e) {
    console.error('加载详情失败', e)
  } finally {
    loading.value = false
  }
})

async function loadReportContent(code, id) {
  if (reportContents.value[id]) return
  try {
    const data = await api.stocks.getReport(code, id)
    reportContents.value[id] = data.content || ''
  } catch (e) {
    reportContents.value[id] = '加载失败'
  }
}

async function toggleReport(idx) {
  expanded.value[idx] = !expanded.value[idx]
  if (expanded.value[idx] && reports.value[idx]) {
    await loadReportContent(props.stock.code, reports.value[idx].id)
  }
}

function close() {
  emit('close')
}

function priceClass(pct) {
  if (pct == null) return ''
  return pct >= 0 ? 'up' : 'down'
}

function dim(key) {
  const d = full.value.dimensions || full.value.tags || {}
  return d[key] || 'none'
}

function diffClass(diff) {
  return diff >= 0 ? 'up' : 'down'
}

function statusLabel(status) {
  const map = { tracking: '🔭 跟踪中', bullish: '看好', neutral: '观望', avoid: '回避', archive: '📁 归档' }
  return map[status] || '观望'
}

const verdictLabel = computed(() => {
  const v = full.value.dimensions?.verdict || full.value.overall
  const map = { green: '看好', yellow: '观望', red: '回避', none: '-' }
  return map[v] || '-'
})

const displayBriefs = computed(() => briefs.value.slice(0, 3))

function badgeText(type) {
  const map = { full: '综合', fundamental: '基本面', technical: '技术面' }
  return map[type] || type
}

function fmtDateTime(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
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
</script>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(0,0,0,0.7);
  display: flex; justify-content: center; align-items: center;
  padding: 16px;
}
.modal-content {
  background: #151e2e; border: 1px solid #334155; border-radius: 12px;
  width: 100%; max-width: 720px; max-height: 90vh;
  display: flex; flex-direction: column;
  overflow: hidden;
  box-sizing: border-box;
  min-width: 0;
}
.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 18px; border-bottom: 1px solid #334155;
  flex-shrink: 0;
}
.modal-title-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.modal-code { font-size: 14px; font-weight: 600; color: #60a5fa; }
.modal-name { font-size: 16px; font-weight: 600; color: #e2e8f0; }
.modal-sector { font-size: 12px; color: #64748b; }
.modal-close {
  background: transparent; color: #94a3b8; border: none;
  font-size: 20px; padding: 4px 8px; cursor: pointer;
}
.modal-close:hover { color: #e2e8f0; }

.modal-body {
  padding: 16px 18px;
  overflow-y: auto;
  overflow-x: hidden;
  flex: 1;
  min-width: 0;
}

/* Top bar */
.top-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid #334155;
}
.price-block { display: flex; align-items: baseline; gap: 8px; }
.modal-price { font-size: 26px; font-weight: 700; }
.price-pct { font-size: 14px; font-weight: 500; }
.status-block { display: flex; gap: 6px; align-items: center; }
.status-badge {
  display: inline-block; padding: 3px 10px; border-radius: 4px;
  font-size: 12px; font-weight: 500;
}
.status-tracking { background: #1e3a5f; color: #60a5fa; }
.status-bullish { background: #064e3b; color: #34d399; }
.status-neutral { background: #713f12; color: #fbbf24; }
.status-avoid { background: #7f1d1d; color: #f87171; }
.status-archive { background: #334155; color: #94a3b8; }
.watch-badge {
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  background: #fbbf24; color: #1e293b; font-size: 11px; font-weight: 600;
}
.modal-dims { display: flex; gap: 5px; margin-left: auto; flex-wrap: wrap; }
.dim-badge { display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.dim-green { background: #064e3b; color: #34d399; }
.dim-yellow { background: #713f12; color: #fbbf24; }
.dim-red { background: #7f1d1d; color: #f87171; }
.dim-none { background: #334155; color: #64748b; }
.verdict-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.verdict-green { background: #064e3b; color: #34d399; }
.verdict-yellow { background: #713f12; color: #fbbf24; }
.verdict-red { background: #7f1d1d; color: #f87171; }
.verdict-none { background: #334155; color: #64748b; }

/* Sections */
.section { margin-bottom: 16px; }
.section-title { font-size: 13px; font-weight: 600; color: #94a3b8; margin-bottom: 8px; }

/* Price marks */
.marks-list { display: flex; flex-direction: column; gap: 6px; }
.mark-row {
  display: flex; align-items: center; gap: 10px;
  padding: 6px 10px; background: #0f172a; border-radius: 6px;
  font-size: 13px; flex-wrap: wrap;
}
.mark-label { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }
.mark-target_buy { background: #064e3b; color: #34d399; }
.mark-stop_loss { background: #7f1d1d; color: #f87171; }
.mark-take_profit { background: #1e3a5f; color: #60a5fa; }
.mark-add { background: #064e3b; color: #34d399; }
.mark-reduce { background: #7f1d1d; color: #f87171; }
.mark-mark { background: #334155; color: #94a3b8; }
.mark-price { font-weight: 600; }
.mark-diff { font-size: 12px; }

/* Loading / Empty */
.loading { text-align: center; color: #64748b; font-size: 13px; padding: 20px 0; }

/* Reports */
.report-list { display: flex; flex-direction: column; gap: 8px; }
.report-section {
  border: 1px solid #334155;
  border-radius: 8px;
  overflow: hidden;
}
.report-header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: #0f172a;
  cursor: pointer;
  transition: background 0.15s;
}
.report-header-bar:hover { background: #1e293b; }
.report-meta { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.report-badge { font-size: 11px; padding: 2px 7px; border-radius: 4px; font-weight: 500; }
.badge-full { background: #14532d; color: #34d399; }
.badge-fundamental { background: #1e3a5f; color: #60a5fa; }
.badge-technical { background: #3f2c1d; color: #fbbf24; }
.report-time { font-size: 11px; color: #94a3b8; }
.report-latest-tag { font-size: 10px; padding: 1px 5px; border-radius: 3px; background: #3b82f6; color: white; font-weight: 500; }
.collapse-btn { font-size: 12px; color: #64748b; }
.report-body {
  padding: 12px 14px;
  font-size: 13px;
  line-height: 1.7;
  background: #0b1220;
  overflow-wrap: break-word;
  word-break: break-word;
  min-width: 0;
}
.report-body h1 { font-size: 16px; font-weight: 700; margin: 12px 0 8px; color: #e2e8f0; }
.report-body h2 { font-size: 13px; font-weight: 600; margin: 10px 0 6px; color: #94a3b8; border-bottom: 1px solid #334155; padding-bottom: 3px; }
.report-body h3 { font-size: 12px; font-weight: 600; margin: 8px 0 4px; color: #60a5fa; }
.report-body strong { color: #e2e8f0; }
.report-body table { width: 100%; margin: 8px 0; font-size: 11px; table-layout: fixed; display: block; overflow-x: auto; }
.report-body td { padding: 4px 6px; border: 1px solid #334155; word-break: break-all; }
.report-body tr:first-child td { background: #1e293b; font-weight: 600; }

/* Briefs */
.briefs-list { display: flex; flex-direction: column; gap: 8px; }
.brief-item {
  padding: 10px 12px; background: #0f172a; border-radius: 6px;
  border-left: 3px solid #334155;
}
.brief-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 4px; }
.brief-date { font-size: 12px; color: #94a3b8; font-weight: 500; }
.brief-pct { font-size: 12px; font-weight: 600; }
.brief-price { font-size: 11px; color: #64748b; margin-left: auto; }
.brief-text { font-size: 13px; line-height: 1.6; color: #e2e8f0; }

/* Notes */
.notes-list { display: flex; flex-direction: column; gap: 8px; }
.note-item {
  padding: 10px 12px; background: #0f172a; border-radius: 6px;
}
.note-time { font-size: 11px; color: #64748b; margin-bottom: 3px; }
.note-content { font-size: 13px; line-height: 1.5; color: #e2e8f0; white-space: pre-wrap; }

/* Actions */
.modal-actions {
  padding-top: 14px;
  border-top: 1px solid #334155;
  text-align: center;
}
.btn-primary {
  display: inline-block;
  padding: 8px 20px;
  background: #1e3a5f;
  color: #60a5fa;
  border-radius: 6px;
  text-decoration: none;
  font-size: 13px;
  font-weight: 500;
  transition: background 0.15s;
}
.btn-primary:hover { background: #2563eb; color: white; }

/* Common */
.up { color: #f87171; }
.down { color: #34d399; }

/* Mobile */
@media (max-width: 640px) {
  .modal-overlay { padding: 0; }
  .modal-content { border-radius: 0; max-height: 100vh; max-width: 100vw; }
  .modal-body { padding: 12px 14px; }
  .modal-header { padding: 12px 14px; }
  .top-bar { gap: 8px; margin-bottom: 12px; padding-bottom: 10px; }
  .modal-price { font-size: 22px; }
  .modal-dims { margin-left: 0; }
  .section { margin-bottom: 12px; }
  .report-body { padding: 10px 12px; font-size: 12px; }
  .report-body h1 { font-size: 14px; }
  .report-body h2 { font-size: 12px; }
  .report-body table { font-size: 10px; }
  .report-header-bar { padding: 8px 10px; }
  .brief-text { font-size: 12px; }
  .note-content { font-size: 12px; }
}
</style>
