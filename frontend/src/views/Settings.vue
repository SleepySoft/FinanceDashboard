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
      <div v-if="!isAdmin" class="card readonly-hint">
        当前为只读账号：可浏览全部数据，但修改操作会被拒绝。可在下方修改自己的密码。
      </div>
      <!-- 未登录访问权限 -->
      <div class="card" v-if="isAdmin">
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

      <!-- 股票分类标签 -->
      <div class="card" v-if="isAdmin">
        <h3>股票分类标签</h3>
        <p class="settings-hint">
          首页按此列表顺序分组显示，拖动 ⠿ 可排序；「说明」会在鼠标悬停分类标签时悬浮显示。
          删除分类后，该分类下的股票移入内置「无分类」（「无分类」平时不显示，仅当其中有股票时出现在看板最后）。
        </p>
        <div class="cat-list">
          <div
            v-for="(row, idx) in catRows"
            :key="row.key"
            :class="['cat-row', { dragging: dragIndex === idx }]"
            draggable="true"
            @dragstart="onCatDragStart(idx)"
            @dragover.prevent
            @drop="onCatDrop(idx)"
            @dragend="dragIndex = null"
          >
            <span class="cat-drag" title="拖动排序">⠿</span>
            <input v-model="row.label" maxlength="20" placeholder="分类名称" class="cat-label" />
            <input v-model="row.desc" maxlength="200" placeholder="说明（鼠标悬停分类标签时显示）" class="cat-desc" />
            <button class="ghost danger-text cat-del" @click="removeCategory(idx)">删除</button>
          </div>
        </div>
        <p v-if="catMsg" :class="['config-msg', catError ? 'err' : 'ok']">{{ catMsg }}</p>
        <div class="settings-actions">
          <button class="ghost" @click="addCategory">添加分类</button>
          <button class="primary" @click="saveCategories" :disabled="savingCats">
            {{ savingCats ? '保存中...' : '保存分类设置' }}
          </button>
        </div>
      </div>

      <!-- 用户管理（仅管理员） -->
      <div class="card" v-if="isAdmin">
        <h3>用户管理</h3>
        <p class="settings-hint">
          只读账号可以浏览全部数据，但不能做任何修改（改状态、记笔记、录交易、改设置都会被拒绝）。
          把只读账号分享给朋友即可；重置密码后该用户需重新登录。
        </p>
        <div class="user-list">
          <div v-for="u in users" :key="u.username" class="user-row">
            <span class="user-name">{{ u.username }}</span>
            <span :class="['user-role', u.role]">{{ u.role === 'admin' ? '管理员' : '只读' }}</span>
            <span class="user-created">{{ fmtUserDate(u.created_at) }}</span>
            <span class="user-actions">
              <button class="ghost" @click="resetUserPw(u)">重置密码</button>
              <button v-if="u.username !== auth.user.value" class="ghost danger-text" @click="removeUser(u)">删除</button>
            </span>
          </div>
        </div>
        <div class="user-create">
          <input v-model="newUserName" placeholder="用户名（字母/数字/_/-）" />
          <input v-model="newUserPassword" type="password" placeholder="初始密码（至少 6 位）" autocomplete="new-password" />
          <select v-model="newUserRole">
            <option value="readonly">只读</option>
            <option value="admin">管理员</option>
          </select>
        </div>
        <p v-if="userMsg" :class="['config-msg', userError ? 'err' : 'ok']">{{ userMsg }}</p>
        <div class="settings-actions">
          <button class="primary" @click="createUser" :disabled="savingUser">
            {{ savingUser ? '创建中...' : '创建账号' }}
          </button>
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
      <div class="card" v-if="isAdmin">
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

      <!-- Tushare 数据源配置 -->
      <div class="card" v-if="isAdmin">
        <h3>Tushare 数据源配置</h3>
        <p class="settings-hint">
          异动扫描与回测使用 Tushare Pro 数据。Token 仅保存在本机 <code>data/_config.json</code>，接口不会回显明文。
        </p>
        <div class="info-row">
          <span class="info-label">当前状态</span>
          <span class="info-value">
            {{ tushareConfigured ? '已配置' : '未配置' }}
            <template v-if="tushareSource === 'env'">（由环境变量 TUSHARE_TOKEN 提供，优先级最高）</template>
            <template v-else-if="tushareSource === 'config'">（保存在配置文件中）</template>
          </span>
        </div>
        <div class="form-row">
          <label>新 Token（留空不修改）</label>
          <input v-model="tushareToken" type="password" autocomplete="off" placeholder="输入新的 Tushare token" />
        </div>
        <p v-if="tushareMsg" :class="['config-msg', tushareError ? 'err' : 'ok']">{{ tushareMsg }}</p>
        <div class="settings-actions">
          <button class="primary" @click="saveTushare" :disabled="savingTushare">保存 Token</button>
          <button class="ghost" @click="testTushare" :disabled="testingTushare">
            {{ testingTushare ? '测试中...' : '测试连接' }}
          </button>
          <button v-if="tushareSource === 'config' && tushareConfigured" class="ghost danger-text" @click="clearTushare" :disabled="savingTushare">
            清除已保存 Token
          </button>
        </div>
      </div>

      <!-- 自动更新（定时任务） -->
      <div class="card" v-if="isAdmin">
        <h3>自动更新（定时任务）</h3>
        <p class="settings-hint">
          价格刷新默认每 5 分钟自动执行；异动扫描会调用 Tushare 全市场数据，需先配置 Token，默认关闭。
        </p>
        <div class="form-row">
          <label>价格刷新间隔（分钟，0=关闭）</label>
          <input v-model.number="priceInterval" type="number" min="0" max="1440" />
        </div>
        <div class="form-row">
          <label>异动扫描间隔（分钟，0=关闭）</label>
          <input v-model.number="anomalyInterval" type="number" min="0" max="1440" />
        </div>
        <div class="form-row">
          <label>浏览提醒（天，0=关闭）</label>
          <input v-model.number="staleViewDays" type="number" min="0" max="365" />
        </div>
        <p class="settings-hint">超过该天数没打开过的股票，看板卡片上的「👁 最后浏览」会闪烁提醒。</p>
        <p v-if="schedMsg" :class="['config-msg', schedError ? 'err' : 'ok']">{{ schedMsg }}</p>
        <div class="info-row" v-for="(task, name) in schedulerTasks" :key="name">
          <span class="info-label">{{ name === 'price_refresh' ? '价格刷新' : '异动扫描' }}</span>
          <span class="info-value">
            <template v-if="task.enabled">
              上次 {{ task.last_run || '—' }} · 下次 {{ task.next_run || '—' }}
            </template>
            <template v-else>未启用</template>
          </span>
        </div>
        <div class="settings-actions">
          <button class="primary" @click="saveScheduler" :disabled="savingSched">保存定时设置</button>
          <button class="ghost" @click="loadSchedulerStatus" :disabled="loadingSched">刷新状态</button>
        </div>
      </div>

      <!-- 防刷屏验证（POW） -->
      <div class="card" v-if="isAdmin">
        <h3>防刷屏验证（POW）</h3>
        <p class="settings-hint">
          用户发消息、提交股票反馈前，浏览器需在本地完成一次 POW 计算（找不到捷径，只能逐个试）。
          难度每 +1 bit，所需计算量翻一倍；下表为约 100 万次/秒的普通浏览器的参考耗时。
        </p>
        <div class="form-row">
          <label>POW 最低难度（bit，8~28，默认 20）</label>
          <input v-model.number="powDifficulty" type="number" min="8" max="28" />
        </div>
        <table class="pow-table">
          <thead><tr><th>难度</th><th>期望计算量</th><th>参考耗时</th></tr></thead>
          <tbody>
            <tr v-for="row in powTable" :key="row.bits" :class="{ current: row.bits === powDifficulty }">
              <td>{{ row.bits }} bit</td><td>{{ row.hashes }}</td><td>{{ row.time }}</td>
            </tr>
          </tbody>
        </table>
        <p v-if="powMsg" :class="['config-msg', powError ? 'err' : 'ok']">{{ powMsg }}</p>
        <div class="settings-actions">
          <button class="primary" @click="savePow" :disabled="savingPow">保存 POW 设置</button>
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
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api.js'
import auth from '../composables/useAuth.js'
import statusCats from '../composables/useStatusCategories.js'

