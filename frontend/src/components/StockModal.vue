<template>
  <div v-if="show" class="modal-overlay" @click.self="close">
    <div class="modal-content" :class="{ mobile: isMobile }">
      <!-- Header -->
      <div class="modal-header">
        <div class="modal-title-row">
          <span class="modal-code">{{ stock.code }}</span>
          <span class="modal-name">{{ stock.name }}</span>
          <span v-if="stock.sector" class="modal-sector">· {{ stock.sector }}</span>
        </div>
        <button class="modal-close" @click="close">✕</button>
      </div>

      <div class="modal-body">
        <!-- Info Bar -->
        <div class="info-bar card">
          <div class="info-main">
            <span class="info-price" :class="priceClass(full.change_pct)">
              {{ full.last_price != null ? '¥' + full.last_price.toFixed(2) : '--' }}
            </span>
            <span v-if="full.change_pct != null" class="info-pct" :class="priceClass(full.change_pct)">
              {{ full.change_pct > 0 ? '+' : '' }}{{ full.change_pct.toFixed(2) }}%
            </span>
            <span :class="['status-tag', 'status-' + (full.status || 'neutral')]">
              {{ statusLabel(full.status) }}
            </span>
            <span v-if="full.tags?.watchlist" class="watch-tag">已关注</span>
          </div>
          <div class="info-dims">
            <span :class="['dim-badge', 'dim-' + dim('quality')]">质</span>
            <span :class="['dim-badge', 'dim-' + dim('valuation')]">估</span>
            <span :class="['dim-badge', 'dim-' + dim('timing')]">时</span>
            <span :class="['dim-badge', 'dim-' + dim('risk')]">险</span>
            <span :class="['verdict-badge', 'verdict-' + (full.dimensions?.verdict || full.overall)]">
              {{ verdictLabel }}
            </span>
          </div>
        </div>

        <div v-if="loading" class="loading">加载中...</div>

        <template v-else>
          <!-- Fundamental Analysis -->
          <div class="analysis-card card">
            <div class="analysis-header" @click="showFund = !showFund">
              <div class="analysis-title">
                <span class="analysis-icon">📊</span>
                <div>
                  <h3>基本面分析</h3>
                  <p class="analysis-status" :class="{ expired: isExpired(full.last_analysis) }">
                    {{ fundamentalStatus }}
                  </p>
                </div>
              </div>
              <span class="collapse-btn">{{ showFund ? '▼' : '▶' }}</span>
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
                      <div class="tci-body" v-show="fundExpandedIndex === idx + 1" v-html="renderMarkdown(fundVersionContents[r.id] || '')"></div>
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
                  <p class="analysis-status" :class="{ expired: isExpired(full.last_analysis) }">
                    {{ technicalStatus }}
                  </p>
                </div>
              </div>
              <span class="collapse-btn">{{ showTech ? '▼' : '▶' }}</span>
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
                      <div class="tci-body" v-show="techExpandedIndex === idx + 1" v-html="renderMarkdown(techVersionContents[r.id] || '')"></div>
                    </div>
                  </div>
                </div>
              </div>
              <div class="empty" v-else>暂无技术面分析报告</div>
            </div>
          </div>

          <!-- Price Marks -->
          <div class="analysis-card card" v-if="full.price_marks?.length > 0">
            <div class="analysis-header" @click="showMarks = !showMarks">
              <div class="analysis-title">
                <span class="analysis-icon">📌</span>
                <h3>价格标记</h3>
              </div>
              <span class="collapse-btn">{{ showMarks ? '▼' : '▶' }}</span>
            </div>
            <div class="analysis-content" v-show="showMarks">
              <div class="marks-list">
                <div v-for="m in full.price_marks" :key="m.id" class="mark-row">
                  <span :class="['mark-label', 'mark-' + m.type]">{{ m.label }}</span>
                  <span class="mark-price">¥{{ m.price.toFixed(2) }}</span>
                  <span v-if="full.last_price != null" :class="['mark-diff', diffClass(full.last_price - m.price)]">
                    {{ full.last_price >= m.price ? '+' : '' }}{{ (full.last_price - m.price).toFixed(2) }}
                    ({{ ((full.last_price - m.price) / m.price * 100).toFixed(1) }}%)
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- Daily Briefs -->
          <div class="analysis-card card" v-if="briefs.length > 0">
            <div class="analysis-header" @click="showBriefs = !showBriefs">
              <div class="analysis-title">
                <span class="analysis-icon">📋</span>
                <h3>交易日简评</h3>
              </div>
              <span class="collapse-btn">{{ showBriefs ? '▼' : '▶' }}</span>
            </div>
            <div class="analysis-content" v-show="showBriefs">
              <div class="briefs-list">
                <div v-for="b in briefs.slice(0, 5)" :key="b.id" class="brief-item">
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
          </div>

          <!-- Notes -->
          <div class="analysis-card card" v-if="notes.length > 0">
            <div class="analysis-header" @click="showNotes = !showNotes">
              <div class="analysis-title">
                <span class="analysis-icon">📝</span>
                <h3>随想笔记</h3>
              </div>
              <span class="collapse-btn">{{ showNotes ? '▼' : '▶' }}</span>
            </div>
            <div class="analysis-content" v-show="showNotes">
              <div class="notes-list">
                <div v-for="n in notes.slice(0, 5)" :key="n.time" class="note-item">
                  <div class="note-time">{{ n.time }}</div>
                  <div class="note-content">{{ n.content }}</div>
                </div>
              </div>
            </div>
          </div>
        </template>

        <!-- Footer -->
        <div class="modal-footer">
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
const showFund = ref(true)
const showTech = ref(true)
const showMarks = ref(true)
const showBriefs = ref(true)
const showNotes = ref(true)
const showFundHistory = ref(false)
const showTechHistory = ref(false)
const fundExpandedIndex = ref(0)
const techExpandedIndex = ref(0)
const fundVersionContents = ref({})
const techVersionContents = ref({})
const briefs = ref([])
const notes = ref([])

