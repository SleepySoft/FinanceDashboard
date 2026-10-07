<template>
  <div class="card reminder-card">
    <div class="reminder-head">
      <div>
        <h3>⏰ 提醒</h3>
        <p>{{ activeCount }} 条进行中<span v-if="proposedCount"> · {{ proposedCount }} 条待确认</span></p>
      </div>
      <button class="ghost" type="button" @click="expanded = !expanded">{{ expanded ? '收起' : '管理' }}</button>
    </div>

    <div v-if="expanded" class="reminder-body">
      <form v-if="!readonly" class="reminder-form" @submit.prevent="createReminder">
        <input v-model="draftTime" type="datetime-local" required />
        <input v-model="draftAction" type="text" maxlength="500" placeholder="到时需要做什么？" required />
        <button class="primary" type="submit" :disabled="saving">添加</button>
      </form>
      <p v-if="error" class="reminder-error">{{ error }}</p>

      <div v-if="visibleItems.length" class="reminder-list">
        <div v-for="item in visibleItems" :key="item.id" :class="['reminder-item', item.display_state]">
          <div class="reminder-time">
            <strong>{{ formatDate(item.remind_at) }}</strong>
            <span :class="['state-pill', item.display_state]">{{ stateText(item) }}</span>
          </div>
          <div class="reminder-action">{{ item.action }}</div>
          <div class="reminder-meta">
            <span>{{ item.source === 'agent' ? 'AI 建议' : '手工创建' }}</span>
            <router-link
              v-if="item.origin?.report_ids?.[0]"
              :to="{ path: `/stock/${code}`, query: { open: `report-${item.origin.report_ids[0]}` } }"
            >查看来源报告</router-link>
          </div>
          <div v-if="!readonly" class="reminder-actions">
            <button v-if="item.state === 'proposed'" type="button" @click="accept(item)">接受</button>
            <button v-if="item.state === 'active'" type="button" @click="changeState(item, 'completed')">完成</button>
            <button v-if="item.state === 'active' || item.state === 'proposed'" type="button" @click="startEdit(item)">改期/编辑</button>
            <button v-if="item.state === 'active' || item.state === 'proposed'" type="button" @click="changeState(item, 'cancelled')">取消</button>
            <button class="danger-text" type="button" @click="remove(item)">删除</button>
          </div>
          <form v-if="editingId === item.id" class="reminder-edit" @submit.prevent="saveEdit(item)">
            <input v-model="editTime" type="datetime-local" required />
            <input v-model="editAction" maxlength="500" required />
            <button class="primary" type="submit">保存</button>
            <button type="button" @click="editingId = ''">关闭</button>
          </form>
        </div>
      </div>
      <div v-else class="reminder-empty">暂无提醒</div>
      <button v-if="hasHistory" class="history-toggle" type="button" @click="showHistory = !showHistory">
        {{ showHistory ? '隐藏历史' : '显示已完成/已取消' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import api from '../api.js'

const props = defineProps({
  code: { type: String, required: true },
  readonly: { type: Boolean, default: false }
})

const items = ref([])
const expanded = ref(false)
const showHistory = ref(false)
const saving = ref(false)
const error = ref('')
const draftAction = ref('')
const draftTime = ref(defaultLocalTime())
const editingId = ref('')
const editAction = ref('')
const editTime = ref('')

const activeCount = computed(() => items.value.filter(item => item.state === 'active').length)
const proposedCount = computed(() => items.value.filter(item => item.state === 'proposed').length)
const hasHistory = computed(() => items.value.some(item => ['completed', 'cancelled'].includes(item.state)))
const visibleItems = computed(() => items.value.filter(item => showHistory.value || !['completed', 'cancelled'].includes(item.state)))

async function load() {
  try {
    const result = await api.reminders.listStock(props.code, true)
    items.value = result.items || []
    if (proposedCount.value || items.value.some(item => ['overdue', 'due_now', 'due_today'].includes(item.display_state))) expanded.value = true
  } catch {
    items.value = []
  }
}

async function createReminder() {
  error.value = ''
  saving.value = true
  try {
    await api.reminders.create(props.code, { action: draftAction.value.trim(), remind_at: localToIso(draftTime.value) })
    draftAction.value = ''
    draftTime.value = defaultLocalTime()
    await changed()
  } catch (e) {
    error.value = e.message || '创建失败'
  } finally {
    saving.value = false
  }
}

async function accept(item) {
  error.value = ''
  try {
    await api.reminders.update(props.code, item.id, { state: 'active' })
    await changed()
  } catch (e) {
    error.value = e.message || '接受失败，请先修改提醒时间'
    startEdit(item)
  }
}

async function changeState(item, state) {
  try {
    await api.reminders.update(props.code, item.id, { state })
    await changed()
  } catch (e) {
    error.value = e.message || '更新失败'
  }
}

function startEdit(item) {
  editingId.value = item.id
  editAction.value = item.action
  editTime.value = isoToLocal(item.remind_at)
}

async function saveEdit(item) {
  try {
    const patch = { action: editAction.value.trim(), remind_at: localToIso(editTime.value) }
    if (item.state === 'proposed') patch.state = 'active'
    await api.reminders.update(props.code, item.id, patch)
    editingId.value = ''
    await changed()
  } catch (e) {
    error.value = e.message || '保存失败'
  }
}

async function remove(item) {
  if (!window.confirm('永久删除这条提醒？')) return
  try {
    await api.reminders.delete(props.code, item.id)
    await changed()
  } catch (e) {
    error.value = e.message || '删除失败'
  }
}

async function changed() {
  await load()
  window.dispatchEvent(new CustomEvent('fd:reminders-changed'))
}

function defaultLocalTime() {
  const date = new Date(Date.now() + 24 * 3600000)
  date.setMinutes(0, 0, 0)
  return isoToLocal(date.toISOString())
}
function isoToLocal(value) {
  const date = new Date(value)
  const offset = date.getTimezoneOffset() * 60000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}
function localToIso(value) { return new Date(value).toISOString() }
function formatDate(value) { return new Date(value).toLocaleString('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }) }
function stateText(item) {
  return { proposed: '待确认', overdue: '已逾期', due_now: '已到期', due_today: '今日', upcoming: '未来', completed: '已完成', cancelled: '已取消' }[item.display_state] || item.state
}

watch(() => props.code, load)
onMounted(load)
</script>

<style scoped>
.reminder-card { padding: 16px 20px; }
.reminder-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.reminder-head h3 { margin: 0 0 3px; }
.reminder-head p { color: #94a3b8; font-size: 12px; }
.reminder-body { margin-top: 14px; }
.reminder-form, .reminder-edit { display: grid; grid-template-columns: 190px minmax(0, 1fr) auto; gap: 8px; margin-bottom: 12px; }
.reminder-list { display: flex; flex-direction: column; gap: 8px; }
.reminder-item { border: 1px solid #334155; border-left: 3px solid #64748b; border-radius: 8px; background: #0f172a; padding: 10px 12px; }
.reminder-item.overdue, .reminder-item.due_now { border-left-color: #ef4444; }
.reminder-item.due_today { border-left-color: #f59e0b; }
.reminder-item.proposed { border-left-color: #a78bfa; }
.reminder-time { display: flex; align-items: center; gap: 8px; color: #cbd5e1; font-size: 12px; }
.state-pill { border-radius: 999px; background: #334155; padding: 1px 7px; color: #cbd5e1; font-size: 10px; }
.state-pill.overdue, .state-pill.due_now { background: #7f1d1d; color: #fecaca; }
.state-pill.proposed { background: #4c1d95; color: #ddd6fe; }
.reminder-action { margin-top: 7px; color: #f1f5f9; font-size: 14px; line-height: 1.55; }
.reminder-meta { display: flex; gap: 10px; margin-top: 5px; color: #64748b; font-size: 11px; }
.reminder-meta a { color: #60a5fa; }
.reminder-actions { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.reminder-actions button, .history-toggle, .reminder-edit button { padding: 4px 9px; background: #1e293b; color: #cbd5e1; }
.reminder-actions .danger-text { color: #f87171; }
.reminder-edit { margin: 9px 0 0; }
.reminder-error { margin-bottom: 8px; color: #f87171; font-size: 12px; }
.reminder-empty { padding: 18px; color: #64748b; text-align: center; }
.history-toggle { margin-top: 10px; }
@media (max-width: 640px) {
  .reminder-form, .reminder-edit { grid-template-columns: 1fr; }
}
</style>