const router = useRouter()

const isAdmin = auth.isAdmin

// 用户管理（仅管理员可见/可用）
const users = ref([])
const newUserName = ref('')
const newUserPassword = ref('')
const newUserRole = ref('readonly')
const userMsg = ref('')
const userError = ref(false)
const savingUser = ref(false)

async function loadUsers() {
  try {
    users.value = await api.auth.listUsers()
  } catch {
    // 列表失败不打断页面
  }
}

function fmtUserDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString()
}

async function createUser() {
  userMsg.value = ''
  userError.value = false
  if (!newUserName.value.trim() || !newUserPassword.value) {
    userError.value = true
    userMsg.value = '请填写用户名和初始密码'
    return
  }
  savingUser.value = true
  try {
    await api.auth.createUser(newUserName.value.trim(), newUserPassword.value, newUserRole.value)
    userMsg.value = `账号「${newUserName.value.trim()}」已创建（${newUserRole.value === 'admin' ? '管理员' : '只读'}）`
    newUserName.value = ''
    newUserPassword.value = ''
    newUserRole.value = 'readonly'
    await loadUsers()
  } catch (e) {
    userError.value = true
    userMsg.value = e.message || '创建失败'
  } finally {
    savingUser.value = false
  }
}

async function removeUser(u) {
  if (!window.confirm(`删除账号「${u.username}」？该用户的登录会话将立即失效。`)) return
  userMsg.value = ''
  userError.value = false
  try {
    await api.auth.deleteUser(u.username)
    userMsg.value = `账号「${u.username}」已删除`
    await loadUsers()
  } catch (e) {
    userError.value = true
    userMsg.value = e.message || '删除失败'
  }
}

