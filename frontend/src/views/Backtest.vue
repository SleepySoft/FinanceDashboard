<template>
  <div class="backtest-page">
    <h2>回测 Playground</h2>

    <div class="backtest-form card">
      <!-- 1. 选择策略 -->
      <div class="form-section">
        <label>策略</label>
        <select v-model="form.strategy_id" @change="onStrategyChange">
          <option value="">-- 选择策略 --</option>
          <option v-for="s in strategies" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
      </div>

      <!-- 2. 参数设置 -->
      <div class="form-section" v-if="currentStrategy && currentStrategy.params">
        <label>参数</label>
        <div class="params-row">
          <div v-for="p in currentStrategy.params" :key="p.name" class="param-input">
            <span class="param-label">{{ p.description || p.name }}</span>
            <input
              v-model.number="form.params[p.name]"
              :type="p.type === 'int' || p.type === 'float' ? 'number' : 'text'"
              :min="p.min"
              :max="p.max"
              :step="p.step || 1"
            />
          </div>
        </div>
      </div>

      <!-- 3. 回测范围 -->
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

      <!-- 4. 资金设置 -->
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

      <!-- 操作 -->
      <div class="form-actions">
        <button class="primary" @click="runBacktest" :disabled="loading">
          {{ loading ? '回测中...' : '开始回测' }}
        </button>
        <label class="checkbox">
          <input type="checkbox" v-model="form.use_cache" />
          使用缓存
        </label>
        <label class="checkbox">
          <input type="checkbox" v-model="frameMode" />
          逐帧模式
        </label>
      </div>
    </div>

    <!-- 结果展示 -->
    <div v-if="result" class="result card">
      <div class="result-header">
        <h3>回测结果</h3>
        <span v-if="result.from_cache" class="cache-tag">⚡ 来自缓存</span>
      </div>

      <!-- 汇总指标 -->
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

      <!-- 权益曲线 -->
      <div v-if="result.equity_curve && result.equity_curve.length" class="chart-section">
        <h4>权益曲线</h4>
        <svg :viewBox="`0 0 ${chartWidth} ${chartHeight}`" class="equity-chart">
          <polyline
            :points="equityPoints"
            fill="none"
            stroke="#3b82f6"
            stroke-width="2"
          />
        </svg>
      </div>

      <!-- 各股票结果 -->
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

      <!-- 逐帧播放器 -->
      <div v-if="frames && frames.length" class="frame-player">
        <h4>逐帧回放</h4>
        <div class="frame-controls">
          <button @click="frameIndex = 0">⏮</button>
          <button @click="prevFrame">◀</button>
          <span class="frame-info">{{ frames[frameIndex]?.date }} ({{ frameIndex + 1 }} / {{ frames.length }})</span>
          <button @click="nextFrame">▶</button>
          <button @click="playFrames">{{ playing ? '⏸' : '▶' }}</button>
        </div>
        <div class="frame-detail">
          <div class="frame-bar">
            <div>O: {{ frames[frameIndex]?.bar?.open }}</div>
            <div>H: {{ frames[frameIndex]?.bar?.high }}</div>
            <div>L: {{ frames[frameIndex]?.bar?.low }}</div>
            <div>C: {{ frames[frameIndex]?.bar?.close }}</div>
          </div>
          <div class="frame-signal" :class="signalClass(frames[frameIndex]?.signal)">
            信号: {{ signalText(frames[frameIndex]?.signal) }}
          </div>
          <div class="frame-portfolio">
            现金: {{ frames[frameIndex]?.portfolio?.cash?.toFixed(0) }}
            | 市值: {{ frames[frameIndex]?.portfolio?.equity?.toFixed(0) }}
            | 持仓: {{ frames[frameIndex]?.position?.quantity }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const strategies = ref([])
const currentStrategy = ref(null)
const loading = ref(false)
const result = ref(null)
const frames = ref(null)
const frameMode = ref(false)
const frameIndex = ref(0)
const playing = ref(false)
let playTimer = null

const chartWidth = 800
const chartHeight = 200

const form = ref({
  strategy_id: '',
  params: {},
  start_date: '2023-01-01',
  end_date: '2024-12-31',
  adjust: 'qfq',
  config: {
    initial_cash: 100000,
    commission: 0.00025,
    size: 0.2,
  },
  use_cache: true,
})

const codesInput = ref('000001.SZ')

// 从 URL 参数预填策略
watch(() => route.query.strategy, (sid) => {
  if (sid && strategies.value.length) {
    form.value.strategy_id = sid
    onStrategyChange()
  }
}, { immediate: false })

async function loadStrategies() {
  try {
    const res = await fetch('/api/backtest/strategies')
    const data = await res.json()
    strategies.value = data.strategies || []
    if (route.query.strategy) {
      form.value.strategy_id = route.query.strategy
      onStrategyChange()
    }
  } catch (e) {
    console.error('Failed to load strategies:', e)
  }
}

function onStrategyChange() {
  const s = strategies.value.find(x => x.id === form.value.strategy_id)
  currentStrategy.value = s || null
  // 重置参数为默认值
  form.value.params = {}
  if (s && s.params) {
    for (const p of s.params) {
      form.value.params[p.name] = p.default
    }
  }
}

async function runBacktest() {
  const codes = codesInput.value.split(/[,，\s]+/).filter(Boolean)
  if (!codes.length) {
    alert('请输入股票代码')
    return
  }
  if (!form.value.strategy_id) {
    alert('请选择策略')
    return
  }

  loading.value = true
  result.value = null
  frames.value = null

  try {
    if (frameMode.value && codes.length === 1) {
      // 逐帧模式
      const res = await fetch('/api/backtest/run/frame', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_id: form.value.strategy_id,
          params: form.value.params,
          code: codes[0],
          start_date: form.value.start_date,
          end_date: form.value.end_date,
          adjust: form.value.adjust,
          config: form.value.config,
        })
      })
      const data = await res.json()
      if (res.ok) {
        frames.value = data.frames
        frameIndex.value = 0
        result.value = { id: data.id, from_cache: false }
      } else {
        alert(data.detail || '回测失败')
      }
    } else {
      // 快速回测
      const res = await fetch('/api/backtest/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_id: form.value.strategy_id,
          params: form.value.params,
          codes: codes,
          start_date: form.value.start_date,
          end_date: form.value.end_date,
          adjust: form.value.adjust,
          config: form.value.config,
          use_cache: form.value.use_cache,
        })
      })
      const data = await res.json()
      if (res.ok) {
        result.value = data
      } else {
        alert(data.detail || '回测失败')
      }
    }
  } catch (e) {
    alert('请求失败: ' + e.message)
  } finally {
    loading.value = false
  }
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

