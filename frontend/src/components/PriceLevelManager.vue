<template>
  <section class="card pl-card">
    <div class="pl-header">
      <div>
        <h3>📍 价格水位</h3>
        <p>分析判断、交易计划和持仓事实统一管理</p>
      </div>
      <button
        type="button"
        class="pl-current"
        :disabled="readonly || !data.current_price"
        title="点击将现价填入价格输入框"
        @click="useCurrentPrice"
      >
        <span>现价</span>
        <strong>{{ data.current_price ? `¥${fmtPrice(data.current_price)}` : '--' }}</strong>
        <small v-if="!readonly && data.current_price">点击填入</small>
      </button>
    </div>

    <div class="pl-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="{ active: filter === tab.key }"
        @click="filter = tab.key"
      >
        {{ tab.label }} <span>{{ countFor(tab.key) }}</span>
      </button>
    </div>

    <div v-if="loading" class="pl-empty">正在加载价格水位…</div>
    <div v-else-if="error" class="pl-error">{{ error }} <button @click="load">重试</button></div>
    <div v-else-if="filteredLevels.length === 0" class="pl-empty">当前分类暂无价格水位</div>
    <div v-else class="pl-list">
      <article v-for="level in filteredLevels" :key="level.id" :class="['pl-row', `family-${level.family}`, `state-${level.state}`]">
        <div class="pl-main">
          <div class="pl-title">
            <span class="pl-family">{{ familyLabel(level.family) }}</span>
            <strong>{{ level.label }}</strong>
            <span v-if="level.state !== 'active'" :class="['pl-state', `pl-state-${level.state}`]">{{ stateLabel(level.state) }}</span>
          </div>
          <div class="pl-meta">
            <span>{{ sourceLabel(level.source) }}</span>
            <span v-if="level.plan?.qty">{{ level.plan.side === 'buy' ? '买入' : '卖出' }} {{ level.plan.qty }} 股</span>
            <span v-if="level.proximity?.state === 'near'" class="near">临近</span>
            <span v-if="level.proximity?.state === 'triggered'" class="triggered">已触及</span>
            <span v-if="level.valid_until">有效至 {{ level.valid_until }}</span>
            <span v-if="level.note" :title="level.note" class="pl-note">{{ level.note }}</span>
          </div>
        </div>
        <div class="pl-price">
          <strong>¥{{ fmtPrice(level.price) }}</strong>
          <span v-if="diffPct(level.price) != null" :class="diffPct(level.price) >= 0 ? 'up' : 'down'">
            {{ diffPct(level.price) >= 0 ? '+' : '' }}{{ diffPct(level.price).toFixed(1) }}%
          </span>
        </div>
        <div v-if="!readonly && level.family !== 'fact'" class="pl-actions">
          <button v-if="level.state === 'proposed'" class="accept" @click="changeState(level, 'active')">接受</button>
          <button v-if="level.state === 'proposed'" @click="changeState(level, 'invalidated')">否决</button>
          <button v-if="level.source === 'manual'" @click="startEdit(level)">编辑</button>
          <button v-if="level.state === 'active'" @click="changeState(level, 'retired')">归档</button>
          <button v-else-if="level.state !== 'proposed'" @click="changeState(level, 'active')">恢复</button>
          <button v-if="level.source === 'manual'" class="danger" @click="remove(level)">删除</button>
        </div>
      </article>
    </div>

    <form v-if="!readonly" class="pl-form" @submit.prevent="save">
      <div class="pl-form-head">
        <strong>{{ editingId ? '编辑价格水位' : '添加价格水位' }}</strong>
        <span>{{ editingId ? '修改选中水位的属性' : '记录观察价格或交易计划' }}</span>
      </div>
      <label class="pl-field">
        <span>水位类别</span>
        <select v-model="form.family" :disabled="!!editingId" @change="chooseDefaultType">
          <option value="analysis">分析水位</option>
          <option value="plan">交易计划</option>
        </select>
      </label>
      <label class="pl-field">
        <span>类型</span>
        <select v-model="form.type">
          <option v-for="type in formTypes" :key="type.key" :value="type.key">{{ type.label }}</option>
        </select>
      </label>
      <label class="pl-field">
        <span>价格</span>
        <input v-model.number="form.price" type="number" min="0" step="0.001" placeholder="输入价格" required />
      </label>
      <label v-if="form.family === 'plan'" class="pl-field">
        <span>数量</span>
        <input v-model.number="form.qty" type="number" min="1" step="100" placeholder="可选" />
      </label>
      <label class="pl-field pl-date-field">
        <span>有效期</span>
        <div class="pl-date-control">
          <input ref="validUntilInput" v-model="form.valid_until" type="date" title="有效期（可空）" />
          <button type="button" title="选择日期" aria-label="选择有效期" @click="openDatePicker">📅</button>
        </div>
      </label>
      <label class="pl-field pl-note-field">
        <span>依据或备注</span>
        <input v-model="form.note" maxlength="200" placeholder="可选，例如观察原因" />
      </label>
      <div class="pl-form-actions">
        <button class="primary" :disabled="saving">{{ saving ? '保存中…' : (editingId ? '保存修改' : '添加水位') }}</button>
        <button v-if="editingId" type="button" @click="resetForm">取消编辑</button>
      </div>
    </form>

    <details v-if="!readonly" class="pl-tools">
      <summary>批量计划工具</summary>
      <div class="pl-grid-form">
        <span>网格</span>
        <input v-model.number="grid.base_price" type="number" min="0" step="0.01" :placeholder="data.current_price ? `基准 ${fmtPrice(data.current_price)}` : '基准价'" />
        <input v-model.number="grid.step_pct" type="number" min="0.1" max="50" step="0.5" placeholder="步长%" />
        <input v-model.number="grid.up" type="number" min="0" max="20" placeholder="上档" />
        <input v-model.number="grid.down" type="number" min="0" max="20" placeholder="下档" />
        <button @click="applyGrid">{{ hasStrategy ? '重算网格' : '生成网格' }}</button>
        <button v-if="hasStrategy" @click="clearStrategy">清除策略计划</button>
        <button v-if="hasAgentPlans" @click="clearAgent">清除 AI 计划</button>
      </div>
    </details>

    <p v-if="actionError" class="pl-error">{{ actionError }}</p>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import api from '../api.js'

