<template>
  <div class="backtest-page">
    <h2>回测 Playground</h2>

    <!-- 模式切换 -->
    <div class="mode-tabs">
      <button :class="{active: mode === 'strategy'}" @click="mode = 'strategy'">策略回测</button>
      <button :class="{active: mode === 'factor'}" @click="mode = 'factor'">因子回测</button>
    </div>

    <div class="backtest-form card">
      <!-- ===== 策略回测模式 ===== -->
      <template v-if="mode === 'strategy'">
        <div class="form-section">
          <label>策略</label>
          <select v-model="form.strategy_id" @change="onStrategyChange">
            <option value="">-- 选择策略 --</option>
            <option v-for="s in strategies" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </div>

        <div class="form-section" v-if="currentStrategy && currentStrategy.params">
          <label>参数</label>
          <div class="params-row">
            <div v-for="p in currentStrategy.params" :key="p.name" class="param-input">
              <span class="param-label">{{ p.description || p.name }}</span>
              <input v-model.number="form.params[p.name]" type="number" :min="p.min" :max="p.max" :step="p.step || 1" />
            </div>
          </div>
        </div>
      </template>

      <!-- ===== 因子回测模式 ===== -->
      <template v-if="mode === 'factor'">
        <div class="factor-section">
          <div class="factor-group">
            <div class="factor-header">
              <span class="factor-title">📈 买入条件</span>
              <select v-model="factorLogic" class="logic-select">
                <option value="and">全部满足</option>
                <option value="or">任一满足</option>
              </select>
            </div>
            <div v-for="(cond, i) in buyConditions" :key="i" class="condition-row">
              <select v-model="cond.factor_id" @change="onFactorChange(cond)">
                <option value="">-- 因子 --</option>
                <option v-for="f in factors" :key="f.id" :value="f.id">{{ f.name }}</option>
              </select>
              <select v-model="cond.operator">
                <option value="<">&lt;</option>
                <option value="<=">&lt;=</option>
                <option value=">">&gt;</option>
                <option value=">=">&gt;=</option>
                <option value="cross_above">上穿</option>
                <option value="cross_below">下穿</option>
              </select>
              <input v-model.number="cond.value" type="number" placeholder="阈值" class="cond-value" />
              <button class="btn-mini danger" @click="removeBuyCondition(i)">✕</button>
            </div>
            <button class="btn-ghost btn-small" @click="addBuyCondition">+ 添加买入条件</button>
          </div>

          <div class="factor-group">
            <div class="factor-header">
              <span class="factor-title">📉 卖出条件</span>
            </div>
            <div v-for="(cond, i) in sellConditions" :key="i" class="condition-row">
              <select v-model="cond.factor_id" @change="onFactorChange(cond)">
                <option value="">-- 因子 --</option>
                <option v-for="f in factors" :key="f.id" :value="f.id">{{ f.name }}</option>
              </select>
              <select v-model="cond.operator">
                <option value="<">&lt;</option>
                <option value="<=">&lt;=</option>
                <option value=">">&gt;</option>
                <option value=">=">&gt;=</option>
                <option value="cross_above">上穿</option>
                <option value="cross_below">下穿</option>
              </select>
              <input v-model.number="cond.value" type="number" placeholder="阈值" class="cond-value" />
              <button class="btn-mini danger" @click="removeSellCondition(i)">✕</button>
            </div>
            <button class="btn-ghost btn-small" @click="addSellCondition">+ 添加卖出条件</button>
          </div>
        </div>
      </template>

      <!-- ===== 公共设置 ===== -->
      <div class="form-section">
        <label>股票代码（支持多个，逗号分隔）</label>
        <input v-model="codesInput" placeholder="000001.SZ, 000002.SZ" />

        <div class="date-row">
          <div>
            <label>开始日期</label>
            <input type="date" v-model="form.start_date" />
          </div>
          <div>
            <label>结束日期</label>
            <input type="date" v-model="form.end_date" />
          </div>
          <div>
            <label>复权</label>
            <select v-model="form.adjust">
              <option value="qfq">前复权</option>
              <option value="hfq">后复权</option>
              <option value="none">不复权</option>
            </select>
          </div>
        </div>
      </div>

      <div class="form-section">
        <div class="config-row">
          <div>
            <label>初始资金</label>
            <input type="number" v-model.number="form.config.initial_cash" step="10000" />
          </div>
          <div>
            <label>佣金率</label>
            <input type="number" v-model.number="form.config.commission" step="0.00001" />
          </div>
          <div>
            <label>仓位比例</label>
            <input type="number" v-model.number="form.config.size" step="0.05" min="0.05" max="1" />
          </div>
        </div>
      </div>

      <div class="form-actions">
        <button class="primary" @click="runBacktest" :disabled="loading">
          {{ loading ? '回测中...' : '开始回测' }}
        </button>
        <label class="checkbox">
          <input type="checkbox" v-model="form.use_cache" />
          使用缓存
        </label>
        <label v-if="mode === 'strategy'" class="checkbox">
          <input type="checkbox" v-model="frameMode" />
          逐帧模式
        </label>
      </div>
    </div>

    <!-- ===== 结果展示 ===== -->
    <div v-if="result" class="result card">
      <div class="result-header">
        <h3>回测结果</h3>
        <span v-if="result.from_cache" class="cache-tag">⚡ 来自缓存</span>
      </div>

      <div v-if="result.summary" class="metrics-grid">
        <div class="metric-box">
          <div class="metric-value" :class="result.summary.total_return >= 0 ? 'up' : 'down'">
            {{ (result.summary.total_return * 100).toFixed(2) }}%
          </div>
          <div class="metric-label">总收益</div>
        </div>
        <div class="metric-box">
          <div class="metric-value">{{ result.summary.total_trades }}</div>
          <div class="metric-label">交易次数</div>
        </div>
        <div class="metric-box">
          <div class="metric-value">{{ (result.summary.win_rate * 100).toFixed(1) }}%</div>
          <div class="metric-label">胜率</div>
        </div>
        <div class="metric-box">
          <div class="metric-value">{{ result.summary.profit_factor?.toFixed(2) || '-' }}</div>
          <div class="metric-label">盈亏比</div>
        </div>
      </div>

      <div v-if="result.equity_curve && result.equity_curve.length" class="chart-section">
        <h4>权益曲线</h4>
        <svg :viewBox="`0 0 ${chartWidth} ${chartHeight}`" class="equity-chart">
          <polyline :points="equityPoints" fill="none" stroke="#3b82f6" stroke-width="2" />
        </svg>
      </div>

      <div v-if="result.results" class="stock-results">
        <h4>各股票表现</h4>
        <div v-for="(r, code) in result.results" :key="code" class="stock-result-item">
          <strong>{{ code }}</strong>
          <span v-if="r.error" class="error-text">{{ r.error }}</span>
          <span v-else>
            收益: <b :class="r.metrics.total_return >= 0 ? 'up' : 'down'">{{ (r.metrics.total_return * 100).toFixed(2) }}%</b>
            | 交易: {{ r.trade_count }}
            | 胜率: {{ (r.metrics.win_rate * 100).toFixed(1) }}%
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const mode = ref('strategy') // 'strategy' | 'factor'
const strategies = ref([])
const factors = ref([])
const currentStrategy = ref(null)
const loading = ref(false)
const result = ref(null)
const frameMode = ref(false)