const fundamentalReports = computed(() => {
  return (full.value.reports || [])
    .filter(r => r.type === 'fundamental' || r.type === 'full')
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
})

const technicalReports = computed(() => {
  return (full.value.reports || [])
    .filter(r => r.type === 'technical' || r.type === 'full')
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
})

const fundamentalContent = computed(() => {
  const r = fundamentalReports.value[0]
  return r ? (fundVersionContents.value[r.id] || '') : ''
})

const technicalContent = computed(() => {
  const r = technicalReports.value[0]
  return r ? (techVersionContents.value[r.id] || '') : ''
})

const fundamentalStatus = computed(() => {
  const r = fundamentalReports.value[0]
  return r ? `最新: ${fmtDateTime(r.created_at)}` : '暂无报告'
})

const technicalStatus = computed(() => {
  const r = technicalReports.value[0]
  return r ? `最新: ${fmtDateTime(r.created_at)}` : '暂无报告'
})

watch(() => props.show, async (visible) => {
  if (!visible) {
    full.value = {}
    briefs.value = []
    notes.value = []
    fundVersionContents.value = {}
    techVersionContents.value = {}
    return
  }
  const code = props.stock.code
  if (!code) return
  loading.value = true
  try {
    const data = await api.stocks.get(code)
    full.value = data

    // Load latest fundamental content
    const fr = fundamentalReports.value[0]
    if (fr) {
      const d = await api.stocks.getReport(code, fr.id)
      fundVersionContents.value[fr.id] = d.content || ''
    }

    // Load latest technical content
    const tr = technicalReports.value[0]
    if (tr) {
      const d = await api.stocks.getReport(code, tr.id)
      techVersionContents.value[tr.id] = d.content || ''
    }

    // Briefs
    briefs.value = (data.daily_briefs || [])
      .sort((a, b) => b.date.localeCompare(a.date))

    // Notes
    const n = await api.stocks.getNotes(code)
    notes.value = (n.notes || [])
  } catch (e) {
    console.error('加载详情失败', e)
  } finally {
    loading.value = false
  }
})

async function toggleFundVersion(idx) {
  fundExpandedIndex.value = fundExpandedIndex.value === idx ? -1 : idx
  const r = fundamentalReports.value[idx]
  if (r && !fundVersionContents.value[r.id]) {
    try {
      const d = await api.stocks.getReport(props.stock.code, r.id)
      fundVersionContents.value[r.id] = d.content || ''
    } catch (e) {
      fundVersionContents.value[r.id] = '加载失败'
    }
  }
}

