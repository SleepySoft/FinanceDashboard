<template>
  <div class="home">
    <div class="header">
      <h1>分析请求池</h1>
      <button class="primary" @click="showAdd = true">+ 提交请求</button>
    </div>

    <div v-if="showAdd" class="add-form card">
      <h3>提交分析请求</h3>
      <p class="hint">输入股票代码，我将分析后正式加入列表。可直接微信告诉我分析某只股票。</p>
      <div class="form-row">
        <input v-model="newCode" placeholder="股票代码，如 000001.SZ" />
        <input v-model="newName" placeholder="名称（可选）" />
        <input v-model="newSector" placeholder="行业（可选）" />
      </div>
      <div class="form-row">
        <select v-model="newType" style="width: auto">
          <option value="full">综合分析（基本面+技术面）</option>
          <option value="fundamental">仅基本面</option>
          <option value="technical">仅技术面</option>
        </select>
      </div>
      <textarea v-model="newNote" rows="2" placeholder="备注 / 分析理由（可选）"></textarea>
      <div class="form-actions">
        <button class="primary" @click="submit" :disabled="!newCode">提交</button>
        <button class="ghost" @click="showAdd = false">取消</button>
      </div>
    </div>

    <div class="tabs">
      <button :class="['tab', { active: tab === 'pending' }]" @click="tab = 'pending'">
        待处理 ({{ pendingCount }})
      </button>
      <button :class="['tab', { active: tab === 'stocks' }]" @click="tab = 'stocks'">
        已分析 ({{ stocks.length }})
      </button>
      <button :class="['tab', { active: tab === 'failed' }]" @click="tab = 'failed'">
        失败 ({{ failedCount }})
      </button>
    </div>

    <!-- Pending Requests -->
    <div v-if="tab === 'pending'">
      <div v-if="pending.length === 0" class="empty card">
        没有待处理的请求。点击"提交请求"或微信告诉我分析哪只股票。
      </div>
      <div v-for="r in pending" :key="r.id" class="req-card card">
        <div class="req-header">
          <div>
            <span class="req-code">{{ r.code }}</span>
            <span v-if="r.name" class="req-name">{{ r.name }}</span>
          </div>
          <span class="status pending">等待分析</span>
        </div>
        <p v-if="r.note" class="req-note">{{ r.note }}</p>
        <p class="req-time">{{ fmtTime(r.created_at) }}</p>
        <div class="req-actions">
          <button class="ghost" @click="delReq(r.id)">删除</button>
        </div>
      </div>
    </div>

    <!-- Analyzed Stocks -->
    <div v-if="tab === 'stocks'">
      <div v-if="stocks.length === 0" class="empty card">
        没有已分析的股票。提交请求并分析后才会出现在这里。
      </div>
      <div class="stock-grid">
        <div
          v-for="s in stocks"
          :key="s.code"
          class="stock-card card"
          @click="$router.push('/stock/' + s.code)"
        >
          <div class="stock-header">
            <div class="stock-title">
              <span class="stock-code">{{ s.code }}</span>
              <span class="stock-name">{{ s.name }}</span>
            </div>
            <div class="stock-badges">
              <span v-if="s.watchlist" class="tag tag-yellow">关注</span>
              <span v-if="s.overall !== 'none'" :class="['tag', 'tag-' + s.overall]">
                {{ tagLabel(s.overall) }}
              </span>
            </div>
          </div>
          <div class="stock-meta">
            <span>报告: {{ s.report_count }}</span>
            <span v-if="s.last_analysis" :class="{ expired: isExpired(s.last_analysis) }">
              分析: {{ fmtDate(s.last_analysis) }}
            </span>
            <span v-else class="no-data">未分析</span>
          </div>
          <div v-if="s.latest_note" class="stock-note">
            💭 {{ s.latest_note.content.length > 36 ? s.latest_note.content.slice(0, 36) + '...' : s.latest_note.content }}
          </div>
        </div>
      </div>
    </div>

    <!-- Failed -->
    <div v-if="tab === 'failed'">
      <div v-if="failed.length === 0" class="empty card">
        没有失败的请求。
      </div>
      <div v-for="r in failed" :key="r.id" class="req-card card">
        <div class="req-header">
          <div>
            <span class="req-code">{{ r.code }}</span>
            <span v-if="r.name" class="req-name">{{ r.name }}</span>
          </div>
          <span class="status failed">失败</span>
        </div>
        <p v-if="r.error" class="req-error">{{ r.error }}</p>
        <p v-if="r.note" class="req-note">{{ r.note }}</p>
        <div class="req-actions">
          <button class="ghost" @click="retry(r)">重新分析</button>
          <button class="ghost" @click="delReq(r.id)">删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api.js'

