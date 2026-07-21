<template>
  <div class="detail">
    <div class="back-bar">
      <button class="back-btn" @click="goBack">← 返回</button>
    </div>
    <StockPanel :code="code" />
  </div>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'
import StockPanel from '../components/StockPanel.vue'

const route = useRoute()
const router = useRouter()
const code = route.params.code

function goBack() {
  router.push('/')
}
</script>

<style scoped>
.detail {
  padding: 0 20px 20px;
}
.back-bar {
  position: sticky;
  top: 0;
  z-index: 10;
  background: #0f172a;
  padding: 16px 0 10px;
  margin-bottom: 4px;
}
.back-btn {
  background: transparent; border: 1px solid #334155; color: #94a3b8;
  padding: 6px 14px; border-radius: 6px; font-size: 13px; cursor: pointer;
}
.back-btn:hover { color: #e2e8f0; border-color: #475569; }
@media (max-width: 640px) {
  .detail { padding: 0 12px 12px; }
  .back-bar { padding: 14px 0 8px; }
}
</style>
