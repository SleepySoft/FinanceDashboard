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
        <!-- Price row -->
        <div class="modal-price-row">
          <span class="modal-price" :class="priceClass(stock.change_pct)">
            {{ stock.last_price != null ? '¥' + stock.last_price.toFixed(2) : '--' }}
          </span>
          <span v-if="stock.change_pct != null" :class="priceClass(stock.change_pct)">
            {{ stock.change_pct > 0 ? '+' : '' }}{{ stock.change_pct.toFixed(2) }}%
          </span>
          <span class="modal-dims">
            <span :class="['dim-badge', 'dim-' + dim('quality')]">质</span>
            <span :class="['dim-badge', 'dim-' + dim('valuation')]">估</span>
            <span :class="['dim-badge', 'dim-' + dim('timing')]">时</span>
            <span :class="['dim-badge', 'dim-' + dim('risk')]">险</span>
          </span>
        </div>
        <!-- Price marks preview -->
        <div v-if="stock.price_marks?.length > 0" class="modal-marks">
          <div v-for="m in stock.price_marks" :key="m.id" class="modal-mark">
            <span :class="['mark-label', 'mark-' + m.type]">{{ m.label }}</span>
            <span>¥{{ m.price.toFixed(2) }}</span>
            <span v-if="m.diff != null" :class="['mark-diff', m.diff >= 0 ? 'up' : 'down']">
              {{ m.diff > 0 ? '+' : '' }}{{ m.diff.toFixed(2) }}
            </span>
          </div>
        </div>

        <!-- Reports -->
        <div v-if="loading" class="loading">加载中...</div>
        <div v-else-if="reports.length > 0" class="modal-reports">
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
        <div v-else class="empty">暂无分析报告</div>

        <!-- Link to full detail -->
        <div class="modal-footer">
          <router-link :to="'/stock/' + stock.code" class="modal-full-link" @click="close">
            打开完整页面 →
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

const loading = ref(false)
const reports = ref([])
const reportContents = ref({})
const expanded = ref([])

watch(() => props.show, async (visible) => {
  if (!visible) {
    reports.value = []
    reportContents.value = {}
    expanded.value = []
    return
  }
  const code = props.stock.code
  if (!code) return
  loading.value = true
  try {
    // Get full stock data which includes reports
    const data = await api.stocks.get(code)
    const reps = (data.reports || [])
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
      .slice(0, 3) // Show latest 3 reports in modal
    reports.value = reps
    expanded.value = reps.map((_, i) => i === 0) // Expand first by default
    // Load content for expanded reports
    for (let i = 0; i < reps.length; i++) {
      if (expanded.value[i]) {
        await loadReportContent(reps[i].id)
      }
    }
  } catch (e) {
    console.error('加载报告失败', e)
  } finally {
    loading.value = false
  }
})

async function loadReportContent(id) {
  if (reportContents.value[id]) return
  try {
    const data = await api.stocks.getReport(props.stock.code, id)
    reportContents.value[id] = data.content || ''
  } catch (e) {
    reportContents.value[id] = '加载失败'
  }
}

async function toggleReport(idx) {
  expanded.value[idx] = !expanded.value[idx]
  if (expanded.value[idx] && reports.value[idx]) {
    await loadReportContent(reports.value[idx].id)
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
  const d = props.stock.dimensions || props.stock.tags || {}
  return d[key] || 'none'
}

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
  width: 100%; max-width: 680px; max-height: 85vh;
  display: flex; flex-direction: column;
  overflow: hidden;
}
.modal-content.mobile {
  max-width: 100%; max-height: 100%; border-radius: 0;
}
.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px; border-bottom: 1px solid #334155;
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
.modal-body { padding: 16px 20px; overflow-y: auto; flex: 1; }
.modal-price-row {
  display: flex; align-items: baseline; gap: 10px; margin-bottom: 12px; flex-wrap: wrap;
}
.modal-price { font-size: 28px; font-weight: 700; }
.modal-dims { display: flex; gap: 6px; margin-left: auto; }
.dim-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }
.dim-green { background: #064e3b; color: #34d399; }
.dim-yellow { background: #713f12; color: #fbbf24; }
.dim-red { background: #7f1d1d; color: #f87171; }
.dim-none { background: #334155; color: #64748b; }
.modal-marks { margin-bottom: 16px; }
.modal-mark { display: flex; align-items: center; gap: 10px; padding: 4px 0; font-size: 13px; }
.mark-label { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }
.mark-target_buy { background: #064e3b; color: #34d399; }
.mark-stop_loss { background: #7f1d1d; color: #f87171; }
.mark-take_profit { background: #1e3a5f; color: #60a5fa; }
.mark-add { background: #064e3b; color: #34d399; }
.mark-reduce { background: #7f1d1d; color: #f87171; }
.mark-mark { background: #334155; color: #94a3b8; }
.up { color: #f87171; }
.down { color: #34d399; }

/* Reports */
.loading { text-align: center; color: #64748b; font-size: 13px; padding: 20px 0; }
.empty { text-align: center; color: #475569; font-size: 13px; padding: 20px 0; }
.modal-reports { margin-bottom: 16px; }
.report-section {
  border: 1px solid #334155;
  border-radius: 8px;
  margin-bottom: 10px;
  overflow: hidden;
}
.report-header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: #0f172a;
  cursor: pointer;
  transition: background 0.15s;
}
.report-header-bar:hover { background: #1e293b; }
.report-meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.report-badge { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 500; }
.badge-full { background: #14532d; color: #34d399; }
.badge-fundamental { background: #1e3a5f; color: #60a5fa; }
.badge-technical { background: #3f2c1d; color: #fbbf24; }
.report-time { font-size: 12px; color: #94a3b8; }
.report-latest-tag { font-size: 11px; padding: 1px 6px; border-radius: 4px; background: #3b82f6; color: white; font-weight: 500; }
.collapse-btn { font-size: 13px; color: #64748b; }
.report-body {
  padding: 14px 16px;
  font-size: 14px;
  line-height: 1.8;
  background: #0b1220;
}
.report-body h1 { font-size: 17px; font-weight: 700; margin: 14px 0 10px; color: #e2e8f0; }
.report-body h2 { font-size: 14px; font-weight: 600; margin: 12px 0 8px; color: #94a3b8; border-bottom: 1px solid #334155; padding-bottom: 4px; }
.report-body h3 { font-size: 13px; font-weight: 600; margin: 10px 0 6px; color: #60a5fa; }
.report-body strong { color: #e2e8f0; }
.report-body table { width: 100%; margin: 10px 0; font-size: 12px; }
.report-body td { padding: 5px 8px; border: 1px solid #334155; }
.report-body tr:first-child td { background: #1e293b; font-weight: 600; }

.modal-footer { text-align: center; padding-top: 12px; border-top: 1px solid #334155; }
.modal-full-link {
  color: #60a5fa; text-decoration: none; font-size: 14px;
}
.modal-full-link:hover { color: #93c5fd; }
</style>
