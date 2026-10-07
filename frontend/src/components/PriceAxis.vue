<template>
  <div v-if="hasData" class="price-axis-wrap">
    <div class="pa-toolbar">
      <div class="pa-summary">
        <span v-if="nextLevel" class="pa-next" :title="entryTitle(nextLevel)">
          上方 {{ fmt(nextLevel.price) }}
          <em>需涨 {{ fmt(nextDiff) }} / {{ pct(nextDiff) }}%</em>
        </span>
        <span v-else class="pa-none">上方无水位</span>
        <span v-if="prevLevel" class="pa-prev" :title="entryTitle(prevLevel)">
          下方 {{ fmt(prevLevel.price) }}
          <em>需跌 {{ fmt(prevDiff) }} / {{ pct(prevDiff) }}%</em>
        </span>
        <span v-else class="pa-none">下方无水位</span>
      </div>
      <div class="pa-actions">
        <button
          type="button"
          :class="['pa-tool-btn', { active: measureMode }]"
          :aria-pressed="measureMode"
          @click="toggleMeasure"
        >↕ 测幅</button>
        <button type="button" class="pa-tool-btn" @click="resetView">复位</button>
      </div>
    </div>

    <div v-if="measureMode" class="pa-measure-readout">
      <template v-if="measurement">
        <strong>{{ fmt(measurement.from) }} → {{ fmt(measurement.to) }}</strong>
        <span :class="measurement.delta >= 0 ? 'rise' : 'fall'">
          {{ measurement.delta >= 0 ? '需涨' : '需跌' }}
          {{ fmt(Math.abs(measurement.delta)) }}（{{ Math.abs(measurement.percent).toFixed(2) }}%）
        </span>
        <button type="button" @click="clearMeasurement">清除</button>
      </template>
      <template v-else-if="measureFrom != null">
        已选起点 {{ fmt(measureFrom) }}，再点一个水位或轴上位置
        <button type="button" @click="clearMeasurement">清除</button>
      </template>
      <template v-else>依次点选两个水位或轴上任意位置，计算涨跌幅</template>
    </div>

    <div
      ref="axisEl"
      :class="['pa-axis', { 'is-dragging': dragging, 'is-measuring': measureMode }]"
      :style="{ height: height + 'px' }"
      title="上下拖动浏览价格，滚轮缩放；双击恢复全部水位"
      @pointerdown="startPan"
      @pointermove="movePan"
      @pointerup="endPan"
      @pointercancel="cancelPan"
      @wheel.prevent="zoomView"
      @dblclick="resetView"
    >
      <div class="pa-axis-caption">价格</div>

      <div
        v-for="tick in ticks"
        :key="tick.key"
        class="pa-tick"
        :style="{ top: tick.y + 'px' }"
      >
        <span class="pa-tick-label">{{ tick.label }}</span>
        <span class="pa-tick-notch"></span>
        <span class="pa-grid-line"></span>
      </div>
      <div class="pa-rail"></div>

      <div
        v-if="measureBand"
        class="pa-measure-band"
        :style="{ top: measureBand.top + 'px', height: measureBand.height + 'px' }"
      ></div>
      <div
        v-if="measureFrom != null"
        class="pa-measure-guide start"
        :style="{ top: priceToY(measureFrom) + 'px' }"
      ><span>A {{ fmt(measureFrom) }}</span></div>
      <div
        v-if="measureTo != null"
        class="pa-measure-guide end"
        :style="{ top: priceToY(measureTo) + 'px' }"
      ><span>B {{ fmt(measureTo) }}</span></div>

      <div v-if="validCurrentPrice" class="pa-current" :style="{ top: currentY + 'px' }">
        <span class="pa-cur-line"></span>
        <span class="pa-cur-tag">现价 {{ fmt(currentPrice) }}</span>
      </div>

      <svg class="pa-leaders" aria-hidden="true">
        <g v-for="entry in laidOut" :key="'leader-' + entry.key">
          <line x1="70" :y1="entry.anchorY" x2="91" :y2="entry.labelY" :class="['pa-leader', badgeClass(entry)]" />
          <circle cx="70" :cy="entry.anchorY" r="4" :class="['pa-anchor', badgeClass(entry), { selected: isMeasured(entry.price) }]" />
        </g>
      </svg>

      <button
        v-for="entry in laidOut"
        :key="entry.key"
        type="button"
        :class="['pa-entry', { selected: isMeasured(entry.price) }]"
        :style="{ top: entry.labelY + 'px' }"
        :title="entryTitle(entry)"
        @pointerdown.stop
        @click.stop="pickMeasurement(entry.price)"
      >
        <span class="pa-entry-main">
          <strong>{{ fmt(entry.price) }}</strong>
          <span class="pa-name">{{ entry.name }}</span>
          <i :class="['pa-badge', badgeClass(entry)]">{{ badgeText(entry) }}</i>
        </span>
        <span class="pa-entry-meta">
          <span>{{ entry.timeText }}</span>
          <span v-if="entry.qty">数量 {{ entry.qty }}</span>
          <span v-if="entry.note" class="pa-note">{{ entry.note }}</span>
        </span>
      </button>

      <div class="pa-drag-hint">拖动平移 · 滚轮缩放</div>
    </div>

    <div class="pa-legend">
      <span><i class="pa-badge pa-b-mark-manual">手工</i> 分析</span>
      <span><i class="pa-badge pa-b-mark-agent">AI</i> 分析</span>
      <span><i class="pa-badge pa-b-ladder-buy">买</i> / <i class="pa-badge pa-b-ladder-sell">卖</i> 计划</span>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  marks: { type: Array, default: () => [] },
  levels: { type: Array, default: () => [] },
  currentPrice: { type: Number, default: null },
  height: { type: Number, default: 380 }
})