async function resetUserPw(u) {
  const pw = window.prompt(`为「${u.username}」设置新密码（至少 6 位）：`)
  if (!pw) return
  userMsg.value = ''
  userError.value = false
  try {
    await api.auth.resetUserPassword(u.username, pw)
    userMsg.value = `「${u.username}」的密码已重置，该用户需用新密码重新登录`
  } catch (e) {
    userError.value = true
    userMsg.value = e.message || '重置失败'
  }
}

// 股票分类标签（改名/新增/删除/拖动排序）
const catRows = ref([])
const catMsg = ref('')
const catError = ref(false)
const savingCats = ref(false)
const dragIndex = ref(null)

function resetCatRows() {
  catRows.value = statusCats.categories.value.map(c => ({ key: c.key, label: c.label, desc: c.desc || '' }))
}

function addCategory() {
  catRows.value.push({ key: 'cat_' + Math.random().toString(36).slice(2, 10), label: '', desc: '' })
}

function removeCategory(idx) {
  const row = catRows.value[idx]
  if (!window.confirm(`删除分类「${row.label || row.key}」？该分类下的股票将移入「无分类」。`)) return
  catRows.value.splice(idx, 1)
}

function onCatDragStart(idx) {
  dragIndex.value = idx
}

function onCatDrop(idx) {
  if (dragIndex.value === null || dragIndex.value === idx) return
  const moved = catRows.value.splice(dragIndex.value, 1)[0]
  catRows.value.splice(idx, 0, moved)
  dragIndex.value = null
}

