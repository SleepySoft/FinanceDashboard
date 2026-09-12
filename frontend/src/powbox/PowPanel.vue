<template>
  <div class="pow-panel">
    <p class="pow-title">🛡 防刷屏验证（POW 工作量证明）</p>
    <p class="pow-desc">
      POW（Proof of Work，工作量证明）会让你的浏览器在本地做一道计算题：
      找到一个数字，使「挑战串 + 你提交的内容 + 该数字」的 SHA-256 哈希值以足够多个 0 开头。
      没有捷径只能逐个试，因此要付出几秒钟的真实算力——机器人批量刷屏会因此变得非常昂贵，
      而正常用户只多花几秒。计算完全在你的浏览器里进行，不会上传任何隐私数据。
    </p>

    <div class="pow-row">
      <span class="pow-label">当前最低要求</span>
      <span v-if="configLoaded">
        难度 {{ minDifficulty }} bit ≈ 约 {{ fmtHashes(2 ** minDifficulty) }} 次计算
        ≈ 预计 {{ fmtDuration(estFor(minDifficulty)) }}
      </span>
      <span v-else>加载站点配置中……</span>
    </div>

    <div class="pow-slider-row">
      <span class="pow-label">手动选择难度</span>
      <input
        type="range"
        :min="0"
        :max="maxDifficulty"
        v-model.number="difficulty"
        :disabled="computing || !configLoaded"
      />
      <span class="pow-diff-value">{{ difficulty }} bit</span>
    </div>
    <p v-if="!configLoaded" class="pow-delta warn">
      正在获取站点 POW 要求……获取成功前不能提交。
    </p>
    <p v-else-if="difficulty < minDifficulty" class="pow-delta warn">
      当前选择 {{ difficulty }} bit 不足以提交。请手动拖动到 {{ minDifficulty }} bit 或以上；
      达到最低要求约需 {{ fmtDuration(estFor(minDifficulty)) }}，难度每 +1 bit，计算量翻一倍。
    </p>
    <p v-else-if="difficulty > minDifficulty" class="pow-delta up">
      比最低要求高 {{ difficulty - minDifficulty }} bit：计算量 ×{{ fmtTimes(difficulty - minDifficulty) }}，
      预计约 {{ fmtDuration(estFor(difficulty)) }} —— 难度每 +1 bit，计算量翻一倍。
    </p>
    <p v-else class="pow-delta">
      当前选择即最低要求，预计约 {{ fmtDuration(estFor(difficulty)) }}。
      难度每 +1 bit，计算量翻一倍。
    </p>

    <div v-if="computing" class="pow-progress">
      <div class="pow-bar"><div class="pow-bar-fill" :style="{ width: progressPct + '%' }"></div></div>
      <div class="pow-stats">
        已计算 {{ fmtHashes(hashes) }} 次 · 速度 {{ fmtRate(rate) }} ·
        已用 {{ (elapsedMs / 1000).toFixed(1) }}s · 预计还需 {{ fmtDuration(remainingSec) }}
      </div>
      <button class="pow-cancel" @click="cancelSolve">取消</button>
    </div>
    <p v-else-if="doneInfo" class="pow-done">✓ {{ doneInfo }}</p>
    <p v-if="error" class="pow-error">{{ error }}</p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { fetchChallenge, fetchPowConfig } from './api.js'
import { solvePow } from './solver.js'

/**
 * PowPanel — POW 说明 + 难度选择 + 求解进度，自成一体。
 * 父组件用法：
 *   <PowPanel ref="powPanel" scope="message" />
 *   const pow = await powPanel.value.obtainPow(contentString)  // 取消/失败会 throw
 *   await api.xxx.submit({ ..., pow })
 */
const props = defineProps({
  scope: { type: String, required: true },
})
const minDifficulty = ref(null)
const maxDifficulty = ref(28)
const difficulty = ref(0)
const configLoaded = ref(false)

// 浏览器实测算力（H/s），跨会话记忆，用于耗时预估
const measuredRate = ref(Number(localStorage.getItem('powbox_hashrate')) || 1e6)

const computing = ref(false)
const hashes = ref(0)
const rate = ref(0)
const elapsedMs = ref(0)
const doneInfo = ref('')
const error = ref('')

let currentSolve = null

const expectedHashes = computed(() => 2 ** difficulty.value)
const remainingSec = computed(() => {
  if (!rate.value) return estFor(difficulty.value)
  return Math.max(0, (expectedHashes.value - hashes.value) / rate.value)
})
const progressPct = computed(() => {
  // 期望意义上的进度（指数分布，可能超 100%，封顶显示）
  return Math.min(100, (hashes.value / expectedHashes.value) * 100)
})