const PAD = 22
const LABEL_HALF = 21.5
const LABEL_GAP = 3
const axisEl = ref(null)
const viewMin = ref(0)
const viewMax = ref(1)
const dragging = ref(false)
const dragStartY = ref(0)
const dragStartMin = ref(0)
const dragStartMax = ref(1)
const dragDistance = ref(0)
const pointerId = ref(null)
const measureMode = ref(false)
const measureFrom = ref(null)
const measureTo = ref(null)
let panFrame = 0
let pendingPointerY = 0

const validCurrentPrice = computed(() => {
  const value = Number(props.currentPrice)
  return Number.isFinite(value) && value > 0 ? value : null
})

const entries = computed(() => {
  const out = []
  for (const mark of props.marks || []) {
    if (mark.state && mark.state !== 'active') continue
    if (isExpired(mark.valid_until)) continue
    const price = Number(mark.price)
    if (!Number.isFinite(price) || price <= 0) continue
    const name = mark.label || mark.type || '分析水位'
    out.push({
      key: 'mark-' + (mark.id || name + price), price, name,
      kind: 'mark', source: mark.source === 'agent' ? 'agent' : 'manual',
      note: mark.note || '', qty: null, timeText: formatEntryTime(mark)
    })
  }
  for (const level of props.levels || []) {
    if (level.enabled === false) continue
    if (level.lifecycle_state && level.lifecycle_state !== 'active') continue
    if (isExpired(level.valid_until)) continue
    const price = Number(level.price)
    if (!Number.isFinite(price) || price <= 0) continue
    const defaultName = level.side === 'buy' ? '买入计划' : '卖出计划'
    out.push({
      key: 'level-' + (level.id || level.side + price), price,
      name: level.note || defaultName, kind: 'ladder', side: level.side,
      source: level.source || 'manual', note: '',
      qty: level.qty || null, timeText: formatEntryTime(level)
    })
  }
  return out.sort((a, b) => b.price - a.price)
})

const hasData = computed(() => entries.value.length > 0 || validCurrentPrice.value)
const dataExtent = computed(() => {
  const prices = entries.value.map(entry => entry.price)
  if (validCurrentPrice.value) prices.push(validCurrentPrice.value)
  if (!prices.length) return { min: 0, max: 1 }
  return { min: Math.min(...prices), max: Math.max(...prices) }
})
const viewSpan = computed(() => Math.max(viewMax.value - viewMin.value, 0.0001))
const usableHeight = computed(() => Math.max(props.height - PAD * 2, 1))

watch(() => [dataExtent.value.min, dataExtent.value.max], resetView, { immediate: true })