const factorLogic = ref('and')
const buyConditions = ref([{ factor_id: '', params: {}, operator: '<', value: 30 }])
const sellConditions = ref([{ factor_id: '', params: {}, operator: '>', value: 70 }])

const chartWidth = 800
const chartHeight = 200

const form = ref({
  strategy_id: '',
  params: {},
  start_date: '2023-01-01',
  end_date: '2024-12-31',
  adjust: 'qfq',
  config: { initial_cash: 100000, commission: 0.00025, size: 0.2 },
  use_cache: true,
})
const codesInput = ref('000001.SZ')

async function loadStrategies() {
  try {
    const res = await fetch('/api/backtest/strategies')
    const data = await res.json()
    strategies.value = data.strategies || []
  } catch (e) { console.error(e) }
}

async function loadFactors() {
  try {
    const res = await fetch('/api/backtest/factors')
    const data = await res.json()
    factors.value = data.factors || []
  } catch (e) { console.error(e) }
}

function onStrategyChange() {
  const s = strategies.value.find(x => x.id === form.value.strategy_id)
  currentStrategy.value = s || null
  form.value.params = {}
  if (s && s.params) {
    for (const p of s.params) form.value.params[p.name] = p.default
  }
}

function onFactorChange(cond) {
  const f = factors.value.find(x => x.id === cond.factor_id)
  cond.params = {}
  if (f && f.params) {
    for (const p of f.params) cond.params[p.name] = p.default
  }
}

function addBuyCondition() { buyConditions.value.push({ factor_id: '', params: {}, operator: '<', value: 0 }) }
function removeBuyCondition(i) { buyConditions.value.splice(i, 1) }
function addSellCondition() { sellConditions.value.push({ factor_id: '', params: {}, operator: '>', value: 0 }) }
function removeSellCondition(i) { sellConditions.value.splice(i, 1) }