async function toggleTechVersion(idx) {
  techExpandedIndex.value = techExpandedIndex.value === idx ? -1 : idx
  const r = technicalReports.value[idx]
  if (r && !techVersionContents.value[r.id]) {
    try {
      const d = await api.stocks.getReport(props.stock.code, r.id)
      techVersionContents.value[r.id] = d.content || ''
    } catch (e) {
      techVersionContents.value[r.id] = '加载失败'
    }
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

function isExpired(iso) {
  return iso && (Date.now() - new Date(iso).getTime()) > 7 * 86400000
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
  background: #0f172a; border: 1px solid #334155; border-radius: 12px;
  width: 100%; max-width: 760px; max-height: 92vh;
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
  padding: 14px 18px;
  overflow-y: auto;
  overflow-x: hidden;
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* Info bar */
.info-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  gap: 10px;
  flex-wrap: wrap;
}
.info-main { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.info-price { font-size: 24px; font-weight: 700; }
.info-pct { font-size: 13px; font-weight: 500; }
.status-tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }
.status-tracking { background: #1e3a5f; color: #60a5fa; }
.status-bullish { background: #064e3b; color: #34d399; }
.status-neutral { background: #713f12; color: #fbbf24; }
.status-avoid { background: #7f1d1d; color: #f87171; }
.status-archive { background: #334155; color: #94a3b8; }
.watch-tag { display: inline-block; padding: 1px 6px; border-radius: 4px; background: #fbbf24; color: #1e293b; font-size: 10px; font-weight: 600; }
.info-dims { display: flex; gap: 4px; flex-wrap: wrap; }

/* Analysis cards */
.analysis-card { overflow: hidden; }
.analysis-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  cursor: pointer;
  transition: background 0.15s;
}
.analysis-header:hover { background: #1e293b; }
.analysis-title { display: flex; align-items: center; gap: 10px; }
.analysis-title h3 { font-size: 14px; font-weight: 600; margin: 0; color: #e2e8f0; }
.analysis-icon { font-size: 16px; }
.analysis-status { font-size: 11px; color: #64748b; margin: 2px 0 0; }
.analysis-status.expired { color: #f87171; }
.collapse-btn { font-size: 12px; color: #64748b; }
.analysis-content { padding: 0 14px 14px; }

/* Dim badges */
.dim-badge { display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.dim-green { background: #064e3b; color: #34d399; }
.dim-yellow { background: #713f12; color: #fbbf24; }
.dim-red { background: #7f1d1d; color: #f87171; }
.dim-none { background: #334155; color: #64748b; }
.verdict-badge { display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.verdict-green { background: #064e3b; color: #34d399; }
.verdict-yellow { background: #713f12; color: #fbbf24; }
.verdict-red { background: #7f1d1d; color: #f87171; }
.verdict-none { background: #334155; color: #64748b; }

/* Report body */
.report-latest { margin-bottom: 10px; }
.report-badge-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.timeline-badge { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 500; }
.badge-full { background: #14532d; color: #34d399; }
.badge-fund { background: #1e3a5f; color: #60a5fa; }
.badge-tech { background: #3f2c1d; color: #fbbf24; }
.report-time { font-size: 11px; color: #94a3b8; }
.timeline-latest { font-size: 10px; padding: 1px 5px; border-radius: 3px; background: #3b82f6; color: white; font-weight: 500; }

.report-body {
  font-size: 13px;
  line-height: 1.7;
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

/* Older versions */
.older-versions { margin-top: 12px; padding-top: 10px; border-top: 1px dashed #334155; }
.older-toggle { font-size: 12px; color: #64748b; cursor: pointer; padding: 6px 0; }
.older-toggle:hover { color: #94a3b8; }
.timeline-collapsed { display: flex; flex-direction: column; gap: 8px; }
.timeline-collapsed-item { padding: 8px 10px; background: #0f172a; border-radius: 6px; cursor: pointer; }
.tci-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.tci-dot { width: 6px; height: 6px; border-radius: 50%; background: #3b82f6; }
.tci-time { font-size: 12px; color: #94a3b8; }
.tci-body { margin-top: 8px; padding-top: 8px; border-top: 1px solid #334155; }

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
.note-item { padding: 10px 12px; background: #0f172a; border-radius: 6px; }
.note-time { font-size: 11px; color: #64748b; margin-bottom: 3px; }
.note-content { font-size: 13px; line-height: 1.5; color: #e2e8f0; white-space: pre-wrap; }

/* Footer */
.modal-footer { text-align: center; padding: 14px 0 4px; }
.btn-primary {
  display: inline-block;
  padding: 8px 20px;
  background: #1e3a5f;
  color: #60a5fa;
  border-radius: 6px;
  text-decoration: none;
  font-size: 13px;
  font-weight: 500;
}
.btn-primary:hover { background: #2563eb; color: white; }

/* Common */
.up { color: #f87171; }
.down { color: #34d399; }
.empty { text-align: center; color: #475569; font-size: 13px; padding: 12px 0; }
.loading { text-align: center; color: #64748b; font-size: 13px; padding: 20px 0; }

/* Mobile */
@media (max-width: 640px) {
  .modal-overlay { padding: 0; }
  .modal-content { border-radius: 0; max-height: 100vh; max-width: 100vw; }
  .modal-body { padding: 10px 12px; gap: 10px; }
  .modal-header { padding: 12px 14px; }
  .info-bar { padding: 10px 12px; }
  .info-price { font-size: 20px; }
  .analysis-content { padding: 0 12px 12px; }
  .analysis-header { padding: 10px 12px; }
  .report-body { font-size: 12px; }
  .report-body h1 { font-size: 14px; }
  .report-body h2 { font-size: 12px; }
  .report-body table { font-size: 10px; }
  .brief-text { font-size: 12px; }
  .note-content { font-size: 12px; }
  .modal-footer { padding: 10px 0 0; }
}
</style>
