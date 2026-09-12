<template>
  <div class="messages-page">
    <div class="messages-header">
      <h2>消息箱</h2>
    </div>
    <p class="messages-hint">
      在这里给站主留言（建议、纠错、想看的股票都可以）。{{ isAdmin ? '你是管理员，可以看到所有人的留言。' : '你只能看到自己发出的留言。' }}
    </p>

    <div v-if="!isAuthenticated" class="card empty">
      需要登录后才能使用消息箱。
      <router-link to="/login" class="login-link">去登录</router-link>
    </div>

    <template v-else>
      <div class="card">
        <textarea
          v-model="draft"
          class="msg-input"
          rows="3"
          maxlength="2000"
          placeholder="写点什么……（发送前需要完成一次 POW 验证）"
        ></textarea>
        <PowPanel ref="powPanel" scope="message" />
        <div class="msg-actions">
          <span class="msg-count">{{ draft.length }}/2000</span>
          <button class="primary" @click="send" :disabled="sending || !draft.trim() || !powPanel?.powReady">
            {{ sending ? '验证并发送中...' : '发送' }}
          </button>
        </div>
        <p v-if="msgError" class="msg-error">{{ msgError }}</p>
      </div>

      <div v-if="messages.length === 0" class="card empty">暂无留言</div>
      <div v-for="m in messages" :key="m.id" class="card msg-item">
        <div class="msg-meta">
          <span class="msg-user">{{ m.username }}</span>
          <span class="msg-time">{{ fmtTime(m.created_at) }}</span>
          <span class="msg-pow" title="该消息提交时完成的 POW 难度">POW {{ m.pow_difficulty }}bit</span>
          <button v-if="isAdmin" class="msg-del" @click="remove(m)">删除</button>
        </div>
        <div class="msg-content">{{ m.content }}</div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api.js'
import auth from '../composables/useAuth.js'
import PowPanel from '../powbox/PowPanel.vue'

const isAuthenticated = auth.isAuthenticated
const isAdmin = auth.isAdmin

const messages = ref([])
const draft = ref('')
const sending = ref(false)
const msgError = ref('')
const powPanel = ref(null)

async function load() {
  try {
    messages.value = await api.messages.list()
  } catch {
    // 列表失败不打断页面
  }
}

async function send() {
  msgError.value = ''
  sending.value = true
  try {
    const content = draft.value.trim()
    const pow = await powPanel.value.obtainPow(content)
    await api.messages.send(content, pow)
    draft.value = ''
    await load()
  } catch (e) {
    if (e.message !== '已取消') msgError.value = e.message || '发送失败'
  } finally {
    sending.value = false
  }
}

async function remove(m) {
  if (!window.confirm('删除这条留言？')) return
  try {
    await api.messages.delete(m.id)
    await load()
  } catch (e) {
    msgError.value = e.message || '删除失败'
  }
}

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleString()
}

onMounted(() => {
  if (isAuthenticated.value) load()
})
</script>

<style scoped>
.messages-page {
  max-width: 680px;
  margin: 0 auto;
  padding: 16px;
}
.messages-header h2 {
  font-size: 20px;
  color: #e2e8f0;
  margin-bottom: 8px;
}
.messages-hint {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 14px;
}
.msg-input {
  width: 100%;
  box-sizing: border-box;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 8px;
  color: #e2e8f0;
  padding: 10px 12px;
  font-size: 14px;
  resize: vertical;
}
.msg-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 4px;
}
.msg-count {
  font-size: 12px;
  color: #64748b;
}
.msg-error {
  color: #f87171;
  font-size: 13px;
  margin-top: 8px;
}
.msg-item {
  margin-top: 10px;
}
.msg-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.msg-user {
  color: #60a5fa;
  font-weight: 600;
  font-size: 13px;
}
.msg-time {
  color: #64748b;
  font-size: 12px;
}
.msg-pow {
  color: #475569;
  font-size: 11px;
}
.msg-del {
  margin-left: auto;
  background: none;
  border: none;
  color: #f87171;
  cursor: pointer;
  font-size: 12px;
}
.msg-content {
  color: #e2e8f0;
  font-size: 14px;
  white-space: pre-wrap;
  line-height: 1.6;
}
.empty {
  text-align: center;
  padding: 40px;
  color: #64748b;
}
.login-link {
  color: #60a5fa;
  margin-left: 8px;
}
</style>
