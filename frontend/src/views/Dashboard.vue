<template>
  <div class="dashboard">
    <!-- Single-line header: title + view tabs + refresh -->
    <div class="dash-header">
      <span class="dash-title">📊 股票池</span>
      <div class="view-tabs mini">
        <button
          v-for="v in views"
          :key="v.key"
          :class="['tab', { active: viewMode === v.key }]"
          @click="viewMode = v.key"
        >
          {{ v.label }}
        </button>
      </div>
      <button class="ghost" @click="refreshPrices" :disabled="loading">
        {{ loading ? '...' : '🔄' }}
      </button>
    </div>

    <!-- Single-line filters + group mode -->
    <div class="toolbar compact">
      <div class="filters">
        <select v-model="filterSector" class="filter-select">
          <option value="">全部行业</option>
          <option v-for="sec in sectors" :key="sec" :value="sec">{{ sec }}</option>
        </select>
        <label class="filter-check">
          <input type="checkbox" v-model="filterWatchlist" />
          关注
        </label>
      </div>
      <div class="group-tabs" v-if="viewMode === 'grouped'">
        <button
          v-for="gm in groupModes"
          :key="gm.key"
          :class="['group-tab', { active: groupMode === gm.key }]"
          @click="groupMode = gm.key"
        >
          {{ gm.label }}
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading && stocks.length === 0" class="card empty">加载中...</div>

    <!-- VIEW 1: Grouped -->
    <template v-if="viewMode === 'grouped'">
      <!-- By Status -->
      <template v-if="groupMode === 'status'">
        <div v-for="group in statusGroups" :key="group.key" class="sector-group">
          <div class="sector-header">
            <span :class="['tag-badge', 'tag-' + group.key]">{{ group.label }}</span>
            <span class="sector-count">{{ group.stocks.length }} 只</span>
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
                  <span class="stock-sector">{{ s.sector }}</span>
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
                <div class="stock-dims">
                  <span :class="['dim-badge', 'dim-' + dim(s, 'quality')]">质</span>
                  <span :class="['dim-badge', 'dim-' + dim(s, 'valuation')]">估</span>
                  <span :class="['dim-badge', 'dim-' + dim(s, 'timing')]">时</span>
                  <span :class="['dim-badge', 'dim-' + dim(s, 'risk')]">险</span>
                </div>
              </div>
              <div v-if="s.price_marks?.length > 0" class="marks-section">
                <div v-for="m in s.price_marks" :key="m.id" class="mark-row">
                  <span class="mark-label">{{ m.label }}</span>
                  <span class="mark-target">¥{{ m.price.toFixed(2) }}</span>
                  <span v-if="m.diff != null" :class="['mark-diff', m.diff >= 0 ? 'up' : 'down']">
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
      </template>

      <!-- By Rating -->
      <template v-if="groupMode === 'rating'">
        <div v-for="group in ratingGroups" :key="group.key" class="sector-group">
          <div class="sector-header">
            <span :class="['tag-badge', 'tag-' + group.key]">{{ group.label }}</span>
            <span class="sector-count">{{ group.stocks.length }} 只</span>
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
                  <span class="stock-sector">{{ s.sector }}</span>
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
                <div class="stock-dims">
                  <span :class="['dim-badge', 'dim-' + dim(s, 'quality')]">质</span>
                  <span :class="['dim-badge', 'dim-' + dim(s, 'valuation')]">估</span>
                  <span :class="['dim-badge', 'dim-' + dim(s, 'timing')]">时</span>
                  <span :class="['dim-badge', 'dim-' + dim(s, 'risk')]">险</span>
                </div>
              </div>
              <div v-if="s.price_marks?.length > 0" class="marks-section">
                <div v-for="m in s.price_marks" :key="m.id" class="mark-row">
                  <span class="mark-label">{{ m.label }}</span>
                  <span class="mark-target">¥{{ m.price.toFixed(2) }}</span>
                  <span v-if="m.diff != null" :class="['mark-diff', m.diff >= 0 ? 'up' : 'down']">
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
      </template>

      <!-- By Sector -->
      <template v-if="groupMode === 'sector'">
        <div v-for="group in sectorGroups" :key="group.sector" class="sector-group">
          <div class="sector-header">
            <span class="sector-name">{{ group.sector || '未分类' }}</span>
            <span class="sector-count">{{ group.stocks.length }} 只</span>
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
                <div class="stock-dims">
                  <span :class="['dim-badge', 'dim-' + dim(s, 'quality')]">质</span>
                  <span :class="['dim-badge', 'dim-' + dim(s, 'valuation')]">估</span>
                  <span :class="['dim-badge', 'dim-' + dim(s, 'timing')]">时</span>
                  <span :class="['dim-badge', 'dim-' + dim(s, 'risk')]">险</span>
                  <span :class="['verdict-badge', 'verdict-' + (s.dimensions?.verdict || s.overall)]">{{ verdictLabel(s) }}</span>
                </div>
              </div>
              <div v-if="s.price_marks?.length > 0" class="marks-section">
                <div v-for="m in s.price_marks" :key="m.id" class="mark-row">
                  <span class="mark-label">{{ m.label }}</span>
                  <span class="mark-target">¥{{ m.price.toFixed(2) }}</span>
                  <span v-if="m.diff != null" :class="['mark-diff', m.diff >= 0 ? 'up' : 'down']">
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
      </template>
    </template>

    <!-- VIEW 2: Matrix (Quality × Valuation) -->
    <template v-if="viewMode === 'matrix'">
      <!-- Unassessed stocks -->
      <div v-if="unassessedStocks.length > 0" class="unassessed-banner card">
        <div class="ua-title">⚪ 未评估（{{ unassessedStocks.length }} 只）— 建议补充分析</div>
        <div class="ua-stocks">
          <div
            v-for="s in unassessedStocks"
            :key="s.code"
            class="matrix-stock"
            @click="$router.push('/stock/' + s.code)"
          >
            <div class="ms-code">{{ s.code }}</div>
            <div class="ms-name">{{ s.name }}</div>
            <div class="ms-price" :class="priceClass(s.change_pct)">
              {{ s.last_price != null ? '¥' + s.last_price.toFixed(1) : '--' }}
              <span v-if="s.change_pct != null">{{ s.change_pct > 0 ? '+' : '' }}{{ s.change_pct.toFixed(1) }}%</span>
            </div>
          </div>
        </div>
      </div>

      <div class="matrix-container">
        <div class="matrix-labels">
          <div class="matrix-y-label">质量好 ↑</div>
          <div class="matrix-y-label-bottom">质量差 ↓</div>
        </div>
        <div class="matrix-grid">
          <div class="matrix-x-labels">
            <span>估值便宜 ←</span>
            <span>→ 估值贵</span>
          </div>
          <div class="matrix-quadrant q-accumulate">
            <div class="q-title">🟢 重仓区</div>
            <div class="q-sub">质量好 + 估值便宜</div>
            <div class="q-stocks">
              <div
                v-for="s in matrixQ1"
                :key="s.code"
                class="matrix-stock"
                @click="$router.push('/stock/' + s.code)"
              >
                <div class="ms-code">{{ s.code }}</div>
                <div class="ms-name">{{ s.name }}</div>
                <div class="ms-price" :class="priceClass(s.change_pct)">
                  {{ s.last_price != null ? '¥' + s.last_price.toFixed(1) : '--' }}
                  <span v-if="s.change_pct != null">{{ s.change_pct > 0 ? '+' : '' }}{{ s.change_pct.toFixed(1) }}%</span>
                </div>
              </div>
              <div v-if="matrixQ1.length === 0" class="q-empty">暂无</div>
            </div>
          </div>
          <div class="matrix-quadrant q-hold">
            <div class="q-title">🔵 持有区</div>
            <div class="q-sub">质量好 + 估值合理/贵</div>
            <div class="q-stocks">
              <div
                v-for="s in matrixQ2"
                :key="s.code"
                class="matrix-stock"
                @click="$router.push('/stock/' + s.code)"
              >
                <div class="ms-code">{{ s.code }}</div>
                <div class="ms-name">{{ s.name }}</div>
                <div class="ms-price" :class="priceClass(s.change_pct)">
                  {{ s.last_price != null ? '¥' + s.last_price.toFixed(1) : '--' }}
                  <span v-if="s.change_pct != null">{{ s.change_pct > 0 ? '+' : '' }}{{ s.change_pct.toFixed(1) }}%</span>
                </div>
              </div>
              <div v-if="matrixQ2.length === 0" class="q-empty">暂无</div>
            </div>
          </div>
          <div class="matrix-quadrant q-speculate">
            <div class="q-title">🟡 投机区</div>
            <div class="q-sub">质量一般 + 估值便宜</div>
            <div class="q-stocks">
              <div
                v-for="s in matrixQ3"
                :key="s.code"
                class="matrix-stock"
                @click="$router.push('/stock/' + s.code)"
              >
                <div class="ms-code">{{ s.code }}</div>
                <div class="ms-name">{{ s.name }}</div>
                <div class="ms-price" :class="priceClass(s.change_pct)">
                  {{ s.last_price != null ? '¥' + s.last_price.toFixed(1) : '--' }}
                  <span v-if="s.change_pct != null">{{ s.change_pct > 0 ? '+' : '' }}{{ s.change_pct.toFixed(1) }}%</span>
                </div>
              </div>
              <div v-if="matrixQ3.length === 0" class="q-empty">暂无</div>
            </div>
          </div>
          <div class="matrix-quadrant q-avoid">
            <div class="q-title">🔴 回避区</div>
            <div class="q-sub">质量差 或 估值离谱</div>
            <div class="q-stocks">
              <div
                v-for="s in matrixQ4"
                :key="s.code"
                class="matrix-stock"
                @click="$router.push('/stock/' + s.code)"
              >
                <div class="ms-code">{{ s.code }}</div>
                <div class="ms-name">{{ s.name }}</div>
                <div class="ms-price" :class="priceClass(s.change_pct)">
                  {{ s.last_price != null ? '¥' + s.last_price.toFixed(1) : '--' }}
                  <span v-if="s.change_pct != null">{{ s.change_pct > 0 ? '+' : '' }}{{ s.change_pct.toFixed(1) }}%</span>
                </div>
              </div>
              <div v-if="matrixQ4.length === 0" class="q-empty">暂无</div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- VIEW 3: Compact List -->
    <template v-if="viewMode === 'list'">
      <div class="list-table card">
        <table>
          <thead>
            <tr>
              <th @click="sortBy('code')">代码 {{ sortIcon('code') }}</th>
              <th @click="sortBy('name')">名称 {{ sortIcon('name') }}</th>
              <th @click="sortBy('sector')">行业 {{ sortIcon('sector') }}</th>
              <th @click="sortBy('last_price')">价格 {{ sortIcon('last_price') }}</th>
              <th @click="sortBy('change_pct')">涨跌 {{ sortIcon('change_pct') }}</th>
              <th @click="sortByDim('quality')">质量 {{ sortIconDim('quality') }}</th>
              <th @click="sortByDim('valuation')">估值 {{ sortIconDim('valuation') }}</th>
              <th @click="sortByDim('timing')">时机 {{ sortIconDim('timing') }}</th>
              <th @click="sortByDim('risk')">风险 {{ sortIconDim('risk') }}</th>
              <th @click="sortByDim('verdict')">综合 {{ sortIconDim('verdict') }}</th>
              <th @click="sortBy('report_count')">报告 {{ sortIcon('report_count') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="s in sortedStocks"
              :key="s.code"
              class="list-row"
              @click="$router.push('/stock/' + s.code)"
            >
              <td class="cell-code">{{ s.code }}</td>
              <td class="cell-name">{{ s.name }}</td>
              <td class="cell-sector">{{ s.sector }}</td>
              <td :class="['cell-price', priceClass(s.change_pct)]">
                {{ s.last_price != null ? '¥' + s.last_price.toFixed(2) : '--' }}
              </td>
              <td :class="['cell-pct', priceClass(s.change_pct)]">
                {{ s.change_pct != null ? (s.change_pct > 0 ? '+' : '') + s.change_pct.toFixed(2) + '%' : '--' }}
              </td>
              <td><span :class="['dim-dot', 'dim-' + dim(s, 'quality')]"></span></td>
              <td><span :class="['dim-dot', 'dim-' + dim(s, 'valuation')]"></span></td>
              <td><span :class="['dim-dot', 'dim-' + dim(s, 'timing')]"></span></td>
              <td><span :class="['dim-dot', 'dim-' + dim(s, 'risk')]"></span></td>
              <td><span :class="['verdict-badge', 'verdict-' + (s.dimensions?.verdict || s.overall)]">{{ verdictLabel(s) }}</span></td>
              <td class="cell-reports">{{ s.report_count }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <div v-if="filteredStocks.length === 0 && !loading" class="card empty">
      没有匹配的股票。调整筛选条件试试。
    </div>
    <StockModal :show="showModal" :stock="selectedStock" @close="closeModal" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api.js'
import StockModal from '../components/StockModal.vue'

const route = useRoute()
const router = useRouter()

const stocks = ref([])
const loading = ref(false)
const lastRefresh = ref(null)
const viewMode = ref('grouped')
const filterSector = ref('')
const filterVerdict = ref('')
const filterWatchlist = ref(false)
const sortKey = ref('code')
const sortAsc = ref(true)
const selectedStock = ref(null)
const showModal = ref(false)

// Read view from URL query
const queryView = route.query.view
if (queryView && ['grouped', 'matrix', 'list'].includes(queryView)) {
  viewMode.value = queryView
}

// Sync view to URL when changed
watch(viewMode, (v) => {
  router.replace({ query: { ...route.query, view: v } })
})

const groupMode = ref('status')
const groupModes = [
  { key: 'status', label: '按投资状态' },
  { key: 'sector', label: '按行业' },
  { key: 'rating', label: '按综合评级' }
]

let autoTimer = null

const views = [
  { key: 'grouped', label: '🏭 行业分组' },
  { key: 'matrix', label: '📊 质量估值矩阵' },
  { key: 'list', label: '📋 紧凑列表' }
]

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
  autoTimer = setInterval(() => load(), 30000)
}
function stopAutoRefresh() {
  if (autoTimer) { clearInterval(autoTimer); autoTimer = null }
}

function openStock(code) {
  const stock = stocks.value.find(s => s.code === code)
  if (stock) {
    selectedStock.value = stock
    showModal.value = true
    router.push({ path: '/stock/' + code, query: { view: viewMode.value } })
  }
}
function closeModal() {
  showModal.value = false
  selectedStock.value = null
  router.push({ path: '/', query: { view: viewMode.value } })
}

// ── Filtered stocks ──
const filteredStocks = computed(() => {
  return stocks.value.filter(s => {
    if (filterSector.value && s.sector !== filterSector.value) return false
    const verdict = s.dimensions?.verdict || s.overall
    if (filterVerdict.value && verdict !== filterVerdict.value) return false
    if (filterWatchlist.value && !s.watchlist) return false
    return true
  })
})

const sectors = computed(() => {
  const set = new Set(stocks.value.map(s => s.sector).filter(Boolean))
  return Array.from(set).sort()
})

// ── Status groups ──
const statusGroups = computed(() => {
  const order = ['tracking', 'bullish', 'neutral', 'avoid', 'archive']
  const labels = { tracking: '🔭 跟踪中', bullish: '看好', neutral: '观望', avoid: '回避', archive: '📁 归档' }
  return order.map(key => ({
    key,
    label: labels[key],
    stocks: filteredStocks.value.filter(s => (s.status || 'neutral') === key)
  })).filter(g => g.stocks.length > 0)
})

// ── Rating groups (default) ──
const ratingGroups = computed(() => {
  const order = ['green', 'yellow', 'red', 'none']
  const labels = { green: '看好', yellow: '观望', red: '回避', none: '未评级' }
  return order.map(key => ({
    key,
    label: labels[key],
    stocks: filteredStocks.value.filter(s => {
      const v = s.dimensions?.verdict || s.overall
      return v === key
    })
  })).filter(g => g.stocks.length > 0)
})

// ── Sector groups ──
const sectorGroups = computed(() => {
  const map = {}
  for (const s of filteredStocks.value) {
    const sec = s.sector || '未分类'
    if (!map[sec]) map[sec] = []
    map[sec].push(s)
  }
  return Object.entries(map)
    .map(([sector, stocks]) => ({ sector, stocks }))
    .sort((a, b) => b.stocks.length - a.stocks.length)
})

// ── Matrix view ──
function isAssessed(s) {
  const q = s.dimensions?.quality || s.tags?.moat || s.tags?.fundamental || 'none'
  const v = s.dimensions?.valuation || s.tags?.valuation || 'none'
  return q !== 'none' && v !== 'none'
}
function isGoodQuality(s) {
  const q = s.dimensions?.quality || s.tags?.moat || s.tags?.fundamental || 'none'
  return q === 'green'
}
function isCheap(s) {
  const v = s.dimensions?.valuation || s.tags?.valuation || 'none'
  return v === 'green'
}
function isExpensive(s) {
  const v = s.dimensions?.valuation || s.tags?.valuation || 'none'
  return v === 'red'
}

const matrixQ1 = computed(() => filteredStocks.value.filter(s => isAssessed(s) && isGoodQuality(s) && isCheap(s)))
const matrixQ2 = computed(() => filteredStocks.value.filter(s => isAssessed(s) && isGoodQuality(s) && !isCheap(s)))
const matrixQ3 = computed(() => filteredStocks.value.filter(s => isAssessed(s) && !isGoodQuality(s) && isCheap(s)))
const matrixQ4 = computed(() => filteredStocks.value.filter(s => isAssessed(s) && !isGoodQuality(s) && !isCheap(s)))
const unassessedStocks = computed(() => filteredStocks.value.filter(s => !isAssessed(s)))

// ── List view ──
const dimOrder = { green: 3, yellow: 2, red: 1, none: 0 }

function sortBy(key) {
  if (sortKey.value === key) {
    sortAsc.value = !sortAsc.value
  } else {
    sortKey.value = key
    sortAsc.value = true
  }
}
function sortByDim(dimKey) {
  const key = 'dim:' + dimKey
  if (sortKey.value === key) {
    sortAsc.value = !sortAsc.value
  } else {
    sortKey.value = key
    sortAsc.value = true
  }
}
function sortIcon(key) {
  if (sortKey.value !== key) return ''
  return sortAsc.value ? '↑' : '↓'
}
function sortIconDim(dimKey) {
  if (sortKey.value !== 'dim:' + dimKey) return ''
  return sortAsc.value ? '↑' : '↓'
}
const sortedStocks = computed(() => {
  const arr = [...filteredStocks.value]
  const key = sortKey.value
  arr.sort((a, b) => {
    let av, bv
    if (key.startsWith('dim:')) {
      const dk = key.slice(4)
      av = dimOrder[dim(a, dk)] ?? 0
      bv = dimOrder[dim(b, dk)] ?? 0
    } else {
      av = a[key]
      bv = b[key]
      if (av == null) av = -Infinity
      if (bv == null) bv = -Infinity
    }
    return sortAsc.value ? (av > bv ? 1 : -1) : (av > bv ? -1 : 1)
  })
  return arr
})

// ── Helpers ──
function dim(s, key) {
  return s.dimensions?.[key] || s.tags?.[key] || 'none'
}
function verdictLabel(s) {
  const v = s.dimensions?.verdict || s.overall
  const labels = { green: '看好', yellow: '观望', red: '回避', none: '-' }
  return labels[v] || '-'
}
function priceClass(pct) {
  if (pct == null) return ''
  return pct >= 0 ? 'up' : 'down'
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

onMounted(() => { load(); startAutoRefresh() })
onUnmounted(stopAutoRefresh)
</script>

<style scoped>
.dash-header { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.dash-title { font-size: 15px; font-weight: 600; flex-shrink: 0; }

.view-tabs { display: flex; gap: 2px; background: #0f172a; padding: 3px; border-radius: 6px; flex-shrink: 0; }
.view-tabs.mini .tab { padding: 3px 10px; border-radius: 4px; font-size: 12px; }
.tab { padding: 6px 14px; border-radius: 6px; font-size: 13px; cursor: pointer; background: transparent; color: #94a3b8; border: none; }
.tab.active { background: #1e3a5f; color: #60a5fa; font-weight: 600; }

.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; flex-wrap: wrap; gap: 8px; }

.filters { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.filter-select { background: #0f172a; color: #e2e8f0; border: 1px solid #334155; border-radius: 5px; padding: 3px 8px; font-size: 12px; }
.filter-check { display: flex; align-items: center; gap: 3px; font-size: 12px; color: #94a3b8; cursor: pointer; }
.filter-check input { accent-color: #3b82f6; width: 14px; height: 14px; }

.group-tabs { display: flex; gap: 2px; background: #0f172a; padding: 2px; border-radius: 5px; }
.group-tab { padding: 3px 8px; border-radius: 4px; font-size: 11px; cursor: pointer; background: transparent; color: #94a3b8; border: 1px solid #334155; }
.group-tab.active { background: #1e3a5f; color: #60a5fa; border-color: #1e3a5f; font-weight: 600; }

/* ── Grouped view ── */
.sector-group { margin-bottom: 20px; }
.sector-header { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.sector-name { font-size: 15px; font-weight: 600; color: #e2e8f0; }
.sector-count { font-size: 12px; color: #64748b; }

.stock-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }

.stock-card { cursor: pointer; transition: transform 0.12s, border-color 0.12s; padding: 14px; }
.stock-card:hover { transform: translateY(-1px); border-color: #3b82f6; }

.stock-main { margin-bottom: 10px; }
.stock-title-row { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; flex-wrap: wrap; }
.stock-code { font-size: 14px; font-weight: 600; color: #60a5fa; }
.stock-name { font-size: 15px; font-weight: 600; color: #e2e8f0; }
.stock-sector { font-size: 11px; color: #64748b; }

.stock-price-row { display: flex; align-items: baseline; gap: 8px; margin-bottom: 8px; }
.price-current { font-size: 22px; font-weight: 700; }
.price-change { font-size: 13px; font-weight: 500; }
.up { color: #f87171; }
.down { color: #34d399; }

.stock-dims { display: flex; gap: 6px; margin-bottom: 8px; }
.dim-badge { display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 11px; font-weight: 600; }
.dim-green { background: #064e3b; color: #34d399; }
.dim-yellow { background: #713f12; color: #fbbf24; }
.dim-red { background: #7f1d1d; color: #f87171; }
.dim-none { background: #334155; color: #64748b; }

.verdict-badge { display: inline-block; padding: 1px 8px; border-radius: 3px; font-size: 11px; font-weight: 600; }
.verdict-green { background: #064e3b; color: #34d399; }
.verdict-yellow { background: #713f12; color: #fbbf24; }
.verdict-red { background: #7f1d1d; color: #f87171; }
.verdict-none { background: #334155; color: #64748b; }

.tag-badge { display: inline-block; padding: 3px 12px; border-radius: 4px; font-size: 13px; font-weight: 600; }
.tag-green { background: #064e3b; color: #34d399; }
.tag-yellow { background: #713f12; color: #fbbf24; }
.tag-red { background: #7f1d1d; color: #f87171; }
.tag-none { background: #334155; color: #94a3b8; }
.tag-tracking { background: #1e3a5f; color: #60a5fa; }
.tag-bullish { background: #064e3b; color: #34d399; }
.tag-neutral { background: #713f12; color: #fbbf24; }
.tag-avoid { background: #7f1d1d; color: #f87171; }
.tag-archive { background: #334155; color: #94a3b8; }
.tag-watch { background: #1e3a5f; color: #60a5fa; font-size: 11px; padding: 1px 8px; }

.marks-section { border-top: 1px solid #334155; padding-top: 8px; margin-bottom: 8px; }
.mark-row { display: flex; align-items: center; gap: 8px; padding: 3px 0; font-size: 12px; }
.mark-label { color: #94a3b8; min-width: 50px; }
.mark-target { font-weight: 600; color: #e2e8f0; }
.mark-diff { font-size: 11px; }

.stock-footer { display: flex; gap: 12px; font-size: 11px; color: #64748b; border-top: 1px solid #334155; padding-top: 8px; }
.stock-footer .expired { color: #f87171; }

.unassessed-banner { margin-bottom: 16px; padding: 12px 16px; border: 1px dashed #475569; }
.ua-title { font-size: 14px; font-weight: 600; color: #94a3b8; margin-bottom: 10px; }
.ua-stocks { display: flex; flex-wrap: wrap; gap: 6px; }

/* ── Matrix view ── */
.matrix-container { display: flex; gap: 12px; }
.matrix-labels { display: flex; flex-direction: column; justify-content: center; align-items: center; width: 30px; flex-shrink: 0; }
.matrix-y-label { writing-mode: vertical-rl; text-orientation: mixed; font-size: 13px; color: #94a3b8; font-weight: 600; }
.matrix-y-label-bottom { writing-mode: vertical-rl; text-orientation: mixed; font-size: 13px; color: #94a3b8; margin-top: auto; }

.matrix-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; flex: 1; }
.matrix-x-labels { grid-column: 1 / -1; display: flex; justify-content: space-between; font-size: 12px; color: #64748b; padding: 0 8px; }

.matrix-quadrant { border: 1px solid #334155; border-radius: 10px; padding: 12px; min-height: 160px; }
.matrix-quadrant.q-accumulate { background: rgba(6, 78, 59, 0.15); border-color: #064e3b; }
.matrix-quadrant.q-hold { background: rgba(30, 58, 95, 0.15); border-color: #1e3a5f; }
.matrix-quadrant.q-speculate { background: rgba(113, 63, 18, 0.15); border-color: #713f12; }
.matrix-quadrant.q-avoid { background: rgba(127, 29, 29, 0.15); border-color: #7f1d1d; }

.q-title { font-size: 14px; font-weight: 700; margin-bottom: 2px; }
.q-sub { font-size: 11px; color: #64748b; margin-bottom: 8px; }
.q-stocks { display: flex; flex-wrap: wrap; gap: 6px; }
.q-empty { font-size: 12px; color: #64748b; font-style: italic; }

.matrix-stock { background: #0f172a; border: 1px solid #334155; border-radius: 6px; padding: 8px 10px; cursor: pointer; min-width: 100px; }
.matrix-stock:hover { border-color: #3b82f6; }
.ms-code { font-size: 12px; font-weight: 600; color: #60a5fa; }
.ms-name { font-size: 11px; color: #94a3b8; margin-bottom: 2px; }
.ms-price { font-size: 13px; font-weight: 600; }

/* ── List view ── */
.list-table { padding: 0; overflow-x: auto; }
.list-table table { width: 100%; border-collapse: collapse; font-size: 13px; }
.list-table th { text-align: left; padding: 10px 12px; color: #94a3b8; font-weight: 600; border-bottom: 1px solid #334155; cursor: pointer; user-select: none; white-space: nowrap; }
.list-table th:hover { color: #e2e8f0; }
.list-table td { padding: 8px 12px; border-bottom: 1px solid #1e293b; white-space: nowrap; }
.list-row { cursor: pointer; }
.list-row:hover { background: #1e293b; }

.cell-code { font-weight: 600; color: #60a5fa; }
.cell-name { color: #e2e8f0; }
.cell-sector { color: #94a3b8; font-size: 12px; }
.cell-price { font-weight: 600; }
.cell-pct { font-weight: 500; }
.cell-reports { color: #64748b; }

.dim-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; }

.empty { text-align: center; padding: 40px; color: #64748b; }

/* Mobile */
@media (max-width: 768px) {
  .dash-header { gap: 6px; }
  .view-tabs.mini .tab { padding: 3px 8px; font-size: 11px; }
  .toolbar { gap: 6px; }
  .filter-select { padding: 3px 6px; font-size: 11px; }
  .group-tab { padding: 2px 6px; font-size: 10px; }
  .stock-grid { grid-template-columns: 1fr; gap: 10px; }
  .stock-card { padding: 14px; }
  .stock-title-row { gap: 6px; }
  .stock-code { font-size: 15px; }
  .stock-name { font-size: 16px; }
  .stock-sector { font-size: 11px; }
  .price-current { font-size: 24px; }
  .price-change { font-size: 14px; }
  .stock-dims { gap: 6px; }
  .dim-badge { padding: 2px 8px; font-size: 12px; }
  .matrix-container { flex-direction: column; }
  .matrix-labels { display: none; }
  .matrix-grid { grid-template-columns: 1fr; }
  .list-table { font-size: 13px; }
  .list-table th, .list-table td { padding: 8px 10px; }
}
</style>