function resetView() {
  const { min, max } = dataExtent.value
  let span = max - min
  if (span <= 0) span = Math.max(max * 0.2, 1)
  const padding = span * 0.14
  viewMin.value = Math.max(0, min - padding)
  viewMax.value = max + padding
  if (viewMax.value <= viewMin.value) viewMax.value = viewMin.value + 1
}

function priceToY(price) {
  return PAD + ((viewMax.value - Number(price)) / viewSpan.value) * usableHeight.value
}

function yToPrice(y) {
  const ratio = (Math.min(props.height - PAD, Math.max(PAD, y)) - PAD) / usableHeight.value
  return viewMax.value - ratio * viewSpan.value
}

const ticks = computed(() => {
  const targetCount = Math.max(2, Math.floor(usableHeight.value / 54))
  const step = niceStep(viewSpan.value / targetCount)
  const first = Math.ceil(viewMin.value / step) * step
  const result = []
  for (let price = first; price <= viewMax.value + step * 0.001; price += step) {
    const normalized = Number(price.toFixed(10))
    result.push({ key: normalized, y: priceToY(normalized), label: formatTick(normalized, step) })
  }
  return result
})

const laidOut = computed(() => {
  const visible = entries.value
    .map(entry => ({ ...entry, anchorY: priceToY(entry.price), labelY: priceToY(entry.price) }))
    .filter(entry => entry.anchorY >= PAD - 6 && entry.anchorY <= props.height - PAD + 6)
    .sort((a, b) => a.anchorY - b.anchorY)
  const minCenter = LABEL_HALF + 3
  const maxCenter = props.height - LABEL_HALF - 3
  const rowHeight = LABEL_HALF * 2 + LABEL_GAP
  for (let index = 0; index < visible.length; index += 1) {
    const previous = index > 0 ? visible[index - 1].labelY + rowHeight : minCenter
    visible[index].labelY = Math.max(visible[index].anchorY, previous)
  }
  if (visible.length && visible[visible.length - 1].labelY > maxCenter) {
    visible[visible.length - 1].labelY = maxCenter
    for (let index = visible.length - 2; index >= 0; index -= 1) {
      visible[index].labelY = Math.min(visible[index].labelY, visible[index + 1].labelY - rowHeight)
    }
  }
  return visible
})

const currentY = computed(() => validCurrentPrice.value ? priceToY(validCurrentPrice.value) : 0)
const nextLevel = computed(() => {
  if (!validCurrentPrice.value) return null
  return [...entries.value].filter(entry => entry.price > validCurrentPrice.value)
    .sort((a, b) => a.price - b.price)[0] || null
})
const prevLevel = computed(() => {
  if (!validCurrentPrice.value) return null
  return [...entries.value].filter(entry => entry.price < validCurrentPrice.value)
    .sort((a, b) => b.price - a.price)[0] || null
})
const nextDiff = computed(() => nextLevel.value ? nextLevel.value.price - validCurrentPrice.value : 0)
const prevDiff = computed(() => prevLevel.value ? validCurrentPrice.value - prevLevel.value.price : 0)

const measurement = computed(() => {
  if (measureFrom.value == null || measureTo.value == null || measureFrom.value === 0) return null
  const delta = measureTo.value - measureFrom.value
  return { from: measureFrom.value, to: measureTo.value, delta, percent: delta / measureFrom.value * 100 }
})
const measureBand = computed(() => {
  if (!measurement.value) return null
  const firstY = priceToY(measurement.value.from)
  const secondY = priceToY(measurement.value.to)
  return { top: Math.min(firstY, secondY), height: Math.abs(firstY - secondY) }
})

function startPan(event) {
  if (event.button !== 0) return
  pointerId.value = event.pointerId
  dragStartY.value = event.clientY
  pendingPointerY = event.clientY
  dragStartMin.value = viewMin.value
  dragStartMax.value = viewMax.value
  dragDistance.value = 0
  dragging.value = true
  event.currentTarget.setPointerCapture(event.pointerId)
}

