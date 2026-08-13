<template>
  <div class="strategy-library">
    <div class="page-header">
      <h2>策略库</h2>
      <router-link to="/backtest" class="btn-link">去回测 →</router-link>
    </div>

    <div class="strategy-grid">
      <div v-for="s in strategies" :key="s.id" class="strategy-card" :class="{builtin: s.type === 'builtin', custom: s.type === 'custom'}">
        <div class="strategy-header">
          <span class="strategy-icon">{{ iconFor(s.tags) }}</span>
          <div class="strategy-title">
            <div class="strategy-name">{{ s.name }}</div>
            <div class="strategy-meta">
              <span class="type-badge" :class="s.type">{{ s.type === 'builtin' ? '内置' : '自定义' }}</span>
              <span v-for="tag in s.tags" :key="tag" class="mini-tag">{{ tag }}</span>
            </div>
          </div>
        </div>
        <div class="strategy-desc">{{ s.description || '暂无描述' }}</div>
        <div class="strategy-params" v-if="s.params && s.params.length">
          <span v-for="p in s.params" :key="p.name" class="param-chip">
            {{ p.name }}: {{ p.default }}
          </span>
        </div>
        <div class="strategy-actions">
          <router-link :to="`/backtest?strategy=${s.id}`" class="btn-primary">回测</router-link>
          <button v-if="s.type === 'custom'" class="btn-ghost" @click="editStrategy(s)">编辑</button>
          <button v-if="s.type === 'custom'" class="btn-ghost danger" @click="deleteStrategy(s.id)">删除</button>
        </div>
      </div>
    </div>

    <div v-if="strategies.length === 0" class="empty">加载中...</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const strategies = ref([])
const router = useRouter()

async function loadStrategies() {
  try {
    const res = await fetch('/api/backtest/strategies')
    const data = await res.json()
    strategies.value = data.strategies || []
  } catch (e) {
    console.error('Failed to load strategies:', e)
  }
}

function iconFor(tags) {
  if (!tags) return '📊'
  const t = tags.join('')
  if (t.includes('趋势')) return '📈'
  if (t.includes('反转')) return '📉'
  if (t.includes('动量')) return '⚡'
  if (t.includes('突破')) return '🚀'
  return '📊'
}

function editStrategy(s) {
  // TODO: open editor modal or navigate to editor
  alert('编辑功能待完善')
}

async function deleteStrategy(id) {
  if (!confirm('确定删除此策略？')) return
  try {
    const res = await fetch(`/api/backtest/strategies/${id}`, { method: 'DELETE' })
    if (res.ok) {
      strategies.value = strategies.value.filter(s => s.id !== id)
    }
  } catch (e) {
    console.error('Failed to delete:', e)
  }
}

onMounted(loadStrategies)
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-header h2 {
  font-size: 18px;
  font-weight: 600;
}
.btn-link {
  color: #60a5fa;
  text-decoration: none;
  font-size: 14px;
}

.strategy-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.strategy-card {
  background: #151e2e;
  border: 1px solid #334155;
  border-radius: 10px;
  padding: 16px;
  transition: border-color 0.15s;
}
.strategy-card:hover {
  border-color: #475569;
}
.strategy-card.builtin {
  border-left: 3px solid #3b82f6;
}
.strategy-card.custom {
  border-left: 3px solid #10b981;
}

.strategy-header {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 8px;
}
.strategy-icon {
  font-size: 22px;
}
.strategy-name {
  font-size: 15px;
  font-weight: 600;
}
.strategy-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
  flex-wrap: wrap;
}
.type-badge {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 500;
}
.type-badge.builtin {
  background: #1e3a5f;
  color: #60a5fa;
}
.type-badge.custom {
  background: #064e3b;
  color: #34d399;
}
.mini-tag {
  font-size: 11px;
  color: #94a3b8;
  background: #1e293b;
  padding: 1px 6px;
  border-radius: 4px;
}

.strategy-desc {
  font-size: 13px;
  color: #94a3b8;
  margin-bottom: 10px;
  line-height: 1.5;
}

.strategy-params {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}
.param-chip {
  font-size: 12px;
  background: #1e293b;
  color: #cbd5e1;
  padding: 2px 8px;
  border-radius: 4px;
}

.strategy-actions {
  display: flex;
  gap: 8px;
}
.btn-primary {
  background: #3b82f6;
  color: white;
  border: none;
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 13px;
  text-decoration: none;
  display: inline-block;
}
.btn-ghost {
  background: transparent;
  color: #94a3b8;
  border: 1px solid #475569;
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
}
.btn-ghost.danger {
  color: #f87171;
  border-color: #7f1d1d;
}

.empty {
  text-align: center;
  color: #64748b;
  padding: 40px;
}
</style>
