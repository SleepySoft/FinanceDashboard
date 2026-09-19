<template>
  <div class="price-axis-wrap" v-if="hasData">
    <!-- 上方/下方最近档位摘要 -->
    <div class="pa-summary">
      <span v-if="nextLevel" class="pa-next" :title="entryTitle(nextLevel)">
        ▲ 上一档 {{ fmt(nextLevel.price) }}
        <em>+{{ fmt(nextDiff) }}（+{{ pct(nextDiff) }}%）</em>
        <i :class="['pa-badge', badgeClass(nextLevel)]">{{ badgeText(nextLevel) }}</i>
      </span>
      <span v-else class="pa-none">▲ 上方无档位</span>
      <span v-if="prevLevel" class="pa-prev" :title="entryTitle(prevLevel)">
        ▼ 下一档 {{ fmt(prevLevel.price) }}
        <em>-{{ fmt(prevDiff) }}（-{{ pct(prevDiff) }}%）</em>
        <i :class="['pa-badge', badgeClass(prevLevel)]">{{ badgeText(prevLevel) }}</i>
      </span>
      <span v-else class="pa-none">▼ 下方无档位</span>
    </div>

    <!-- 水位轴主体 -->
    <div class="pa-axis" :style="{ height: height + 'px' }">
      <div class="pa-rail"></div>
      <!-- 当前价 -->
      <div v-if="currentPrice" class="pa-current" :style="{ top: currentY + 'px' }">
        <span class="pa-cur-line"></span>
        <span class="pa-cur-tag">现价 {{ fmt(currentPrice) }}</span>
      </div>
      <!-- 各档位 -->
      <div v-for="e in laidOut" :key="e.key" class="pa-entry" :style="{ top: e.y + 'px' }">
        <span :class="['pa-dot', badgeClass(e)]"></span>
        <span class="pa-price">{{ fmt(e.price) }}</span>
        <span class="pa-label" :title="entryTitle(e)">{{ e.label }}</span>
        <i :class="['pa-badge', badgeClass(e)]">{{ badgeText(e) }}</i>
      </div>
    </div>

    <!-- 图例 -->
    <div class="pa-legend">
      <span><i class="pa-badge pa-b-mark-manual">手工</i> 价格标记</span>
      <span><i class="pa-badge pa-b-mark-agent">AI</i> 技术面标记</span>
      <span><i class="pa-badge pa-b-ladder-buy">买</i> / <i class="pa-badge pa-b-ladder-sell">卖</i> 阶梯（含网格）</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

// 价格水位轴：把三类价位画在同一根纵轴上——
//   手工价格标记（mark×manual）、AI 技术面标记（mark×agent）、价格阶梯/网格（ladder）
// 并标注当前价与上/下一档的差额。设计依据见 AGENTS.md 决策 16。
const props = defineProps({
  marks: { type: Array, default: () => [] },          // price_marks（含 source 字段）
  levels: { type: Array, default: () => [] },         // ladder levels（含 side/source/qty）
  currentPrice: { type: Number, default: null },
  height: { type: Number, default: 300 }
})

const PAD = 14       // 轴上下留白 px
const MIN_GAP = 22   // 标签行最小间距 px

const entries = computed(() => {
  const out = []
  for (const m of props.marks || []) {
    const price = Number(m.price)
    if (!price || price <= 0) continue
    out.push({
      key: 'm' + (m.id || m.label + price),
      price, label: m.label || '标记',
      kind: 'mark', source: m.source === 'agent' ? 'agent' : 'manual',
      note: m.note || ''
    })
  }
  for (const lv of props.levels || []) {
    if (lv.enabled === false) continue
    const price = Number(lv.price)
    if (!price || price <= 0) continue
    out.push({
      key: 'l' + (lv.id || lv.side + price),
      price,
      label: (lv.note || (lv.side === 'buy' ? '买入' : '卖出')) + (lv.qty ? ` ×${lv.qty}` : ''),
      kind: 'ladder', side: lv.side, source: lv.source || 'manual',
      note: lv.note || ''
    })
  }
  return out.sort((a, b) => a.price - b.price)
})

const hasData = computed(() => entries.value.length > 0 || props.currentPrice)

// 价格 → y 坐标（价格高在上）
const priceRange = computed(() => {
  const ps = entries.value.map(e => e.price)
  if (props.currentPrice) ps.push(props.currentPrice)
  if (!ps.length) return { min: 0, max: 1 }
  let min = Math.min(...ps), max = Math.max(...ps)
  if (min === max) { min *= 0.95; max *= 1.05 }
  return { min, max }
})

function priceToY(p) {
  const { min, max } = priceRange.value
  const usable = props.height - PAD * 2
  return PAD + (1 - (p - min) / (max - min)) * usable
}