function movePan(event) {
  if (!dragging.value || event.pointerId !== pointerId.value) return
  pendingPointerY = event.clientY
  dragDistance.value = Math.max(dragDistance.value, Math.abs(event.clientY - dragStartY.value))
  if (panFrame) return
  panFrame = requestAnimationFrame(() => {
    panFrame = 0
    const deltaPixels = pendingPointerY - dragStartY.value
    const deltaPrice = deltaPixels / usableHeight.value * (dragStartMax.value - dragStartMin.value)
    let nextMin = dragStartMin.value + deltaPrice
    let nextMax = dragStartMax.value + deltaPrice
    if (nextMin < 0) {
      nextMax -= nextMin
      nextMin = 0
    }
    viewMin.value = nextMin
    viewMax.value = nextMax
  })
}

function endPan(event) {
  if (!dragging.value || event.pointerId !== pointerId.value) return
  if (dragDistance.value < 5 && measureMode.value) {
    const rect = axisEl.value?.getBoundingClientRect()
    if (rect) pickMeasurement(yToPrice(event.clientY - rect.top))
  }
  cancelPan(event)
}

function cancelPan(event) {
  if (axisEl.value?.hasPointerCapture(event.pointerId)) axisEl.value.releasePointerCapture(event.pointerId)
  dragging.value = false
  pointerId.value = null
}

function zoomView(event) {
  const rect = axisEl.value?.getBoundingClientRect()
  if (!rect) return
  const anchor = yToPrice(event.clientY - rect.top)
  const factor = event.deltaY > 0 ? 1.16 : 0.86
  let nextMin = anchor - (anchor - viewMin.value) * factor
  let nextMax = anchor + (viewMax.value - anchor) * factor
  const minimumSpan = Math.max(dataExtent.value.max * 0.002, 0.01)
  if (nextMax - nextMin < minimumSpan) return
  if (nextMin < 0) {
    nextMax -= nextMin
    nextMin = 0
  }
  viewMin.value = nextMin
  viewMax.value = nextMax
}

function toggleMeasure() {
  measureMode.value = !measureMode.value
  if (!measureMode.value) clearMeasurement()
}
function pickMeasurement(price) {
  if (!measureMode.value) return
  const normalized = Number(Number(price).toFixed(4))
  if (measureFrom.value == null || measureTo.value != null) {
    measureFrom.value = normalized
    measureTo.value = null
  } else {
    measureTo.value = normalized
  }
}
function clearMeasurement() {
  measureFrom.value = null
  measureTo.value = null
}
function isMeasured(price) {
  return price === measureFrom.value || price === measureTo.value
}

function niceStep(rawStep) {
  if (!Number.isFinite(rawStep) || rawStep <= 0) return 1
  const power = 10 ** Math.floor(Math.log10(rawStep))
  const fraction = rawStep / power
  let niceFraction = 10
  if (fraction <= 1) niceFraction = 1
  else if (fraction <= 2) niceFraction = 2
  else if (fraction <= 2.5) niceFraction = 2.5
  else if (fraction <= 5) niceFraction = 5
  return niceFraction * power
}
function formatTick(value, step) {
  const decimals = step >= 1 ? 2 : Math.min(4, Math.max(2, Math.ceil(-Math.log10(step)) + 1))
  return Number(value).toFixed(decimals)
}
function isExpired(value) {
  if (!value) return false
  const expiry = new Date(value.length === 10 ? `${value}T23:59:59` : value)
  return !Number.isNaN(expiry.getTime()) && expiry.getTime() < Date.now()
}
function shortDate(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: value.length > 10 ? '2-digit' : undefined,
    minute: value.length > 10 ? '2-digit' : undefined,
    hour12: false
  }).format(date)
}
function formatEntryTime(entry) {
  if (entry.valid_from && entry.valid_until) return `${shortDate(entry.valid_from)} 至 ${shortDate(entry.valid_until)}`
  if (entry.valid_until) return `有效至 ${shortDate(entry.valid_until)}`
  if (entry.valid_from) return `生效于 ${shortDate(entry.valid_from)}`
  const created = entry.created_at || entry.updated_at
  return created ? `创建于 ${shortDate(created)}` : '未记录时间'
}
function fmt(value) { return value == null ? '--' : Number(value).toFixed(2) }
function pct(value) { return validCurrentPrice.value ? (value / validCurrentPrice.value * 100).toFixed(2) : '--' }
function badgeClass(entry) {
  if (entry.kind === 'ladder') return entry.side === 'buy' ? 'pa-b-ladder-buy' : 'pa-b-ladder-sell'
  return entry.source === 'agent' ? 'pa-b-mark-agent' : 'pa-b-mark-manual'
}
function badgeText(entry) {
  if (entry.kind === 'ladder') {
    const side = entry.side === 'buy' ? '买' : '卖'
    if (entry.source === 'strategy') return `${side}·网格`
    if (entry.source === 'agent') return `${side}·AI`
    return side
  }
  return entry.source === 'agent' ? 'AI' : '手工'
}
function entryTitle(entry) {
  const type = entry.kind === 'ladder' ? '计划水位' : '分析水位'
  const details = [type, entry.name, `价格 ${fmt(entry.price)}`, entry.timeText]
  if (entry.note) details.push(entry.note)
  return details.join(' · ')
}