const props = defineProps({
  code: { type: String, required: true },
  readonly: { type: Boolean, default: false },
})
const emit = defineEmits(['changed'])

const emptyData = () => ({ current_price: null, price_updated: null, types: [], levels: [] })
const data = ref(emptyData())
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const actionError = ref('')
const filter = ref('all')
const editingId = ref(null)
const validUntilInput = ref(null)
const form = ref({ family: 'analysis', type: 'support', price: null, qty: null, valid_until: '', note: '' })
const grid = ref({ base_price: null, step_pct: 3, up: 3, down: 3 })

const tabs = [
  { key: 'all', label: '全部' },
  { key: 'analysis', label: '分析' },
  { key: 'plan', label: '计划' },
  { key: 'fact', label: '事实' },
  { key: 'proposed', label: '待确认' },
]
const filteredLevels = computed(() => data.value.levels.filter(level => {
  if (filter.value === 'all') return true
  if (filter.value === 'proposed') return level.state === 'proposed'
  return level.family === filter.value
}))
const formTypes = computed(() => data.value.types.filter(type => type.family === form.value.family))
const hasStrategy = computed(() => data.value.levels.some(level => level.family === 'plan' && level.source === 'strategy'))
const hasAgentPlans = computed(() => data.value.levels.some(level => level.family === 'plan' && level.source === 'agent'))

function countFor(key) {
  if (key === 'all') return data.value.levels.length
  if (key === 'proposed') return data.value.levels.filter(level => level.state === 'proposed').length
  return data.value.levels.filter(level => level.family === key).length
}

function familyLabel(family) {
  return { analysis: '分析', plan: '计划', fact: '事实' }[family] || family
}
function stateLabel(state) {
  return { proposed: '待确认', active: '有效', retired: '已归档', invalidated: '已失效', expired: '已过期' }[state] || state
}
function sourceLabel(source) {
  return { manual: '手动', agent: 'AI', strategy: '策略', system: '系统' }[source] || source
}
function fmtPrice(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number.toFixed(number < 1 ? 3 : 2) : '--'
}
function diffPct(price) {
  const current = Number(data.value.current_price)
  const target = Number(price)
  if (!Number.isFinite(current) || current <= 0 || !Number.isFinite(target)) return null
  return (target - current) / current * 100
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const result = await api.stocks.listPriceLevels(props.code)
    data.value = result && Array.isArray(result.levels) ? result : emptyData()
    if (!formTypes.value.some(type => type.key === form.value.type)) chooseDefaultType()
  } catch (e) {
    error.value = e.message || '价格水位加载失败'
  } finally {
    loading.value = false
  }
}

