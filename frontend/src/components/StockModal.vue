<template>
  <div v-if="show" class="modal-overlay" @click.self="close">
    <div class="modal-content" :class="{ mobile: isMobile }">
      <div class="modal-header">
        <div class="modal-title-row">
          <span class="modal-code">{{ stock.code }}</span>
          <span class="modal-name">{{ stock.name }}</span>
          <span v-if="stock.sector" class="modal-sector">· {{ stock.sector }}</span>
        </div>
        <button class="modal-close" @click="close">✕</button>
      </div>
      <div class="modal-body">
        <StockPanel :code="stock.code" embedded readonly />
        <div class="modal-footer">
          <router-link :to="'/stock/' + stock.code" class="btn-primary" @click="close">
            进入完整页面 →
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import StockPanel from './StockPanel.vue'

const props = defineProps({
  show: Boolean,
  stock: { type: Object, default: () => ({}) }
})
const emit = defineEmits(['close'])

const isMobile = computed(() => window.innerWidth <= 768)

function close() {
  emit('close')
}
</script>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(0,0,0,0.7);
  display: flex; justify-content: center; align-items: center;
  padding: 16px;
}
.modal-content {
  background: #0f172a; border: 1px solid #334155; border-radius: 12px;
  width: 100%; max-width: 760px; max-height: 92vh;
  display: flex; flex-direction: column;
  overflow: hidden;
  box-sizing: border-box;
  min-width: 0;
}
.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 18px; border-bottom: 1px solid #334155;
  flex-shrink: 0;
}
.modal-title-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.modal-code { font-size: 14px; font-weight: 600; color: #60a5fa; }
.modal-name { font-size: 16px; font-weight: 600; color: #e2e8f0; }
.modal-sector { font-size: 12px; color: #64748b; }
.modal-close {
  background: transparent; color: #94a3b8; border: none;
  font-size: 20px; padding: 4px 8px; cursor: pointer;
}
.modal-close:hover { color: #e2e8f0; }
.modal-body {
  padding: 14px 18px;
  overflow-y: auto;
  overflow-x: hidden;
  flex: 1;
  min-width: 0;
}
.modal-footer { text-align: center; padding: 14px 0 4px; border-top: 1px solid #334155; margin-top: 12px; }
.btn-primary {
  display: inline-block;
  padding: 8px 20px;
  background: #1e3a5f;
  color: #60a5fa;
  border-radius: 6px;
  text-decoration: none;
  font-size: 13px;
  font-weight: 500;
}
.btn-primary:hover { background: #2563eb; color: white; }

@media (max-width: 640px) {
  .modal-overlay { padding: 0; }
  .modal-content { border-radius: 0; max-height: 100vh; max-width: 100vw; }
  .modal-body { padding: 10px 12px; }
  .modal-header { padding: 12px 14px; }
}
</style>
