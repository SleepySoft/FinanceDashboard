<template>
  <div class="anomaly-board">
    <!-- Header -->
    <div class="nav">
      <router-link to="/" class="logo">← 返回看板</router-link>
    </div>

    <h1 class="page-title">异动雷达</h1>
    <p class="page-subtitle">异动不是波动，是异常行为。宁缺毋滥。</p>

    <!-- Controls -->
    <div class="controls card">
      <div class="control-row">
        <label>日期：</label>
        <select v-model="selectedDate" @change="loadDate">
          <option v-for="d in dates" :key="d" :value="d">{{ d }}</option>
        </select>
        <button class="primary" @click="scanNow" :disabled="scanning">
          {{ scanning ? '扫描中...' : '手动扫描' }}
        </button>
        <button class="ghost" @click="loadLatest">最新</button>
      </div>
      <div v-if="scanResult" class="scan-result">
        <span :class="scanResult.ok ? 'ok' : 'err'">{{ scanResult.msg }}</span>
      </div>
    </div>

    <!-- Weekly Summary -->
    <div class="weekly-summary card" v-if="weekly">
      <h3>
        本周统计
        <span class="week-range">{{ weekly.week_start }} ~ {{ weekly.week_end }}</span>
      </h3>
      <div class="stats-grid">
        <div class="stat-item">
          <div class="stat-value">{{ weekly.total_stock_anomalies }}</div>
          <div class="stat-label">个股异动</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">{{ weekly.total_sector_anomalies }}</div>
          <div class="stat-label">板块异动</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">{{ weekly.top_sectors?.length || 0 }}</div>
          <div class="stat-label">活跃板块</div>
        </div>
      </div>
      <div v-if="weekly.top_sectors?.length" class="top-sectors">
        <div class="subsection-title">活跃板块 TOP5</div>
        <div class="sector-tags">
          <span
            v-for="s in weekly.top_sectors.slice(0, 5)"
            :key="s.sector"
            class="sector-tag"
            @click="filterBySector(s.sector)"
          >
            {{ s.sector }} ({{ s.count }}次)
          </span>
        </div>
      </div>
    </div>

    <!-- Sector Anomalies -->
    <div class="sector-section card" v-if="sectors.length">
      <h3>
        板块异动
        <span class="count-badge">{{ sectors.length }}</span>
      </h3>
      <div class="sector-list">
        <div
          v-for="s in sectors"
          :key="s.sector"
          class="sector-item"
          :class="`level-${s.level}`"
        >
          <div class="sector-header">
            <span class="sector-name">{{ s.sector }}</span>
            <span class="sector-score">{{ s.score }}分</span>
            <span class="tag" :class="`tag-${s.level}`">{{ levelText(s.level) }}</span>
          </div>
          <div class="sector-stats">
            <span>{{ s.anomaly_count }}只个股异动</span>
            <span>板块平均{{ s.avg_change_pct > 0 ? '涨' : '跌' }}{{ Math.abs(s.avg_change_pct).toFixed(1) }}%</span>
            <span v-if="s.top_gainer">领涨: {{ s.top_gainer.name }} +{{ s.top_gainer.change_pct?.toFixed(1) }}%</span>
          </div>
          <div class="sector-signals">
            <span v-for="(sig, i) in s.signals" :key="i" class="signal-chip">
              {{ sig.desc }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Stock Anomalies -->
    <div class="stock-section card" v-if="stocks.length">
      <h3>
        个股异动
        <span class="count-badge">{{ stocks.length }}</span>
        <span v-if="filteredStocks.length !== stocks.length" class="filter-hint">
          (已筛选 {{ filteredStocks.length }} 只)
        </span>
      </h3>

      <!-- Filters -->
      <div class="filters">
        <button
          class="filter-btn"
          :class="{ active: levelFilter === 'all' }"
          @click="levelFilter = 'all'"
        >全部</button>
        <button
          class="filter-btn"
          :class="{ active: levelFilter === 'strong' }"
          @click="levelFilter = 'strong'"
        >强烈</button>
        <button
          class="filter-btn"
          :class="{ active: levelFilter === 'notable' }"
          @click="levelFilter = 'notable'"
        >显著</button>
        <button
          v-if="sectorFilter"
          class="filter-btn active sector-filter"
          @click="sectorFilter = ''"
        >板块: {{ sectorFilter }} ×</button>
      </div>

      <!-- Stock Cards -->
      <div class="stock-list">
        <div
          v-for="stock in filteredStocks"
          :key="stock.code"
          class="stock-card"
          :class="{ 'sector-anomaly': stock.sector_anomaly }"
        >
          <div class="stock-header">
            <div class="stock-info">
              <span class="stock-name" @click="openStock(stock.code)">{{ stock.name }}</span>
              <span class="stock-code">{{ stock.code }}</span>
              <span v-if="stock.sector" class="stock-sector">{{ stock.sector }}</span>
              <span v-if="stock.sector_anomaly" class="sector-sync">板块共振</span>
            </div>
            <div class="stock-score">
              <span class="score-num">{{ stock.score }}</span>
              <span class="tag" :class="`tag-${stock.level}`">{{ levelText(stock.level) }}</span>
            </div>
          </div>

          <div class="stock-metrics">
            <span :class="stock.change_pct > 0 ? 'up' : 'down'">
              {{ stock.change_pct > 0 ? '+' : '' }}{{ stock.change_pct?.toFixed(2) }}%
            </span>
            <span>振幅 {{ stock.amplitude?.toFixed(1) }}%</span>
            <span>量比 {{ stock.vol_ratio?.toFixed(1) }}x</span>
            <span v-if="stock.breakout_type !== 'none'" class="breakout">
              突破{{ stock.breakout_type === 'high' ? '高' : '低' }}点
            </span>
          </div>

          <div class="stock-signals">
            <span v-for="(sig, i) in stock.signals" :key="i" class="signal-chip">
              {{ sig.desc }}
            </span>
          </div>

          <div class="stock-actions">
            <button class="ghost small" @click="openStock(stock.code)">查看详情</button>
            <button class="primary small" @click="addToDashboard(stock.code)" :disabled="adding[stock.code]">
              {{ adding[stock.code] ? '已添加' : '加入看板' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="!loading && !stocks.length && !sectors.length" class="empty-state card">
      <div class="empty-icon">📡</div>
      <div class="empty-title">暂无异动信号</div>
      <div class="empty-desc">当前日期未发现满足条件的异动。这很正常——宁缺毋滥。</div>
      <button class="primary" @click="scanNow" :disabled="scanning">
        {{ scanning ? '扫描中...' : '重新扫描' }}
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading card">
      <div class="spinner"></div>
      <span>加载中...</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api.js'

const router = useRouter()

const dates = ref([])
const selectedDate = ref('')
const stocks = ref([])
const sectors = ref([])
const weekly = ref(null)
const loading = ref(false)
const scanning = ref(false)
const scanResult = ref(null)
const levelFilter = ref('all')
const sectorFilter = ref('')
const adding = ref({})

const filteredStocks = computed(() => {
  let result = stocks.value
  if (levelFilter.value !== 'all') {
    result = result.filter(s => s.level === levelFilter.value)
  }
  if (sectorFilter.value) {
    result = result.filter(s => s.sector === sectorFilter.value)
  }
  return result
})

function levelText(level) {
  const map = { weak: '微弱', notable: '显著', strong: '强烈' }
  return map[level] || level
}

async function loadDates() {
  try {
    const res = await api.anomalies.listDates()
    dates.value = res.dates || []
    if (dates.value.length && !selectedDate.value) {
      selectedDate.value = dates.value[0]
      await loadDate()
    }
  } catch (e) {
    console.error('Failed to load dates:', e)
  }
}

async function loadDate() {
  if (!selectedDate.value) return
  loading.value = true
  try {
    const data = await api.anomalies.getByDate(selectedDate.value)
    stocks.value = data.stocks || []
    sectors.value = data.sectors || []
    // 同时加载本周统计
    const w = await api.anomalies.getWeekly(selectedDate.value)
    weekly.value = w
  } catch (e) {
    console.error('Failed to load anomalies:', e)
    stocks.value = []
    sectors.value = []
  } finally {
    loading.value = false
  }
}

async function loadLatest() {
  loading.value = true
  try {
    const data = await api.anomalies.getLatest()
    if (data.date) {
      selectedDate.value = data.date
      stocks.value = data.stocks || []
      sectors.value = data.sectors || []
      const w = await api.anomalies.getWeekly(data.date)
      weekly.value = w
    }
  } catch (e) {
    console.error('Failed to load latest:', e)
  } finally {
    loading.value = false
  }
}

async function scanNow() {
  scanning.value = true
  scanResult.value = null
  try {
    const res = await api.anomalies.scan(selectedDate.value)
    scanResult.value = { ok: true, msg: `扫描完成：发现 ${res.stocks_found} 只个股异动，${res.sectors_found} 个板块异动` }
    // 刷新当前日期数据
    await loadDates()
    await loadDate()
  } catch (e) {
    scanResult.value = { ok: false, msg: `扫描失败: ${e.message}` }
  } finally {
    scanning.value = false
  }
}

function filterBySector(sector) {
  sectorFilter.value = sector
}

function openStock(code) {
  router.push(`/stock/${code}`)
}

async function addToDashboard(code) {
  adding.value[code] = true
  try {
    const res = await api.anomalies.addToDashboard(code)
    if (res.status === 'ok' || res.status === 'exists') {
      adding.value[code] = true
      setTimeout(() => {
        adding.value[code] = false
      }, 2000)
    }
  } catch (e) {
    console.error('Failed to add to dashboard:', e)
    adding.value[code] = false
  }
}

onMounted(() => {
  loadDates()
})
</script>

<style scoped>
.page-title {
  font-size: 22px;
  font-weight: 700;
  margin-bottom: 4px;
}
.page-subtitle {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 16px;
}

.controls {
  padding: 16px 20px;
}
.control-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.control-row label {
  font-size: 13px;
  color: #94a3b8;
}
.control-row select {
  min-width: 120px;
}
.scan-result {
  margin-top: 10px;
  font-size: 13px;
}
.scan-result .ok { color: #34d399; }
.scan-result .err { color: #f87171; }

/* Weekly Summary */
.week-range {
  font-size: 12px;
  color: #64748b;
  font-weight: 400;
  margin-left: 8px;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin: 12px 0;
}
.stat-item {
  text-align: center;
  padding: 12px;
  background: #0f172a;
  border-radius: 8px;
}
.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #60a5fa;
}
.stat-label {
  font-size: 12px;
  color: #64748b;
  margin-top: 4px;
}
.top-sectors {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #334155;
}
.subsection-title {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 8px;
}
.sector-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.sector-tag {
  padding: 4px 10px;
  background: #1e293b;
  border: 1px solid #475569;
  border-radius: 4px;
  font-size: 12px;
  color: #e2e8f0;
  cursor: pointer;
  transition: all 0.15s;
}
.sector-tag:hover {
  background: #334155;
  border-color: #60a5fa;
}

/* Sector List */
.sector-item {
  padding: 14px 16px;
  margin-bottom: 10px;
  background: #0f172a;
  border-radius: 8px;
  border-left: 3px solid #475569;
}
.sector-item.level-notable { border-left-color: #fbbf24; }
.sector-item.level-strong { border-left-color: #f87171; }
.sector-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
  flex-wrap: wrap;
}
.sector-name {
  font-weight: 600;
  font-size: 14px;
}
.sector-score {
  font-size: 13px;
  color: #94a3b8;
}
.sector-stats {
  font-size: 12px;
  color: #64748b;
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

/* Filters */
.filters {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.filter-btn {
  padding: 4px 12px;
  font-size: 12px;
  background: #0f172a;
  border: 1px solid #475569;
  color: #94a3b8;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s;
}
.filter-btn:hover, .filter-btn.active {
  background: #1e293b;
  border-color: #60a5fa;
  color: #e2e8f0;
}
.filter-btn.sector-filter {
  border-color: #34d399;
  color: #34d399;
}

/* Stock Cards */
.stock-card {
  padding: 14px 16px;
  margin-bottom: 10px;
  background: #0f172a;
  border-radius: 8px;
  border: 1px solid #1e293b;
  transition: border-color 0.15s;
}
.stock-card:hover {
  border-color: #334155;
}
.stock-card.sector-anomaly {
  border-color: #334155;
  background: linear-gradient(135deg, #0f172a 0%, #1a1f2e 100%);
}
.stock-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
  flex-wrap: wrap;
  gap: 8px;
}
.stock-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.stock-name {
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  color: #60a5fa;
}
.stock-name:hover {
  text-decoration: underline;
}
.stock-code {
  font-size: 12px;
  color: #64748b;
  font-family: monospace;
}
.stock-sector {
  font-size: 11px;
  padding: 1px 6px;
  background: #1e293b;
  border-radius: 3px;
  color: #94a3b8;
}
.sector-sync {
  font-size: 11px;
  padding: 1px 6px;
  background: #064e3b;
  color: #34d399;
  border-radius: 3px;
}
.stock-score {
  display: flex;
  align-items: center;
  gap: 6px;
}
.score-num {
  font-size: 18px;
  font-weight: 700;
  color: #fbbf24;
}
.stock-metrics {
  display: flex;
  gap: 16px;
  font-size: 13px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.stock-metrics .up { color: #f87171; }
.stock-metrics .down { color: #34d399; }
.stock-metrics .breakout {
  color: #fbbf24;
  font-weight: 500;
}
.stock-signals {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}
.signal-chip {
  font-size: 11px;
  padding: 2px 8px;
  background: #1e293b;
  border-radius: 3px;
  color: #94a3b8;
}
.stock-actions {
  display: flex;
  gap: 8px;
}
button.small {
  padding: 4px 10px;
  font-size: 12px;
}

/* Tags */
.tag-weak { background: #334155; color: #94a3b8; }
.tag-notable { background: #713f12; color: #fbbf24; }
.tag-strong { background: #7f1d1d; color: #f87171; }

/* Empty State */
.empty-state {
  text-align: center;
  padding: 40px 20px;
}
.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}
.empty-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 8px;
}
.empty-desc {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 16px;
}

/* Loading */
.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 30px;
}
.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid #334155;
  border-top-color: #60a5fa;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Count badge */
.count-badge {
  font-size: 12px;
  padding: 1px 8px;
  background: #1e293b;
  border-radius: 10px;
  color: #94a3b8;
  font-weight: 400;
  margin-left: 6px;
}
.filter-hint {
  font-size: 12px;
  color: #64748b;
  margin-left: 6px;
}

/* Mobile */
@media (max-width: 640px) {
  .stats-grid {
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
  }
  .stat-item {
    padding: 8px;
  }
  .stat-value {
    font-size: 18px;
  }
  .stock-header {
    flex-direction: column;
  }
  .stock-metrics {
    gap: 10px;
  }
}
</style>