const powReady = computed(() => configLoaded.value && difficulty.value >= minDifficulty.value)

function estFor(bits) {
  return 2 ** bits / measuredRate.value
}

function fmtHashes(n) {
  if (n < 1e4) return String(Math.round(n))
  if (n < 1e8) return (n / 1e4).toFixed(1).replace(/\.0$/, '') + ' 万'
  return (n / 1e8).toFixed(1).replace(/\.0$/, '') + ' 亿'
}

function fmtRate(r) {
  if (!r) return '--'
  return fmtHashes(r) + ' 次/秒'
}

function fmtTimes(k) {
  const t = 2 ** k
  return t >= 1024 ? (t / 1024) + 'K' : String(t)
}

function fmtDuration(sec) {
  if (!Number.isFinite(sec)) return '--'
  if (sec < 1) return '不到 1 秒'
  if (sec < 60) return `约 ${Math.ceil(sec)} 秒`
  if (sec < 3600) return `约 ${Math.ceil(sec / 60)} 分钟`
  return `约 ${(sec / 3600).toFixed(1)} 小时`
}

async function obtainPow(content) {
  if (computing.value) throw new Error('正在计算中')
  if (!configLoaded.value) throw new Error('POW 配置未加载')
  if (difficulty.value < minDifficulty.value) throw new Error(`POW 难度需拖动到 ${minDifficulty.value} bit 或以上`)
  error.value = ''
  doneInfo.value = ''
  computing.value = true
  hashes.value = 0
  elapsedMs.value = 0
  try {
    const ch = await fetchChallenge(props.scope)
    const solve = solvePow({
      challenge: ch.challenge,
      content,
      difficulty: difficulty.value,
      onProgress: (p) => {
        hashes.value = p.hashes
        rate.value = p.rate
        elapsedMs.value = p.elapsedMs
      },
    })
    currentSolve = solve
    const result = await solve.promise
    // 记住实测算力，下次预估更准
    if (result.rate > 0) {
      measuredRate.value = result.rate
      localStorage.setItem('powbox_hashrate', String(Math.round(result.rate)))
    }
    doneInfo.value = `验证完成：${difficulty.value} bit · ${fmtHashes(result.hashes)} 次计算 · 耗时 ${(result.elapsedMs / 1000).toFixed(1)}s`
    return { challenge: ch.challenge, nonce: result.nonce, difficulty: difficulty.value }
  } catch (e) {
    if (e.message !== '已取消') error.value = e.message || 'POW 计算失败'
    throw e
  } finally {
    computing.value = false
    currentSolve = null
  }
}

function cancelSolve() {
  currentSolve?.cancel()
}

onMounted(async () => {
  try {
    const cfg = await fetchPowConfig()
    minDifficulty.value = cfg.min_difficulty
    maxDifficulty.value = cfg.bounds?.[1] ?? 28
    configLoaded.value = true
  } catch {
    configLoaded.value = false
    error.value = 'POW 配置加载失败，请刷新后重试'
  }
})

defineExpose({ obtainPow, powReady })
</script>

<style scoped>
.pow-panel {
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 12px 14px;
  background: rgba(30, 41, 59, 0.4);
  margin: 10px 0;
}
.pow-title {
  font-size: 13px;
  font-weight: 600;
  color: #e2e8f0;
  margin-bottom: 6px;
}
.pow-desc {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.6;
  margin-bottom: 10px;
}
.pow-row,
.pow-slider-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: #cbd5e1;
  margin-bottom: 8px;
}
.pow-label {
  color: #64748b;
  font-size: 12px;
  min-width: 108px;
  flex-shrink: 0;
}
.pow-slider-row input[type='range'] {
  flex: 1;
  accent-color: #3b82f6;
}
.pow-diff-value {
  font-weight: 600;
  color: #60a5fa;
  min-width: 48px;
  text-align: right;
}
.pow-delta {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 8px;
}
.pow-delta.up {
  color: #fbbf24;
}
.pow-delta.warn {
  color: #f87171;
}
.pow-progress {
  margin-top: 6px;
}
.pow-bar {
  height: 8px;
  background: #1e293b;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 6px;
}
.pow-bar-fill {
  height: 100%;
  background: #3b82f6;
  transition: width 0.2s;
}
.pow-stats {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 6px;
}
.pow-cancel {
  padding: 4px 12px;
  border: 1px solid #475569;
  border-radius: 6px;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  font-size: 12px;
}
.pow-cancel:hover {
  color: #f87171;
  border-color: #f87171;
}
.pow-done {
  font-size: 12px;
  color: #34d399;
  margin-top: 6px;
}
.pow-error {
  font-size: 12px;
  color: #f87171;
  margin-top: 6px;
}
</style>