// 防重叠：按价格顺序强制最小纵向间距
const laidOut = computed(() => {
  const items = entries.value.map(e => ({ ...e, y: priceToY(e.price) }))
  for (let i = 1; i < items.length; i++) {
    if (items[i].y - items[i - 1].y < MIN_GAP) items[i].y = items[i - 1].y + MIN_GAP
  }
  const overflow = items.length ? items[items.length - 1].y - (props.height - PAD) : 0
  if (overflow > 0) for (const it of items) it.y -= overflow
  return items
})

const currentY = computed(() => props.currentPrice ? priceToY(props.currentPrice) : 0)

const nextLevel = computed(() =>
  props.currentPrice ? entries.value.find(e => e.price > props.currentPrice) : null)
const prevLevel = computed(() =>
  props.currentPrice ? [...entries.value].reverse().find(e => e.price < props.currentPrice) : null)
const nextDiff = computed(() => nextLevel.value ? nextLevel.value.price - props.currentPrice : 0)
const prevDiff = computed(() => prevLevel.value ? props.currentPrice - prevLevel.value.price : 0)

function fmt(v) { return v == null ? '--' : Number(v).toFixed(2) }
function pct(v) { return props.currentPrice ? (v / props.currentPrice * 100).toFixed(1) : '--' }

function badgeClass(e) {
  if (e.kind === 'ladder') return e.side === 'buy' ? 'pa-b-ladder-buy' : 'pa-b-ladder-sell'
  return e.source === 'agent' ? 'pa-b-mark-agent' : 'pa-b-mark-manual'
}
function badgeText(e) {
  if (e.kind === 'ladder') {
    const side = e.side === 'buy' ? '买' : '卖'
    return e.source === 'strategy' ? side + '·网格' : e.source === 'agent' ? side + '·AI' : side
  }
  return e.source === 'agent' ? 'AI' : '手工'
}
function entryTitle(e) {
  const parts = [e.kind === 'ladder' ? '价格阶梯' : (e.source === 'agent' ? 'AI 标记' : '手工标记')]
  if (e.note) parts.push(e.note)
  return parts.join('：')
}
</script>

<style scoped>
.price-axis-wrap { margin-bottom: 12px; }
.pa-summary { display: flex; justify-content: space-between; gap: 8px; flex-wrap: wrap; font-size: 12px; margin-bottom: 6px; }
.pa-summary em { font-style: normal; color: #64748b; margin: 0 2px; }
.pa-next { color: #b91c1c; }
.pa-prev { color: #15803d; }
.pa-none { color: #94a3b8; }

.pa-axis { position: relative; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }
.pa-rail { position: absolute; left: 10px; top: 8px; bottom: 8px; width: 2px; background: #cbd5e1; border-radius: 1px; }

.pa-entry { position: absolute; left: 18px; right: 6px; display: flex; align-items: center; gap: 6px; height: 20px; transform: translateY(-10px); font-size: 12px; white-space: nowrap; overflow: hidden; }
.pa-dot { width: 8px; height: 8px; border-radius: 50%; flex: none; margin-left: -11px; border: 1.5px solid #fff; box-shadow: 0 0 0 1px #cbd5e1; }
.pa-dot.pa-b-ladder-buy { background: #16a34a; }
.pa-dot.pa-b-ladder-sell { background: #dc2626; }
.pa-dot.pa-b-mark-manual { background: #2563eb; }
.pa-dot.pa-b-mark-agent { background: #7c3aed; }
.pa-price { font-weight: 600; color: #0f172a; flex: none; }
.pa-label { color: #475569; overflow: hidden; text-overflow: ellipsis; }

.pa-badge { font-style: normal; font-size: 10px; padding: 0 5px; border-radius: 8px; flex: none; line-height: 16px; }
.pa-b-ladder-buy { background: #dcfce7; color: #15803d; }
.pa-b-ladder-sell { background: #fee2e2; color: #b91c1c; }
.pa-b-mark-manual { background: #dbeafe; color: #1d4ed8; }
.pa-b-mark-agent { background: #ede9fe; color: #6d28d9; }

.pa-current { position: absolute; left: 8px; right: 0; transform: translateY(-9px); display: flex; align-items: center; pointer-events: none; }
.pa-cur-line { flex: 1; border-top: 2px dashed #f59e0b; }
.pa-cur-tag { position: absolute; right: 6px; background: #f59e0b; color: #fff; font-size: 11px; font-weight: 600; padding: 1px 8px; border-radius: 9px; }

.pa-legend { display: flex; gap: 14px; flex-wrap: wrap; font-size: 11px; color: #64748b; margin-top: 6px; }
</style>