async function saveCategories() {
  catMsg.value = ''
  catError.value = false
  const labels = catRows.value.map(r => r.label.trim())
  if (labels.some(l => !l)) {
    catError.value = true
    catMsg.value = '分类名称不能为空'
    return
  }
  if (new Set(labels).size !== labels.length) {
    catError.value = true
    catMsg.value = '分类名称不能重复'
    return
  }
  savingCats.value = true
  try {
    const payload = catRows.value.map(r => ({ key: r.key, label: r.label.trim(), desc: (r.desc || '').trim() }))
    const cfg = await auth.updateConfig({ status_categories: payload })
    const n = cfg.reassigned_count || 0
    catMsg.value = n > 0 ? `分类设置已保存，${n} 只股票已移入「无分类」` : '分类设置已保存'
    resetCatRows()
  } catch (e) {
    catError.value = true
    catMsg.value = e.message || '保存失败'
  } finally {
    savingCats.value = false
  }
}

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

// Tushare 数据源配置
const tushareToken = ref('')
const tushareMsg = ref('')
const tushareError = ref(false)
const savingTushare = ref(false)
const testingTushare = ref(false)
const tushareConfigured = computed(() => !!auth.config.value.tushare_token_configured)
const tushareSource = computed(() => auth.config.value.tushare_token_source || 'none')

async function saveTushare() {
  tushareMsg.value = ''
  tushareError.value = false
  savingTushare.value = true
  try {
    const patch = tushareToken.value ? { tushare_token: tushareToken.value } : {}
    const cfg = await auth.updateConfig(patch)
    await auth.bootstrap(true)
    tushareToken.value = ''
    tushareMsg.value = cfg.tushare_token_configured ? 'Token 已保存' : '当前仍未配置 Token'
  } catch (e) {
    tushareError.value = true
    tushareMsg.value = e.message || '保存失败'
  } finally {
    savingTushare.value = false
  }
}

async function clearTushare() {
  if (!window.confirm('将清除配置文件中保存的 Tushare token，继续？')) return
  tushareMsg.value = ''
  tushareError.value = false
  savingTushare.value = true
  try {
    await auth.updateConfig({ tushare_token: '' })
    await auth.bootstrap(true)
    tushareMsg.value = '已清除配置文件中的 Token'
  } catch (e) {
    tushareError.value = true
    tushareMsg.value = e.message || '清除失败'
  } finally {
    savingTushare.value = false
  }
}

async function testTushare() {
  tushareMsg.value = ''
  tushareError.value = false
  testingTushare.value = true
  try {
    const res = await api.tushare.test(tushareToken.value || '')
    tushareError.value = !res.ok
    tushareMsg.value = res.message
  } catch (e) {
    tushareError.value = true
    tushareMsg.value = e.message || '测试失败'
  } finally {
    testingTushare.value = false
  }
}

// 自动更新（定时任务）
const priceInterval = ref(auth.config.value.price_refresh_interval_min ?? 5)
const anomalyInterval = ref(auth.config.value.anomaly_scan_interval_min ?? 0)
const staleViewDays = ref(auth.config.value.stale_view_days ?? 7)
const schedulerTasks = ref({})
const schedMsg = ref('')
const schedError = ref(false)
const savingSched = ref(false)
const loadingSched = ref(false)

async function loadSchedulerStatus() {
  loadingSched.value = true
  try {
    const res = await api.scheduler.status()
    schedulerTasks.value = res.tasks || {}
  } catch {
    // 状态获取失败不打断页面
  } finally {
    loadingSched.value = false
  }
}

async function saveScheduler() {
  schedMsg.value = ''
  schedError.value = false
  savingSched.value = true
  try {
    const cfg = await auth.updateConfig({
      price_refresh_interval_min: Number(priceInterval.value) || 0,
      anomaly_scan_interval_min: Number(anomalyInterval.value) || 0,
      stale_view_days: Number(staleViewDays.value) || 0,
    })
    priceInterval.value = cfg.price_refresh_interval_min
    anomalyInterval.value = cfg.anomaly_scan_interval_min
    staleViewDays.value = cfg.stale_view_days
    schedMsg.value = '定时设置已保存，将在下个周期生效'
    await loadSchedulerStatus()
  } catch (e) {
    schedError.value = true
    schedMsg.value = e.message || '保存失败'
  } finally {
    savingSched.value = false
  }
}

