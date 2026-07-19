<template>
  <div class="dashboard">
    <div class="dash-header">
      <h1>Dashboard</h1>
      <div class="dash-actions">
        <button class="primary" @click="$router.push('/requests')">+ 提交分析请求</button>
        <button class="ghost" @click="refreshPrices" :disabled="loading">{{ loading ? '刷新中...' : '刷新价格' }}</button>
      </div>
    </div>
    <div v-if="lastRefresh" class="refresh-info">
      价格更新于 {{ fmtTime(lastRefresh) }} · 自动刷新每30秒
    </div>

    <!-- Loading -->
    <div v-if="loading && stocks.length === 0" class="card empty">加载中...</div>

    <!-- By Tag Groups -->
    <div v-for="group in tagGroups" :key="group.key" class="tag-group">
      <div class="tag-group-header">
        <span :class="['tag-badge', 'tag-' + group.key]">{{ group.label }}</span>
        <span class="tag-count">{{ group.stocks.length }} 只</span>
      </div>
      <div class="stock-grid">
        <div
          v-for="s in group.stocks"
          :key="s.code"
          class="stock-card card"
          @click="$router.push('/stock/' + s.code)"
        >
          <div class="stock-main">
            <div class="stock-title-row">
              <span class="stock-code">{{ s.code }}</span>
              <span class="stock-name">{{ s.name }}</span>
              <span v-if="s.watchlist" class="tag-badge tag-watch">关注</span>
            </div>
            <div class="stock-price-row">
              <span class="price-current" :class="priceClass(s.change_pct)">
                {{ s.last_price != null ? '¥' + s.last_price.toFixed(2) : '--' }}
              </span>
              <span v-if="s.change_pct != null" class="price-change" :class="priceClass(s.change_pct)">
                {{ s.change_pct > 0 ? '+' : '' }}{{ s.change_pct.toFixed(2) }}%
              </span>
            </div>
          </div>

          <!-- Price Marks -->
          <div v-if="s.price_marks.length > 0" class="marks-section">
            <div v-for="m in s.price_marks" :key="m.id" class="mark-row">
              <span class="mark-label">{{ m.label }}</span>
              <span class="mark-target">¥{{ m.price.toFixed(2) }}</span>
              <span v-if="m.diff != null" :class="['mark-diff', diffClass(m.diff)]">
                {{ m.diff > 0 ? '+' : '' }}{{ m.diff.toFixed(2) }} ({{ m.diff_pct > 0 ? '+' : '' }}{{ m.diff_pct.toFixed(1) }}%)
              </span>
            </div>
          </div>

          <div class="stock-footer">
            <span>报告: {{ s.report_count }}</span>
            <span v-if="s.last_analysis" :class="{ expired: isExpired(s.last_analysis) }">
              分析: {{ fmtDate(s.last_analysis) }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="stocks.length === 0 && !loading" class="card empty">
      暂无股票。点击"提交分析请求"添加第一只股票。
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import api from '../api.js'

const stocks = ref([])
const loading = ref(false)
const lastRefresh = ref(null)
let autoTimer = null

async function load() {
  loading.value = true
  try {
    const data = await api.dashboard.get()
    stocks.value = data.stocks || []
    lastRefresh.value = data.price_data_time || data.last_update
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function refreshPrices() {
  loading.value = true
  try {
    await api.prices.refresh()
    await load()
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function startAutoRefresh() {
  // Auto refresh every 30 seconds (reads from _dashboard.json)
  autoTimer = setInterval(() => {
    load()
  }, 30000)
}

function stopAutoRefresh() {
  if (autoTimer) {
    clearInterval(autoTimer)
    autoTimer = null
  }
}

const tagGroups = computed(() => {
  const order = ['green', 'yellow', 'red', 'none']
  const labels = { green: '看好', yellow: '观望', red: '回避', none: '无标签' }
  return order.map(key => ({
    key,
    label: labels[key],
    stocks: stocks.value.filter(s => s.overall === key)
  })).filter(g => g.stocks.length > 0)
})

function priceClass(pct) {
  if (pct == null) return ''
  return pct >= 0 ? 'up' : 'down'
}

function diffClass(diff) {
  if (diff == null) return ''
  return diff >= 0 ? 'up' : 'down'
}

function fmtDate(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

function fmtTime(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}

function isExpired(iso) {
  return iso && (Date.now() - new Date(iso).getTime()) > 7 * 86400000
}

onMounted(() => {
  load()
  startAutoRefresh()
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<style scoped>
.dash-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.dash-header h1 { font-size: 22px; font-weight: 600; }
.dash-actions { display: flex; gap: 10px; }

.tag-group { margin-bottom: 24px; }
.tag-group-header { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.tag-badge { display: inline-block; padding: 3px 12px; border-radius: 4px; font-size: 13px; font-weight: 600; }
.tag-green { background: #064e3b; color: #34d399; }
.tag-yellow { background: #713f12; color: #fbbf24; }
.tag-red { background: #7f1d1d; color: #f87171; }
.tag-none { background: #334155; color: #94a3b8; }
.tag-watch { background: #1e3a5f; color: #60a5fa; font-size: 11px; padding: 1px 8px; }
.tag-count { font-size: 13px; color: #64748b; }

.stock-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; }
.stock-card { cursor: pointer; transition: transform 0.12s, border-color 0.12s; padding: 16px; }
.stock-card:hover { transform: translateY(-1px); border-color: #3b82f6; }

.stock-main { margin-bottom: 10px; }
.stock-title-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.stock-code { font-size: 14px; font-weight: 600; color: #60a5fa; }
.stock-name { font-size: 13px; color: #94a3b8; }

.stock-price-row { display: flex; align-items: baseline; gap: 10px; }
.price-current { font-size: 24px; font-weight: 700; }
.price-change { font-size: 14px; font-weight: 500; }
.up { color: #f87171; }
.down { color: #34d399; }

.marks-section { border-top: 1px solid #334155; padding-top: 10px; margin-bottom: 10px; }
.mark-row { display: flex; align-items: center; gap: 10px; padding: 4px 0; font-size: 13px; }
.mark-label { color: #94a3b8; min-width: 50px; }
.mark-target { font-weight: 600; color: #e2e8f0; }
.mark-diff { font-size: 12px; }

.stock-footer { display: flex; gap: 14px; font-size: 12px; color: #64748b; border-top: 1px solid #334155; padding-top: 10px; }
.stock-footer .expired { color: #f87171; }

.refresh-info { font-size: 12px; color: #64748b; margin-bottom: 16px; margin-top: -8px; }

.empty { text-align: center; padding: 40px; color: #64748b; }

/* Mobile */
@media (max-width: 640px) {
  .dash-header { flex-direction: column; gap: 12px; align-items: stretch; }
  .dash-header h1 { font-size: 18px; }
  .dash-actions { flex-wrap: wrap; }
  .dash-actions button { flex: 1; }
  .stock-grid { grid-template-columns: 1fr; }
  .price-current { font-size: 20px; }
}
</style>
