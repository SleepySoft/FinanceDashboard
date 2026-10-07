<template>
  <div class="reminders-page">
    <header class="page-head">
      <div><h2>提醒</h2><p>跨股票查看未来复核事项与历史记录</p></div>
      <div class="view-switch">
        <button :class="{ active: view === 'timeline' }" @click="view = 'timeline'">时间轴</button>
        <button :class="{ active: view === 'list' }" @click="view = 'list'">列表</button>
      </div>
    </header>

    <div class="summary-grid">
      <button v-for="item in scopes" :key="item.key" :class="['summary-card', { active: scope === item.key }]" @click="scope = item.key">
        <strong>{{ item.count }}</strong><span>{{ item.label }}</span>
      </button>
    </div>

    <div v-if="loading" class="card empty">加载中…</div>
    <div v-else-if="!items.length" class="card empty">当前筛选下没有提醒</div>

    <div v-else-if="view === 'timeline'" class="timeline">
      <section v-for="group in groups" :key="group.key" class="day-group">
        <div class="day-label"><strong>{{ group.label }}</strong><span>{{ group.items.length }} 条</span></div>
        <div class="day-items">
          <ReminderRow v-for="item in group.items" :key="item.id" :item="item" :can-write="canWrite" @changed="load" />
        </div>
      </section>
    </div>
    <div v-else class="reminder-grid">
      <ReminderRow v-for="item in items" :key="item.id" :item="item" :can-write="canWrite" @changed="load" />
    </div>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import api from '../api.js'
import auth from '../composables/useAuth.js'

const scope = ref('all')
const view = ref('timeline')
const items = ref([])
const counts = ref({ due: 0, proposed: 0, upcoming: 0, history: 0 })
const loading = ref(false)
const canWrite = auth.canWrite
let refreshTimer = null

const scopes = computed(() => [
  { key: 'all', label: '全部', count: Object.values(counts.value).reduce((sum, value) => sum + value, 0) },
  { key: 'due', label: '到期/逾期', count: counts.value.due || 0 },
  { key: 'upcoming', label: '未来', count: counts.value.upcoming || 0 },
  { key: 'proposed', label: '待确认', count: counts.value.proposed || 0 },
  { key: 'history', label: '历史', count: counts.value.history || 0 },
])

const groups = computed(() => {
  const map = new Map()
  const sorted = [...items.value].sort((left, right) => new Date(left.remind_at) - new Date(right.remind_at))
  for (const item of sorted) {
    const date = new Date(item.remind_at)
    const key = Number.isNaN(date.getTime()) ? 'unknown' : date.toLocaleDateString('sv-SE')
    if (!map.has(key)) map.set(key, [])
    map.get(key).push(item)
  }
  return [...map.entries()].map(([key, groupItems]) => ({
    key,
    label: key === 'unknown' ? '时间未知' : new Date(`${key}T00:00:00`).toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'short' }),
    items: groupItems,
  }))
})