onMounted(() => {
  if (!isAdmin.value) return
  loadSchedulerStatus()
  resetCatRows()
  loadUsers()
})

// 防刷屏验证（POW）难度
const powDifficulty = ref(auth.config.value.pow_difficulty ?? 20)
const powMsg = ref('')
const powError = ref(false)
const savingPow = ref(false)
const powTable = [
  { bits: 16, hashes: '6.5 万次', time: '不到 0.1 秒' },
  { bits: 18, hashes: '26 万次', time: '约 0.3 秒' },
  { bits: 20, hashes: '105 万次', time: '约 1 秒（默认）' },
  { bits: 22, hashes: '419 万次', time: '约 4 秒' },
  { bits: 24, hashes: '1678 万次', time: '约 17 秒' },
  { bits: 26, hashes: '6711 万次', time: '约 1 分钟' },
  { bits: 28, hashes: '2.7 亿次', time: '约 4.5 分钟' },
]

async function savePow() {
  powMsg.value = ''
  powError.value = false
  savingPow.value = true
  try {
    const cfg = await auth.updateConfig({ pow_difficulty: Number(powDifficulty.value) })
    powDifficulty.value = cfg.pow_difficulty
    powMsg.value = 'POW 难度已保存，立即生效'
  } catch (e) {
    powError.value = true
    powMsg.value = e.message || '保存失败'
  } finally {
    savingPow.value = false
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
button.ghost {
  padding: 8px 14px;
  border: 1px solid #334155;
  border-radius: 6px;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  font-size: 13px;
}
button.ghost:hover {
  color: #e2e8f0;
  border-color: #475569;
}
button.ghost:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
button.ghost.danger-text {
  color: #f87171;
}
.info-row {
  display: flex;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px dashed #334155;
  font-size: 14px;
}
.cat-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 14px;
}
.cat-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  border: 1px solid #334155;
  border-radius: 8px;
  background: rgba(30, 41, 59, 0.4);
}
.cat-row.dragging {
  opacity: 0.5;
  border-color: #3b82f6;
}
.cat-drag {
  cursor: grab;
  color: #64748b;
  user-select: none;
}
.cat-row input {
  flex: 1;
  min-width: 0;
}
.cat-row input.cat-label {
  flex: 0 0 140px;
}
.cat-row input.cat-desc {
  color: #94a3b8;
}
.cat-del {
  padding: 4px 10px;
  font-size: 12px;
  flex-shrink: 0;
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
.readonly-hint {
  color: #fbbf24;
  font-size: 13px;
  padding: 12px 16px;
}
.user-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 14px;
}
.user-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border: 1px solid #334155;
  border-radius: 8px;
  font-size: 14px;
}
.user-name {
  color: #e2e8f0;
  font-weight: 600;
  min-width: 100px;
}
.user-role {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
}
.user-role.admin {
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
}
.user-role.readonly {
  background: rgba(148, 163, 184, 0.15);
  color: #94a3b8;
}
.user-created {
  color: #64748b;
  font-size: 12px;
  flex: 1;
}
.user-actions {
  display: flex;
  gap: 6px;
}
.user-actions button {
  padding: 4px 10px;
  font-size: 12px;
}
.user-create {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
}
.user-create input,
.user-create select {
  flex: 1;
  min-width: 0;
}
.pow-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 12px;
}
.pow-table th,
.pow-table td {
  text-align: left;
  padding: 4px 8px;
  border-bottom: 1px dashed #334155;
}
.pow-table th {
  color: #64748b;
  font-weight: 500;
}
.pow-table tr.current td {
  color: #60a5fa;
  font-weight: 600;
}
.login-link {
  color: #60a5fa;
  margin-left: 8px;
}
</style>