function signalText(s) {
  if (s === 1) return '买入'
  if (s === -1) return '卖出'
  return '持仓'
}
function signalClass(s) {
  if (s === 1) return 'signal-buy'
  if (s === -1) return 'signal-sell'
  return 'signal-hold'
}

function nextFrame() {
  if (frames.value && frameIndex.value < frames.value.length - 1) frameIndex.value++
}
function prevFrame() {
  if (frameIndex.value > 0) frameIndex.value--
}
function playFrames() {
  if (playing.value) {
    playing.value = false
    clearInterval(playTimer)
  } else {
    playing.value = true
    playTimer = setInterval(() => {
      if (frameIndex.value >= (frames.value?.length || 0) - 1) {
        playing.value = false
        clearInterval(playTimer)
      } else {
        frameIndex.value++
      }
    }, 500)
  }
}

onMounted(loadStrategies)
</script>

<style scoped>
.backtest-page h2 {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 16px;
}

.backtest-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
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
.param-input input {
  width: 100px;
}
.param-label {
  font-size: 12px;
  color: #64748b;
}

.date-row,
.config-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.date-row > div,
.config-row > div {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.date-row input,
.config-row input {
  width: 140px;
}

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
.checkbox input {
  width: auto;
}

/* 结果区域 */
.result {
  margin-top: 16px;
}
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
.metric-value {
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 4px;
}
.metric-value.up { color: #34d399; }
.metric-value.down { color: #f87171; }
.metric-label {
  font-size: 12px;
  color: #64748b;
}

.chart-section h4,
.stock-results h4,
.frame-player h4 {
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

.stock-results {
  margin-top: 16px;
}
.stock-result-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #334155;
  font-size: 13px;
}
.error-text {
  color: #f87171;
}

/* 逐帧播放器 */
.frame-player {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #334155;
}
.frame-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.frame-controls button {
  background: #1e293b;
  color: #e2e8f0;
  border: 1px solid #475569;
  padding: 4px 10px;
  border-radius: 4px;
}
.frame-info {
  font-size: 13px;
  color: #94a3b8;
  min-width: 180px;
  text-align: center;
}
.frame-detail {
  background: #1e293b;
  border-radius: 8px;
  padding: 12px;
  font-size: 13px;
}
.frame-bar {
  display: flex;
  gap: 16px;
  margin-bottom: 8px;
}
.frame-signal {
  font-weight: 600;
  margin-bottom: 6px;
}
.signal-buy { color: #34d399; }
.signal-sell { color: #f87171; }
.signal-hold { color: #94a3b8; }

@media (max-width: 640px) {
  .date-row, .config-row {
    flex-direction: column;
  }
  .metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
