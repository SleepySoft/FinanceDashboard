<template>
  <div class="login-page">
    <div class="login-card card">
      <div class="login-logo">FinanceDashboard</div>
      <h1 class="login-title">登录</h1>
      <p v-if="auth.config.value.allow_anonymous_read" class="login-hint">
        当前为只读模式，未登录也可浏览；登录后可进行修改操作。
      </p>
      <p v-else class="login-hint">
        当前为完全锁定模式，需要登录后才能查看。
      </p>

      <form @submit.prevent="submit">
        <div class="form-row">
          <label>用户名</label>
          <input v-model="username" autocomplete="username" placeholder="用户名" required />
        </div>
        <div class="form-row">
          <label>密码</label>
          <input
            v-model="password"
            type="password"
            autocomplete="current-password"
            placeholder="密码"
            required
          />
        </div>
        <p v-if="error" class="login-error">{{ error }}</p>
        <button class="primary login-submit" type="submit" :disabled="submitting">
          {{ submitting ? '登录中...' : '登录' }}
        </button>
      </form>

      <div v-if="auth.config.value.allow_anonymous_read" class="login-footer">
        <router-link to="/">以只读方式浏览</router-link>
      </div>
      <div class="login-footer muted">
        首次运行的管理员账号与初始密码见服务器日志 / data/_users.json
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import auth from '../composables/useAuth.js'

const route = useRoute()
const router = useRouter()

const username = ref('')
const password = ref('')
const error = ref('')
const submitting = ref(false)

async function submit() {
  error.value = ''
  submitting.value = true
  try {
    await auth.login(username.value.trim(), password.value)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.push(redirect)
  } catch (e) {
    error.value = e.message || '登录失败'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 60vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px 0;
}
.login-card {
  width: 100%;
  max-width: 380px;
  padding: 28px;
}
.login-logo {
  font-size: 18px;
  font-weight: 700;
  color: #60a5fa;
  text-align: center;
  margin-bottom: 4px;
}
.login-title {
  font-size: 20px;
  font-weight: 600;
  text-align: center;
  color: #e2e8f0;
  margin: 8px 0 12px;
}
.login-hint {
  font-size: 12px;
  color: #94a3b8;
  text-align: center;
  margin-bottom: 16px;
  line-height: 1.6;
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
  box-sizing: border-box;
}
.login-error {
  color: #f87171;
  font-size: 13px;
  margin-bottom: 12px;
}
.login-submit {
  width: 100%;
  padding: 10px;
  font-size: 15px;
}
.login-footer {
  margin-top: 16px;
  text-align: center;
  font-size: 12px;
}
.login-footer a {
  color: #60a5fa;
  text-decoration: none;
}
.login-footer.muted {
  color: #475569;
  margin-top: 10px;
}
</style>