async function runBacktest() {
  const codes = codesInput.value.split(/[,，\s]+/).filter(Boolean)
  if (!codes.length) { alert('请输入股票代码'); return }
  loading.value = true
  result.value = null

  try {
    if (mode.value === 'strategy') {
      await runStrategyBacktest(codes)
    } else {
      await runFactorBacktest(codes)
    }
  } catch (e) {
    alert('请求失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

async function runStrategyBacktest(codes) {
  if (!form.value.strategy_id) { alert('请选择策略'); return }

  const payload = {
    strategy_id: form.value.strategy_id,
    params: form.value.params,
    codes: codes,
    start_date: form.value.start_date,
    end_date: form.value.end_date,
    adjust: form.value.adjust,
    config: form.value.config,
    use_cache: form.value.use_cache,
  }

  if (frameMode.value && codes.length === 1) {
    const res = await fetch('/api/backtest/run/frame', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...payload, code: codes[0] })
    })
    const data = await res.json()
    if (!res.ok) alert(data.detail || '回测失败')
    else result.value = data
  } else {
    const res = await fetch('/api/backtest/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    const data = await res.json()
    if (!res.ok) alert(data.detail || '回测失败')
    else result.value = data
  }
}

async function runFactorBacktest(codes) {
  // 过滤掉未完成的条件
  const validBuy = buyConditions.value.filter(c => c.factor_id)
  const validSell = sellConditions.value.filter(c => c.factor_id)

  if (!validBuy.length && !validSell.length) {
    alert('请至少设置一个买入或卖出条件')
    return
  }

  const res = await fetch('/api/backtest/factor-run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      codes: codes,
      buy_conditions: validBuy,
      sell_conditions: validSell,
      start_date: form.value.start_date,
      end_date: form.value.end_date,
      adjust: form.value.adjust,
      logic: factorLogic.value,
      config: form.value.config,
    })
  })
  const data = await res.json()
  if (!res.ok) alert(data.detail || '回测失败')
  else result.value = data
}

const equityPoints = computed(() => {
  if (!result.value?.equity_curve?.length) return ''
  const data = result.value.equity_curve
  const values = data.map(d => d.value)
  const minV = Math.min(...values)
  const maxV = Math.max(...values)
  const range = maxV - minV || 1
  const stepX = chartWidth / (data.length - 1 || 1)
  return data.map((d, i) => {
    const x = i * stepX
    const y = chartHeight - ((d.value - minV) / range) * chartHeight
    return `${x},${y}`
  }).join(' ')
})

onMounted(() => {
  loadStrategies()
  loadFactors()
})
</script>

<style scoped>
.backtest-page h2 { font-size: 18px; font-weight: 600; margin-bottom: 12px; }

.mode-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.mode-tabs button {
  background: #1e293b;
  color: #94a3b8;
  border: 1px solid #334155;
  padding: 8px 20px;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
}
.mode-tabs button.active {
  background: #3b82f6;
  color: white;
  border-color: #3b82f6;
}

.backtest-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.form-section label {
  font-size: 13px;
  color: #94a3b8;
  font-weight: 500;
}
.form-section input,
.form-section select {
  width: 100%;
  max-width: 400px;
}

.params-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
.param-input {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.param-input input { width: 100px; }
.param-label { font-size: 12px; color: #64748b; }

.date-row, .config-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.date-row > div, .config-row > div {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.date-row input, .config-row input { width: 140px; }

.form-actions {
  display: flex;
  align-items: center;
  gap: 16px;
  padding-top: 8px;
  border-top: 1px solid #334155;
}
.form-actions button.primary {
  background: #3b82f6;
  color: white;
  padding: 10px 24px;
  font-size: 14px;
}
.checkbox {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #94a3b8;
  cursor: pointer;
}
.checkbox input { width: auto; }

/* 因子回测 */
.factor-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.factor-group {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 14px;
}
.factor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.factor-title {
  font-size: 14px;
  font-weight: 600;
}
.logic-select {
  width: auto !important;
  font-size: 12px;
  padding: 4px 8px !important;
}
.condition-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
.condition-row select {
  width: auto;
  min-width: 100px;
}
.cond-value {
  width: 80px !important;
}
.btn-mini {
  padding: 2px 8px;
  font-size: 12px;
  border-radius: 4px;
  border: none;
  cursor: pointer;
}
.btn-mini.danger {
  background: #7f1d1d;
  color: #f87171;
}
.btn-small {
  padding: 6px 12px;
  font-size: 12px;
}

/* 结果 */
.result { margin-top: 16px; }
.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.cache-tag {
  font-size: 12px;
  color: #fbbf24;
  background: #713f12;
  padding: 2px 8px;
  border-radius: 4px;
}
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}
.metric-box {
  background: #1e293b;
  border-radius: 8px;
  padding: 14px;
  text-align: center;
}
.metric-value { font-size: 20px; font-weight: 700; margin-bottom: 4px; }
.metric-value.up { color: #34d399; }
.metric-value.down { color: #f87171; }
.metric-label { font-size: 12px; color: #64748b; }

.chart-section h4,
.stock-results h4 {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 10px;
  color: #cbd5e1;
}
.equity-chart {
  width: 100%;
  height: 180px;
  background: #1e293b;
  border-radius: 8px;
}
.stock-results { margin-top: 16px; }
.stock-result-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #334155;
  font-size: 13px;
}
.error-text { color: #f87171; }

@media (max-width: 640px) {
  .date-row, .config-row, .condition-row { flex-direction: column; }
  .condition-row select, .cond-value { width: 100% !important; }
  .metrics-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
