<template>
  <div class="holdings-page">
    <div class="hp-header">
      <h2>📦 持仓管理</h2>
      <router-link to="/" class="btn-ghost">← 返回大盘</router-link>
    </div>

    <!-- Summary Bar -->
    <div v-if="summary.count > 0" class="hp-summary-bar card">
      <div class="hp-summary-item">
        <span class="hp-label">持仓</span>
        <span class="hp-value">{{ summary.count }} 只</span>
      </div>
      <div class="hp-summary-item">
        <span class="hp-label">总市值</span>
        <span class="hp-value">¥{{ summary.marketValue.toLocaleString('zh-CN', {maximumFractionDigits:0}) }}</span>
      </div>
      <div class="hp-summary-item">
        <span class="hp-label">总成本</span>
        <span class="hp-value">¥{{ summary.cost.toLocaleString('zh-CN', {maximumFractionDigits:0}) }}</span>
      </div>
      <div class="hp-summary-item">
        <span class="hp-label">浮动盈亏</span>
        <span :class="['hp-value', 'hp-pnl', summary.pnl >= 0 ? 'up' : 'down']">
          {{ summary.pnl >= 0 ? '+' : '' }}¥{{ summary.pnl.toLocaleString('zh-CN', {maximumFractionDigits:0}) }}
          ({{ summary.pnlPct >= 0 ? '+' : '' }}{{ summary.pnlPct.toFixed(1) }}%)
        </span>
      </div>
      <div v-if="summary.realized > 0" class="hp-summary-item">
        <span class="hp-label">已落袋利润</span>
        <span class="hp-value t-profit">+¥{{ summary.realized.toLocaleString('zh-CN', {maximumFractionDigits:0}) }}</span>
      </div>
    </div>

    <!-- Holdings List -->
    <div v-if="loading" class="card empty">加载中...</div>
    <div v-else-if="holdingsList.length === 0" class="card empty">暂无持仓</div>
    <div v-else class="holdings-list">
      <div v-for="item in holdingsList" :key="item.code" class="holdings-item card">
        <div class="hi-header" @click="toggleExpand(item.code)">
          <div class="hi-main">
            <span class="hi-name">{{ item.name }}</span>
            <span class="hi-code">{{ item.code }}</span>
            <span class="hi-sector">{{ item.sector }}</span>
          </div>
          <div class="hi-stats">
            <span class="hi-qty">{{ item.quantity }}股</span>
            <span class="hi-cost">@ ¥{{ item.avg_cost.toFixed(2) }}</span>
            <span class="hi-price" :class="priceClass(item.change_pct)">
              ¥{{ item.last_price?.toFixed(2) || '--' }}
            </span>
            <span v-if="item.change_pct != null" class="hi-change" :class="priceClass(item.change_pct)">
              {{ item.change_pct > 0 ? '+' : '' }}{{ item.change_pct.toFixed(2) }}%
            </span>
            <span :class="['hi-pnl', item.pnl >= 0 ? 'up' : 'down']">
              {{ item.pnl >= 0 ? '+' : '' }}¥{{ item.pnl.toFixed(0) }}
            </span>
            <span v-if="item.realized_pnl > 0" class="hi-realized t-profit">
              已落袋 +{{ item.realized_pnl.toFixed(0) }}
            </span>
          </div>
          <span class="hi-toggle">{{ expanded.has(item.code) ? '▾' : '▸' }}</span>
        </div>
        <div v-show="expanded.has(item.code)" class="hi-detail">
          <div class="hi-detail-grid">
            <div class="hi-detail-col">
              <div class="hi-detail-row">
                <span class="hi-dlabel">持仓数量</span>
                <span class="hi-dvalue">{{ item.quantity }}股</span>
              </div>
              <div class="hi-detail-row">
                <span class="hi-dlabel">平均成本</span>
                <span class="hi-dvalue">¥{{ item.avg_cost.toFixed(2) }}</span>
              </div>
              <div class="hi-detail-row">
                <span class="hi-dlabel">当前价格</span>
                <span class="hi-dvalue">¥{{ item.last_price?.toFixed(2) || '--' }}</span>
              </div>
              <div class="hi-detail-row">
                <span class="hi-dlabel">市值</span>
                <span class="hi-dvalue">¥{{ (item.quantity * (item.last_price || 0)).toFixed(0) }}</span>
              </div>
              <div class="hi-detail-row">
                <span class="hi-dlabel">浮动盈亏</span>
                <span :class="['hi-dvalue', item.pnl >= 0 ? 'up' : 'down']">
                  {{ item.pnl >= 0 ? '+' : '' }}¥{{ item.pnl.toFixed(0) }} ({{ item.pnlPct >= 0 ? '+' : '' }}{{ item.pnlPct.toFixed(1) }}%)
                </span>
              </div>
              <div v-if="item.realized_pnl > 0" class="hi-detail-row">
                <span class="hi-dlabel">已落袋利润</span>
                <span class="hi-dvalue t-profit">+¥{{ item.realized_pnl.toFixed(0) }}</span>
              </div>
            </div>
            <div class="hi-detail-col">
              <div class="hi-trades-header">交易记录</div>
              <div v-if="item.trades?.length > 0" class="hi-trades-wrap">
                <table class="hi-trades-table">
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
                    <tr v-for="t in item.trades" :key="t.id">
                      <td>{{ t.date }}</td>
                      <td :class="t.type === 'buy' ? 'up' : 'down'">{{ t.type === 'buy' ? '买入' : '卖出' }}</td>
                      <td>¥{{ t.price.toFixed(2) }}</td>
                      <td>{{ t.quantity }}</td>
                      <td>{{ t.fee?.toFixed(2) || '-' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div v-else class="empty" style="padding: 12px 0;">暂无交易记录</div>
            </div>
          </div>
          <div class="hi-actions">
            <router-link :to="'/stock/' + item.code" class="btn-primary">进入详情 →</router-link>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api.js'

const loading = ref(true)
const holdingsRaw = ref([])
const stocksMap = ref({})
const expanded = ref(new Set())

const holdingsList = computed(() => {
  return holdingsRaw.value
    .filter(h => h.quantity > 0)
    .map(h => {
      const s = stocksMap.value[h.code] || {}
      const price = s.last_price || 0
      const cost = h.quantity * h.avg_cost
      const mkt = h.quantity * price
      const pnl = mkt - cost
      const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0
      return {
        code: h.code,
        name: s.name || h.code,
        sector: s.sector || '',
        quantity: h.quantity,
        avg_cost: h.avg_cost,
        last_price: price,
        change_pct: s.change_pct,
        pnl,
        pnlPct,
        realized_pnl: h.realized_pnl || 0,
        trades: h.trades || [],
      }
    })
    .sort((a, b) => Math.abs(b.pnl) - Math.abs(a.pnl))
})

const summary = computed(() => {
  let count = 0
  let marketValue = 0
  let cost = 0
  let realized = 0
  for (const item of holdingsList.value) {
    count++
    marketValue += item.quantity * (item.last_price || 0)
    cost += item.quantity * item.avg_cost
    realized += item.realized_pnl
  }
  const pnl = marketValue - cost
  const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0
  return { count, marketValue, cost, pnl, pnlPct, realized }
})

function priceClass(pct) {
  if (pct == null) return ''
  return pct >= 0 ? 'up' : 'down'
}

function toggleExpand(code) {
  if (expanded.value.has(code)) {
    expanded.value.delete(code)
  } else {
    expanded.value.add(code)
  }
}

async function load() {
  loading.value = true
  try {
    // Get all stocks with prices
    const dash = await api.dashboard.get()
    for (const s of dash.stocks || []) {
      stocksMap.value[s.code] = s
    }
    // Get holdings
    const hlist = await api.holdings.list()
    const enriched = []
    for (const h of hlist) {
      if (h.quantity <= 0) continue
      try {
        const tradesRes = await api.holdings.getTrades(h.code)
        enriched.push({ ...h, trades: tradesRes.trades || [] })
      } catch (e) {
        enriched.push({ ...h, trades: [] })
      }
    }
    holdingsRaw.value = enriched
  } catch (e) {
    console.error('Load holdings failed:', e)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.holdings-page { max-width: 960px; margin: 0 auto; padding: 16px; }
.hp-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.hp-header h2 { margin: 0; font-size: 20px; }
.btn-ghost { color: #94a3b8; text-decoration: none; font-size: 14px; }
.btn-ghost:hover { color: #e2e8f0; }

.hp-summary-bar { display: flex; gap: 20px; flex-wrap: wrap; padding: 12px 16px; margin-bottom: 16px; }
.hp-summary-item { display: flex; flex-direction: column; gap: 2px; }
.hp-label { font-size: 11px; color: #64748b; }
.hp-value { font-size: 15px; font-weight: 600; color: #e2e8f0; }
.hp-pnl { font-weight: 700; }

.holdings-list { display: flex; flex-direction: column; gap: 10px; }
.holdings-item { padding: 0; overflow: hidden; }
.hi-header { display: flex; align-items: center; gap: 12px; padding: 12px 16px; cursor: pointer; transition: background 0.15s; }
.hi-header:hover { background: #1e293b; }
.hi-main { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; flex-wrap: wrap; }
.hi-name { font-size: 15px; font-weight: 600; color: #e2e8f0; }
.hi-code { font-size: 12px; color: #60a5fa; }
.hi-sector { font-size: 11px; color: #64748b; }
.hi-stats { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.hi-qty { font-size: 14px; font-weight: 600; }
.hi-cost { font-size: 12px; color: #94a3b8; }
.hi-price { font-size: 14px; font-weight: 600; }
.hi-change { font-size: 12px; font-weight: 500; }
.hi-pnl { font-size: 14px; font-weight: 600; }
.hi-realized { font-size: 12px; font-weight: 600; }
.hi-toggle { font-size: 14px; color: #64748b; margin-left: auto; }

.hi-detail { border-top: 1px solid #334155; padding: 14px 16px; }
.hi-detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.hi-detail-col { display: flex; flex-direction: column; gap: 6px; }
.hi-detail-row { display: flex; align-items: center; gap: 10px; }
.hi-dlabel { font-size: 12px; color: #94a3b8; min-width: 60px; }
.hi-dvalue { font-size: 14px; font-weight: 500; color: #e2e8f0; }
.hi-trades-header { font-size: 13px; font-weight: 600; color: #94a3b8; margin-bottom: 6px; }
.hi-trades-wrap { overflow-x: auto; }
.hi-trades-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.hi-trades-table th { text-align: left; padding: 6px 8px; border-bottom: 1px solid #334155; color: #94a3b8; font-weight: 500; }
.hi-trades-table td { padding: 6px 8px; border-bottom: 1px solid #1e293b; }
.hi-trades-table tr:last-child td { border-bottom: none; }
.hi-actions { margin-top: 12px; text-align: right; }
.btn-primary { display: inline-block; padding: 6px 16px; background: #1e3a5f; color: #60a5fa; border-radius: 6px; text-decoration: none; font-size: 13px; font-weight: 500; }
.btn-primary:hover { background: #2563eb; color: white; }

.up { color: #f87171; }
.down { color: #34d399; }
.t-profit { color: #fbbf24; }
.empty { color: #475569; font-size: 13px; text-align: center; padding: 20px 0; }

@media (max-width: 640px) {
  .hp-summary-bar { gap: 12px; }
  .hi-header { flex-wrap: wrap; gap: 8px; }
  .hi-stats { width: 100%; justify-content: flex-start; }
  .hi-detail-grid { grid-template-columns: 1fr; }
}
</style>