async function load() {
  loading.value = true
  try {
    const result = await api.reminders.list(scope.value)
    items.value = result.items || []
    counts.value = result.counts || counts.value
    window.dispatchEvent(new CustomEvent('fd:reminders-changed'))
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

const ReminderRow = defineComponent({
  props: { item: { type: Object, required: true }, canWrite: Boolean },
  emits: ['changed'],
  setup(props, { emit }) {
    const stateLabels = { proposed: '待确认', overdue: '已逾期', due_now: '已到期', due_today: '今日', upcoming: '未来', completed: '已完成', cancelled: '已取消' }
    async function update(state) {
      try {
        await api.reminders.update(props.item.code, props.item.id, { state })
        emit('changed')
      } catch {
        // API toast explains why, for example an expired proposal needs rescheduling.
      }
    }
    return () => h('article', { class: ['global-reminder', props.item.display_state] }, [
      h('div', { class: 'timeline-dot' }),
      h('div', { class: 'row-head' }, [
        h(RouterLink, { to: `/stock/${props.item.code}`, class: 'stock-link' }, () => `${props.item.stock_name} · ${props.item.code}`),
        h('span', { class: ['row-state', props.item.display_state] }, stateLabels[props.item.display_state] || props.item.state),
      ]),
      h('time', new Date(props.item.remind_at).toLocaleString('zh-CN', { dateStyle: 'medium', timeStyle: 'short' })),
      h('p', props.item.action),
      h('div', { class: 'row-foot' }, [
        h('span', props.item.source === 'agent' ? 'AI 建议' : `由 ${props.item.created_by} 创建`),
        props.canWrite && ['active'].includes(props.item.state) ? h('button', { onClick: () => update('completed') }, '完成') : null,
        props.canWrite && props.item.state === 'proposed' ? h('button', { onClick: () => update('active') }, '接受') : null,
        props.canWrite && ['active', 'proposed'].includes(props.item.state) ? h('button', { onClick: () => update('cancelled') }, '取消') : null,
      ])
    ])
  }
})

watch(scope, load)
onMounted(() => {
  load()
  refreshTimer = window.setInterval(load, 30000)
})
onBeforeUnmount(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
})
</script>

<style scoped>
.reminders-page { max-width: 940px; margin: 0 auto; padding: 16px 0; }
.page-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 16px; }
.page-head h2 { margin-bottom: 4px; font-size: 22px; }
.page-head p { color: #64748b; font-size: 12px; }
.view-switch { display: flex; gap: 4px; padding: 3px; border-radius: 8px; background: #0f172a; }
.view-switch button { background: transparent; color: #94a3b8; padding: 6px 11px; }
.view-switch button.active { background: #334155; color: #fff; }
.summary-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-bottom: 18px; }
.summary-card { display: flex; flex-direction: column; gap: 2px; border: 1px solid #334155; background: #151e2e; color: #94a3b8; }
.summary-card strong { color: #e2e8f0; font-size: 20px; }
.summary-card.active { border-color: #3b82f6; background: #172554; }
.timeline { position: relative; }
.day-group { display: grid; grid-template-columns: 150px minmax(0, 1fr); gap: 22px; }
.day-label { position: sticky; top: 12px; align-self: start; display: flex; flex-direction: column; color: #cbd5e1; font-size: 13px; }
.day-label span { margin-top: 3px; color: #64748b; font-size: 11px; }
.day-items { position: relative; padding: 0 0 18px 22px; border-left: 2px solid #334155; }
.reminder-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.reminder-grid :deep(.timeline-dot) { display: none; }
.empty { padding: 40px; color: #64748b; text-align: center; }
:deep(.global-reminder) { position: relative; margin-bottom: 10px; border: 1px solid #334155; border-radius: 9px; background: #151e2e; padding: 12px 14px; }
:deep(.global-reminder .timeline-dot) { position: absolute; top: 19px; left: -29px; width: 12px; height: 12px; border: 2px solid #0b1120; border-radius: 50%; background: #64748b; }
:deep(.global-reminder.overdue .timeline-dot), :deep(.global-reminder.due_now .timeline-dot) { background: #ef4444; }
:deep(.global-reminder.proposed .timeline-dot) { background: #a78bfa; }
:deep(.row-head) { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
:deep(.stock-link) { color: #60a5fa; font-size: 12px; text-decoration: none; }
:deep(.row-state) { border-radius: 999px; background: #334155; padding: 2px 7px; color: #cbd5e1; font-size: 10px; }
:deep(.row-state.overdue), :deep(.row-state.due_now) { background: #7f1d1d; color: #fecaca; }
:deep(.row-state.proposed) { background: #4c1d95; color: #ddd6fe; }
:deep(.global-reminder time) { display: block; margin-top: 8px; color: #94a3b8; font-size: 12px; }
:deep(.global-reminder p) { margin-top: 5px; color: #f1f5f9; line-height: 1.55; }
:deep(.row-foot) { display: flex; align-items: center; gap: 7px; margin-top: 9px; color: #64748b; font-size: 11px; }
:deep(.row-foot button) { margin-left: auto; background: #1e293b; color: #cbd5e1; padding: 4px 8px; }
:deep(.row-foot button + button) { margin-left: 0; }
@media (max-width: 700px) {
  .summary-grid { grid-template-columns: repeat(2, 1fr); }
  .day-group { grid-template-columns: 1fr; gap: 7px; }
  .day-label { position: static; }
  .day-items { margin-left: 6px; }
  .reminder-grid { grid-template-columns: 1fr; }
}
</style>