onBeforeUnmount(() => {
  if (panFrame) cancelAnimationFrame(panFrame)
})
</script>

<style scoped>
.price-axis-wrap { margin-bottom: 12px; }
.pa-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: 8px; }
.pa-summary { display: flex; gap: 8px 16px; flex-wrap: wrap; min-width: 0; font-size: 12px; }
.pa-summary span { display: inline-flex; align-items: center; gap: 5px; }
.pa-summary em { font-style: normal; color: #64748b; }
.pa-next { color: #b91c1c; }
.pa-prev { color: #15803d; }
.pa-none { color: #94a3b8; }
.pa-actions { display: flex; gap: 6px; flex: none; }
.pa-tool-btn { border: 1px solid #cbd5e1; border-radius: 6px; background: #fff; color: #475569; padding: 4px 8px; font-size: 11px; cursor: pointer; }
.pa-tool-btn:hover { border-color: #94a3b8; background: #f8fafc; }
.pa-tool-btn.active { border-color: #2563eb; background: #eff6ff; color: #1d4ed8; }
.pa-measure-readout { display: flex; align-items: center; gap: 10px; min-height: 30px; margin-bottom: 7px; padding: 5px 9px; border: 1px solid #bfdbfe; border-radius: 7px; background: #eff6ff; color: #475569; font-size: 12px; }
.pa-measure-readout strong { color: #0f172a; }
.pa-measure-readout .rise { color: #dc2626; font-weight: 600; }
.pa-measure-readout .fall { color: #16a34a; font-weight: 600; }
.pa-measure-readout button { margin-left: auto; border: 0; background: transparent; color: #2563eb; cursor: pointer; }

.pa-axis { position: relative; overflow: hidden; border: 1px solid #dbe3ee; border-radius: 10px; background: linear-gradient(90deg, #f8fafc 0 76px, #fff 76px); cursor: grab; user-select: none; touch-action: none; }
.pa-axis.is-dragging { cursor: grabbing; }
.pa-axis.is-measuring:not(.is-dragging) { cursor: crosshair; }
.pa-axis-caption { position: absolute; z-index: 5; top: 5px; left: 10px; color: #94a3b8; font-size: 10px; font-weight: 600; letter-spacing: .08em; }
.pa-rail { position: absolute; z-index: 2; left: 69px; top: 0; bottom: 0; width: 2px; background: #94a3b8; }
.pa-tick { position: absolute; z-index: 1; left: 0; right: 0; height: 1px; pointer-events: none; }
.pa-tick-label { position: absolute; right: calc(100% - 59px); width: 55px; transform: translateY(-50%); color: #64748b; font-size: 10px; font-variant-numeric: tabular-nums; text-align: right; }
.pa-tick-notch { position: absolute; left: 64px; width: 7px; border-top: 1px solid #64748b; }
.pa-grid-line { position: absolute; left: 71px; right: 0; border-top: 1px solid #edf2f7; }

.pa-leaders { position: absolute; z-index: 4; inset: 0; width: 100%; height: 100%; overflow: visible; pointer-events: none; }
.pa-leader { stroke-width: 1.25; opacity: .65; transition: y1 .1s ease-out, y2 .1s ease-out; }
.pa-anchor { stroke: #fff; stroke-width: 1.5; transition: cy .1s ease-out; }
.pa-anchor.selected { stroke: #0f172a; stroke-width: 2; }
.pa-leader.pa-b-ladder-buy, .pa-anchor.pa-b-ladder-buy { stroke: #16a34a; fill: #16a34a; }
.pa-leader.pa-b-ladder-sell, .pa-anchor.pa-b-ladder-sell { stroke: #dc2626; fill: #dc2626; }
.pa-leader.pa-b-mark-manual, .pa-anchor.pa-b-mark-manual { stroke: #2563eb; fill: #2563eb; }
.pa-leader.pa-b-mark-agent, .pa-anchor.pa-b-mark-agent { stroke: #7c3aed; fill: #7c3aed; }

.pa-entry { position: absolute; z-index: 6; left: 90px; right: 8px; min-width: 0; height: 43px; transform: translateY(-50%); display: flex; flex-direction: column; justify-content: center; gap: 2px; overflow: hidden; border: 1px solid #e2e8f0; border-radius: 7px; background: rgba(255, 255, 255, .94); padding: 4px 8px; text-align: left; box-shadow: 0 1px 2px rgba(15, 23, 42, .05); transition: top .1s ease-out, border-color .15s, box-shadow .15s; }
.pa-entry:hover { z-index: 8; border-color: #94a3b8; box-shadow: 0 3px 10px rgba(15, 23, 42, .12); }
.pa-entry.selected { border-color: #2563eb; box-shadow: 0 0 0 2px rgba(37, 99, 235, .14); }
.pa-entry-main, .pa-entry-meta { display: flex; align-items: center; gap: 6px; min-width: 0; }
.pa-entry-main strong { flex: none; color: #0f172a; font-size: 12px; font-variant-numeric: tabular-nums; }
.pa-name { overflow: hidden; color: #334155; font-size: 12px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.pa-entry-meta { color: #94a3b8; font-size: 10px; }
.pa-entry-meta > span { flex: none; }
.pa-entry-meta .pa-note { overflow: hidden; flex: 1; color: #64748b; text-overflow: ellipsis; white-space: nowrap; }
.is-dragging .pa-entry, .is-dragging .pa-leader, .is-dragging .pa-anchor { transition: none; }

.pa-badge { flex: none; border-radius: 8px; padding: 0 5px; font-size: 10px; font-style: normal; line-height: 16px; }
.pa-b-ladder-buy { background: #dcfce7; color: #15803d; }
.pa-b-ladder-sell { background: #fee2e2; color: #b91c1c; }
.pa-b-mark-manual { background: #dbeafe; color: #1d4ed8; }
.pa-b-mark-agent { background: #ede9fe; color: #6d28d9; }
.pa-current { position: absolute; z-index: 5; left: 70px; right: 0; display: flex; align-items: center; pointer-events: none; transition: top .1s ease-out; }
.pa-cur-line { flex: 1; border-top: 2px dashed #f59e0b; }
.pa-cur-tag { position: absolute; right: 7px; transform: translateY(-50%); border-radius: 9px; background: #f59e0b; padding: 2px 8px; color: #fff; font-size: 11px; font-weight: 700; }
.is-dragging .pa-current { transition: none; }
.pa-measure-band { position: absolute; z-index: 3; left: 70px; right: 0; min-height: 1px; border-top: 1px solid rgba(37, 99, 235, .65); border-bottom: 1px solid rgba(37, 99, 235, .65); background: rgba(59, 130, 246, .08); pointer-events: none; }
.pa-measure-guide { position: absolute; z-index: 7; left: 62px; right: 0; border-top: 1px dashed #2563eb; pointer-events: none; }
.pa-measure-guide span { position: absolute; left: 13px; transform: translateY(-110%); border-radius: 4px; background: #2563eb; padding: 1px 4px; color: #fff; font-size: 9px; }
.pa-measure-guide.end { border-color: #7c3aed; }
.pa-measure-guide.end span { background: #7c3aed; }
.pa-drag-hint { position: absolute; z-index: 4; right: 8px; bottom: 5px; color: #cbd5e1; font-size: 9px; pointer-events: none; }
.pa-legend { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 7px; color: #64748b; font-size: 11px; }

@media (max-width: 640px) {
  .pa-toolbar { align-items: stretch; flex-direction: column; }
  .pa-actions { align-self: flex-end; }
  .pa-measure-readout { align-items: flex-start; flex-wrap: wrap; }
  .pa-entry { left: 82px; right: 5px; padding-inline: 6px; }
  .pa-entry-meta .pa-note { display: none; }
}
</style>
