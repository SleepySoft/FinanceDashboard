<template>
  <section class="arachne-card card">
    <div class="arachne-header">
      <div>
        <h3>🕸 产业链图谱</h3>
        <p>查看公司在产业链中的位置、上下游与相关公司</p>
      </div>
      <button class="ghost" @click="toggle">
        {{ open ? '收起' : '展开' }}
      </button>
    </div>

    <template v-if="open">
      <div v-if="loading" class="arachne-state">正在连接 Arachne…</div>
      <div v-else-if="error" class="arachne-state arachne-error">
        <span>{{ error }}</span>
        <button class="ghost" @click="load">重试</button>
      </div>
      <div v-else-if="result && !result.matched" class="arachne-state">
        Arachne 尚未收录 {{ name || code }}（{{ code }}）
      </div>
      <div v-else-if="result?.embed_url" class="arachne-frame-wrap">
        <iframe
          class="arachne-frame"
          :src="result.embed_url"
          :title="`${name || code} 产业链图谱`"
          loading="lazy"
          referrerpolicy="same-origin"
        ></iframe>
      </div>
    </template>
  </section>
</template>

<script setup>
import { ref, watch } from 'vue'
import api from '../api.js'

const props = defineProps({
  code: { type: String, required: true },
  name: { type: String, default: '' },
})

const open = ref(false)
const loading = ref(false)
const error = ref('')
const result = ref(null)

async function load() {
  loading.value = true
  error.value = ''
  try {
    result.value = await api.arachne.resolveStock(props.code, props.name)
  } catch (e) {
    error.value = e.message || '产业链服务暂不可用'
  } finally {
    loading.value = false
  }
}

function toggle() {
  open.value = !open.value
  if (open.value && !result.value && !loading.value) load()
}

watch(() => props.code, () => {
  open.value = false
  result.value = null
  error.value = ''
})
</script>

<style scoped>
.arachne-card { padding: 0; overflow: hidden; }
.arachne-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
}
.arachne-header h3 { margin: 0 0 3px; }
.arachne-header p { margin: 0; color: #94a3b8; font-size: 12px; }
.arachne-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 100px;
  padding: 20px;
  border-top: 1px solid #334155;
  color: #94a3b8;
  font-size: 13px;
}
.arachne-error { color: #fca5a5; }
.arachne-frame-wrap { border-top: 1px solid #334155; }
.arachne-frame { display: block; width: 100%; height: 620px; border: 0; background: #020617; }
@media (max-width: 640px) {
  .arachne-header { align-items: flex-start; }
  .arachne-frame { height: 520px; }
}
</style>
