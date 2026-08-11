<template>
  <div class="settings-page">
    <div class="settings-header">
      <h2>设置</h2>
      <router-link to="/" class="btn-ghost">← 返回看板</router-link>
    </div>

    <div v-if="!auth.isAuthenticated.value" class="card empty">
      需要登录后才能访问设置。
      <router-link to="/login" class="login-link">去登录</router-link>
    </div>

    <template v-else>
      <!-- 未登录访问权限 -->
      <div class="card">
        <h3>未登录访问权限</h3>
        <p class="settings-hint">控制未登录访客能看到什么：</p>
        <div class="mode-options">
          <label
            :class="['mode-option', { active: mode === 'locked' }]"
          >
            <input type="radio" value="locked" v-model="mode" />
            <div class="mode-text">
              <span class="mode-title">完全锁定</span>
              <span class="mode-desc">未登录时看不到任何内容，一律跳转登录页</span>
            </div>
          </label>
          <label
            :class="['mode-option', { active: mode === 'readonly' }]"
          >
            <input type="radio" value="readonly" v-model="mode" />
            <div class="mode-text">
              <span class="mode-title">只读模式</span>
              <span class="mode-desc">未登录可以浏览数据，但所有修改操作需要登录</span>
            </div>
          </label>
        </div>
        <p v-if="configMsg" :class="['config-msg', configError ? 'err' : 'ok']">{{ configMsg }}</p>
        <div class="settings-actions">
          <button class="primary" @click="saveMode" :disabled="savingMode">保存权限设置</button>
        </div>
      </div>

      <!-- 修改密码 -->
      <div class="card">
        <h3>修改密码</h3>
        <div class="form-row">
          <label>原密码</label>
          <input v-model="oldPassword" type="password" autocomplete="current-password" />
        </div>
        <div class="form-row">
          <label>新密码（至少 6 位）</label>
          <input v-model="newPassword" type="password" autocomplete="new-password" />
        </div>
        <div class="form-row">
          <label>确认新密码</label>
          <input v-model="confirmPassword" type="password" autocomplete="new-password" />
        </div>
        <p v-if="pwMsg" :class="['config-msg', pwError ? 'err' : 'ok']">{{ pwMsg }}</p>
        <div class="settings-actions">
          <button class="primary" @click="changePassword" :disabled="savingPw">修改密码</button>
        </div>
      </div>

      <!-- Agent 访问密钥 -->
      <div class="card">
        <h3>Agent 访问密钥</h3>
        <p class="settings-hint">
          本地 Agent 通过项目根目录 <code>agent_token.txt</code> 读取密钥（首次启动自动生成）。
          重新生成后旧密钥立即失效，正在运行的 Agent 需要重新读取该文件。
        </p>
        <div class="info-row">
          <span class="info-label">当前状态</span>
          <span class="info-value">
            {{ auth.config.value.api_key_configured ? '已配置（见 agent_token.txt）' : '未配置（点击下方生成）' }}
          </span>
        </div>
        <p v-if="tokenMsg" :class="['config-msg', tokenError ? 'err' : 'ok']">{{ tokenMsg }}</p>
        <div class="settings-actions">
          <button class="primary" @click="generateToken" :disabled="generatingToken">
            {{ generatingToken ? '生成中...' : '生成新 Token' }}
          </button>
        </div>
      </div>

      <!-- 账户信息 -->
      <div class="card">
        <h3>账户信息</h3>
        <div class="info-row">
          <span class="info-label">当前用户</span>
          <span class="info-value">{{ auth.user.value }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">会话有效期</span>
          <span class="info-value">{{ auth.config.value.session_ttl_hours }} 小时</span>
        </div>
        <div class="settings-actions">
          <button class="danger" @click="doLogout">退出登录</button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api.js'
import auth from '../composables/useAuth.js'

const router = useRouter()

// 权限模式
const mode = ref(auth.config.value.allow_anonymous_read ? 'readonly' : 'locked')
const configMsg = ref('')
const configError = ref(false)
const savingMode = ref(false)

async function saveMode() {
  configMsg.value = ''
  configError.value = false
  savingMode.value = true
  try {
    const cfg = await auth.updateConfig({ allow_anonymous_read: mode.value === 'readonly' })
    mode.value = cfg.allow_anonymous_read ? 'readonly' : 'locked'
    configMsg.value = '权限设置已保存'
  } catch (e) {
    configError.value = true
    configMsg.value = e.message || '保存失败'
  } finally {
    savingMode.value = false
  }
}

// Agent 访问密钥
const tokenMsg = ref('')
const tokenError = ref(false)
const generatingToken = ref(false)

async function generateToken() {
  if (!window.confirm('将重新生成 Agent 访问密钥，旧密钥立即失效。继续？')) return
  tokenMsg.value = ''
  tokenError.value = false
  generatingToken.value = true
  try {
    const res = await api.auth.regenerateToken()
    tokenMsg.value = `${res.message}（页面不显示明文，本机 Agent 直接读取该文件）`
    await auth.bootstrap(true)
  } catch (e) {
    tokenError.value = true
    tokenMsg.value = e.message || '生成失败'
  } finally {
    generatingToken.value = false
  }
}

// 修改密码
const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const pwMsg = ref('')
const pwError = ref(false)
const savingPw = ref(false)

async function changePassword() {
  pwMsg.value = ''
  pwError.value = false
  if (newPassword.value !== confirmPassword.value) {
    pwError.value = true
    pwMsg.value = '两次输入的新密码不一致'
    return
  }
  savingPw.value = true
  try {
    await auth.changePassword(oldPassword.value, newPassword.value)
    pwMsg.value = '密码已修改'
    oldPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
  } catch (e) {
    pwError.value = true
    pwMsg.value = e.message || '修改失败'
  } finally {
    savingPw.value = false
  }
}

// 退出登录
async function doLogout() {
  await auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.settings-page {
  max-width: 680px;
  margin: 0 auto;
  padding: 16px;
}
.settings-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.settings-header h2 {
  font-size: 20px;
  color: #e2e8f0;
}
.btn-ghost {
  padding: 6px 14px;
  border: 1px solid #334155;
  border-radius: 6px;
  color: #94a3b8;
  text-decoration: none;
  font-size: 13px;
}
.btn-ghost:hover {
  color: #e2e8f0;
  border-color: #475569;
}
.settings-hint {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 12px;
}
.settings-hint code {
  background: #1e293b;
  color: #93c5fd;
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 12px;
}
.mode-options {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 14px;
}
.mode-option {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 14px;
  border: 1px solid #334155;
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.mode-option.active {
  border-color: #3b82f6;
  background: rgba(59, 130, 246, 0.08);
}
.mode-option input {
  margin-top: 3px;
  accent-color: #3b82f6;
}
.mode-text {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.mode-title {
  font-size: 14px;
  font-weight: 600;
  color: #e2e8f0;
}
.mode-desc {
  font-size: 12px;
  color: #94a3b8;
}
.form-row {
  margin-bottom: 14px;
}
.form-row label {
  display: block;
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 5px;
}
.form-row input {
  width: 100%;
  max-width: 360px;
  box-sizing: border-box;
}
.config-msg {
  font-size: 13px;
  margin-bottom: 12px;
}
.config-msg.ok {
  color: #34d399;
}
.config-msg.err {
  color: #f87171;
}
.settings-actions {
  display: flex;
  gap: 10px;
}
.info-row {
  display: flex;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px dashed #334155;
  font-size: 14px;
}
.info-label {
  color: #64748b;
  min-width: 90px;
}
.info-value {
  color: #e2e8f0;
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