function chooseDefaultType() {
  form.value.type = formTypes.value[0]?.key || ''
}
function useCurrentPrice() {
  const current = Number(data.value.current_price)
  if (Number.isFinite(current) && current > 0) form.value.price = current
}
function openDatePicker() {
  const input = validUntilInput.value
  if (!input) return
  try {
    if (typeof input.showPicker === 'function') input.showPicker()
    else input.focus()
  } catch {
    input.focus()
  }
}
function resetForm() {
  editingId.value = null
  form.value = { family: 'analysis', type: data.value.types.find(type => type.family === 'analysis')?.key || '', price: null, qty: null, valid_until: '', note: '' }
}
function startEdit(level) {
  editingId.value = level.id
  form.value = {
    family: level.family,
    type: level.type,
    price: level.price,
    qty: level.plan?.qty || null,
    valid_until: level.valid_until || '',
    note: level.note || '',
  }
}
function applyResult(result) {
  data.value = result
  emit('changed')
}
async function save() {
  actionError.value = ''
  saving.value = true
  try {
    const payload = {
      family: form.value.family,
      type: form.value.type,
      price: form.value.price,
      qty: form.value.qty || null,
      valid_until: form.value.valid_until || null,
      note: form.value.note.trim(),
    }
    const result = editingId.value
      ? await api.stocks.updatePriceLevel(props.code, editingId.value, payload)
      : await api.stocks.createPriceLevel(props.code, payload)
    applyResult(result)
    resetForm()
  } catch (e) {
    actionError.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}
async function changeState(level, state) {
  actionError.value = ''
  try {
    const patch = state === 'active' && level.state === 'expired'
      ? { state, valid_until: null }
      : { state }
    applyResult(await api.stocks.updatePriceLevel(props.code, level.id, patch))
  } catch (e) {
    actionError.value = e.message || '状态更新失败'
  }
}
async function remove(level) {
  if (!window.confirm(`删除价格水位“${level.label} ¥${fmtPrice(level.price)}”？`)) return
  try {
    applyResult(await api.stocks.deletePriceLevel(props.code, level.id))
  } catch (e) {
    actionError.value = e.message || '删除失败'
  }
}
async function applyGrid() {
  actionError.value = ''
  try {
    await api.ladder.applyStrategy(props.code, 'grid', {
      base_price: grid.value.base_price || null,
      step_pct: grid.value.step_pct || 3,
      up: grid.value.up ?? 3,
      down: grid.value.down ?? 3,
    })
    await load()
    emit('changed')
  } catch (e) {
    actionError.value = e.message || '网格生成失败'
  }
}
async function clearStrategy() {
  if (!window.confirm('清除策略生成的所有计划水位？')) return
  await api.ladder.clearStrategy(props.code)
  await load()
  emit('changed')
}
async function clearAgent() {
  if (!window.confirm('清除 AI 生成的所有计划水位？')) return
  await api.ladder.clearAgent(props.code)
  await load()
  emit('changed')
}

watch(() => props.code, load)
onMounted(load)
</script>

<style scoped>
.pl-card { padding: 0; overflow: hidden; }
.pl-header { display: flex; justify-content: space-between; align-items: center; padding: 16px 18px 10px; }
.pl-header h3 { margin: 0; }
.pl-header p { margin: 4px 0 0; color: #64748b; font-size: 12px; }
.pl-current { display: flex; align-items: baseline; gap: 8px; border: 1px solid transparent; background: transparent; color: #94a3b8; font-size: 12px; padding: 5px 8px; }
.pl-current:not(:disabled):hover { border-color: #334155; background: #0f172a; }
.pl-current:disabled { cursor: default; opacity: 1; }
.pl-current strong { color: #e2e8f0; font-size: 18px; }
.pl-current small { color: #38bdf8; font-size: 10px; }
.pl-tabs { display: flex; gap: 5px; padding: 0 18px 10px; overflow-x: auto; }
.pl-tabs button { border: 1px solid #334155; background: #0f172a; color: #94a3b8; border-radius: 999px; padding: 4px 10px; white-space: nowrap; }
.pl-tabs button.active { border-color: #0891b2; color: #67e8f9; background: #083344; }
.pl-tabs span { opacity: .7; margin-left: 3px; }
.pl-list { border-top: 1px solid #334155; border-bottom: 1px solid #334155; background: rgba(15, 23, 42, .35); }
.pl-row { display: grid; grid-template-columns: minmax(0, 1fr) 110px auto; gap: 12px; align-items: center; padding: 10px 18px; border-bottom: 1px solid #1e293b; border-left: 3px solid #64748b; }
.pl-row.family-analysis { border-left-color: #38bdf8; }
.pl-row.family-plan { border-left-color: #f59e0b; }
.pl-row.family-fact { border-left-color: #a78bfa; }
.pl-row.state-retired, .pl-row.state-invalidated, .pl-row.state-expired { opacity: .55; }
.pl-main { min-width: 0; }
.pl-title { display: flex; align-items: center; gap: 7px; font-size: 13px; }
.pl-family, .pl-state { border-radius: 4px; padding: 1px 5px; font-size: 10px; background: #1e293b; color: #94a3b8; }
.pl-state-proposed { background: #422006; color: #fbbf24; }
.pl-meta { display: flex; gap: 9px; margin-top: 4px; color: #64748b; font-size: 11px; min-width: 0; }
.pl-note { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.near { color: #fbbf24; }.triggered { color: #fb7185; }
.pl-price { text-align: right; display: flex; flex-direction: column; }
.pl-price strong { color: #e2e8f0; }.pl-price span { font-size: 11px; }
.up { color: #f87171; }.down { color: #4ade80; }
.pl-actions { display: flex; gap: 4px; flex-wrap: wrap; justify-content: flex-end; }
.pl-actions button { padding: 3px 7px; font-size: 11px; }
.pl-actions .accept { color: #34d399; }.pl-actions .danger { color: #f87171; }
.pl-form { display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 10px; align-items: end; margin-top: 12px; padding: 14px 18px 16px; border-top: 2px solid #334155; background: #0a101c; }
.pl-form-head { grid-column: 1 / -1; display: flex; align-items: baseline; gap: 10px; padding-bottom: 9px; border-bottom: 1px solid #1e293b; }
.pl-form-head strong { color: #e2e8f0; font-size: 14px; white-space: nowrap; }
.pl-form-head span { color: #64748b; font-size: 11px; }
.pl-field { display: flex; flex-direction: column; gap: 5px; min-width: 0; color: #94a3b8; font-size: 11px; }
.pl-field > input, .pl-field > select, .pl-date-control input, .pl-grid-form input { width: 100%; min-width: 0; height: 35px; padding: 6px 8px; }
.pl-note-field { grid-column: span 2; }
.pl-date-control { display: grid; grid-template-columns: minmax(0, 1fr) 36px; gap: 5px; }
.pl-date-control button { height: 35px; padding: 0; border: 1px solid #475569; background: #1e293b; color: #cbd5e1; }
.pl-form-actions { grid-column: 1 / -1; display: flex; justify-content: flex-end; gap: 8px; padding-top: 2px; }
.pl-form-actions button { min-width: 96px; white-space: nowrap; }
.pl-tools { padding: 10px 18px 14px; color: #94a3b8; font-size: 12px; }
.pl-tools summary { cursor: pointer; }
.pl-grid-form { display: flex; gap: 7px; align-items: center; flex-wrap: wrap; margin-top: 9px; }
.pl-grid-form input { width: 105px; }
.pl-empty, .pl-error { padding: 24px 18px; text-align: center; color: #64748b; }
.pl-error { color: #fca5a5; }
@media (max-width: 850px) {
  .pl-row { grid-template-columns: 1fr auto; }
  .pl-actions { grid-column: 1 / -1; justify-content: flex-start; }
  .pl-form { grid-template-columns: 1fr 1fr; }
  .pl-note-field { grid-column: span 2; }
}
@media (max-width: 520px) {
  .pl-header { align-items: flex-start; }
  .pl-current { flex-wrap: wrap; justify-content: flex-end; max-width: 130px; }
  .pl-current small { flex-basis: 100%; text-align: right; }
  .pl-form { grid-template-columns: minmax(0, 1fr); }
  .pl-note-field { grid-column: auto; }
  .pl-form-head { align-items: flex-start; flex-direction: column; gap: 3px; }
  .pl-form-actions { justify-content: stretch; }
  .pl-form-actions button { flex: 1; }
}
</style>