const requests = ref([])
const stocks = ref([])
const showAdd = ref(false)
const newCode = ref('')
const newName = ref('')
const newSector = ref('')
const newNote = ref('')
const tab = ref('pending')

const pending = computed(() => requests.value.filter(r => r.status === 'pending'))
const pendingCount = computed(() => pending.value.length)
const failed = computed(() => requests.value.filter(r => r.status === 'failed'))
const failedCount = computed(() => failed.value.length)

async function load() {
  requests.value = await api.requests.list()
  stocks.value = await api.stocks.list()
}

const newType = ref('full')

async function submit() {
  await api.requests.submit(newCode.value, newName.value, newSector.value, newNote.value, newType.value)
  newCode.value = newName.value = newSector.value = newNote.value = ''
  newType.value = 'full'
  showAdd.value = false
  await load()
  tab.value = 'pending'
}

async function delReq(id) {
  await api.requests.delete(id)
  await load()
}

async function retry(req) {
  // Re-submit as new request
  await api.requests.submit(req.code, req.name, req.sector, req.note + ' (retry)')
  await delReq(req.id)
  await load()
}

function tagLabel(t) {
  return { green: '看好', yellow: '观望', red: '回避', none: '-' }[t] || '-'
}

function fmtDate(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

function fmtTime(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function isExpired(iso) {
  return iso && (Date.now() - new Date(iso).getTime()) > 7 * 86400000
}

onMounted(load)
</script>

<style scoped>
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.header h1 { font-size: 22px; font-weight: 600; }
.add-form { margin-bottom: 20px; }
.add-form h3 { margin-bottom: 8px; font-size: 15px; }
.hint { font-size: 13px; color: #64748b; margin-bottom: 12px; }
.form-row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }
.form-row input { flex: 1; min-width: 140px; }
.add-form textarea { width: 100%; margin-bottom: 10px; }
.form-actions { display: flex; gap: 10px; }

.tabs { display: flex; gap: 8px; margin-bottom: 16px; }
.tab { padding: 8px 16px; border-radius: 6px; background: #1e293b; border: 1px solid #334155; color: #94a3b8; font-size: 14px; cursor: pointer; }
.tab.active { background: #3b82f6; color: white; border-color: #3b82f6; }

.empty { text-align: center; padding: 40px; color: #64748b; }

.req-card { margin-bottom: 12px; }
.req-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.req-code { font-size: 15px; font-weight: 600; color: #e2e8f0; margin-right: 8px; }
.req-name { font-size: 13px; color: #94a3b8; }
.status { font-size: 12px; padding: 2px 10px; border-radius: 999px; }
.status.pending { background: #1e3a5f; color: #60a5fa; }
.status.failed { background: #7f1d1d; color: #f87171; }
.req-note { font-size: 13px; color: #94a3b8; margin: 6px 0; }
.req-error { font-size: 13px; color: #f87171; margin: 6px 0; }
.req-time { font-size: 12px; color: #475569; }
.req-actions { display: flex; gap: 8px; margin-top: 10px; }

.stock-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.stock-card { cursor: pointer; transition: transform 0.15s, border-color 0.15s; }
.stock-card:hover { transform: translateY(-2px); border-color: #3b82f6; }
.stock-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
.stock-code { font-size: 14px; font-weight: 600; color: #60a5fa; margin-right: 8px; }
.stock-name { font-size: 13px; color: #94a3b8; }
.stock-badges { display: flex; gap: 6px; }
.stock-meta { display: flex; gap: 16px; font-size: 12px; color: #64748b; }
.stock-meta .expired { color: #f87171; }
.stock-meta .no-data { color: #475569; }

.stock-note { margin-top: 8px; font-size: 12px; color: #94a3b8; line-height: 1.4; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* Mobile */
@media (max-width: 640px) {
  .header { flex-direction: column; gap: 12px; align-items: stretch; }
  .header h1 { font-size: 18px; }
  .form-row { flex-direction: column; }
  .form-row input { width: 100%; min-width: unset; }
  .tabs { flex-wrap: wrap; }
  .stock-grid { grid-template-columns: 1fr; }
  .stock-card { padding: 16px; }
  .stock-header { flex-direction: column; gap: 6px; }
  .stock-meta { flex-wrap: wrap; gap: 8px; }
  .req-header { flex-direction: column; align-items: flex-start; gap: 4px; }
}
</style>
