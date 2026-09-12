<template>
  <div v-if="show" class="modal-overlay stock-modal-overlay" @click.self="close">
    <div class="modal-content stock-modal" :class="{ mobile: isMobile }">
      <div class="modal-header">
        <div class="modal-title-row">
          <span class="modal-code">{{ stock.code }}</span>
          <span class="modal-name">{{ stock.name }}</span>
          <span v-if="stock.sector" class="modal-sector">· {{ stock.sector }}</span>
        </div>
        <button class="modal-close" @click="close">✕</button>
      </div>
      <div ref="modalBody" class="modal-body" @scroll.passive="queueScrollSave">
        <StockPanel :code="stock.code" embedded :readonly="!canWrite" @loaded="restoreScroll" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import StockPanel from './StockPanel.vue'
import auth from '../composables/useAuth.js'
import { readState, writeState } from '../composables/useSession.js'

const props = defineProps({
  show: Boolean,
  stock: { type: Object, default: () => ({}) }
})
const emit = defineEmits(['close'])

const isMobile = computed(() => window.innerWidth <= 768)
const canWrite = auth.canWrite
const modalBody = ref(null)
let scrollSaveTimer = null

function scrollKey() {
  return `stock:modalScroll:${props.stock?.code}`
}

function saveScroll() {
  if (props.show && props.stock?.code && modalBody.value) {
    writeState(scrollKey(), modalBody.value.scrollTop)
  }
}

function queueScrollSave() {
  if (scrollSaveTimer) return
  scrollSaveTimer = setTimeout(() => {
    scrollSaveTimer = null
    saveScroll()
  }, 200)
}

function restoreScroll() {
  nextTick(() => {
    const saved = props.stock?.code ? readState(scrollKey(), 0) : 0
    if (modalBody.value && saved > 0) modalBody.value.scrollTop = saved
  })
}

function onVisibilityChange() {
  if (document.visibilityState === 'hidden') saveScroll()
}

watch(() => [props.show, props.stock?.code], ([show]) => {
  document.body.classList.toggle('stock-modal-open', show)
  if (show) restoreScroll()
}, { immediate: true })

onMounted(() => {
  document.addEventListener('visibilitychange', onVisibilityChange)
  window.addEventListener('pagehide', saveScroll)
})

onUnmounted(() => {
  document.body.classList.remove('stock-modal-open')
  document.removeEventListener('visibilitychange', onVisibilityChange)
  window.removeEventListener('pagehide', saveScroll)
  if (scrollSaveTimer) clearTimeout(scrollSaveTimer)
})

function close() {
  saveScroll()
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
.stock-modal-overlay {
  z-index: 1000;
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

@media (max-width: 768px) {
  .stock-modal-overlay {
    align-items: stretch;
    padding: 0;
  }
  .stock-modal.modal-content {
    width: 100%;
    max-width: 100%;
    height: 100vh;
    height: 100dvh;
    max-height: 100vh;
    max-height: 100dvh;
    border: 0;
    border-radius: 0;
  }
  .stock-modal.modal-content .modal-header {
    padding: max(10px, env(safe-area-inset-top)) 12px 10px;
  }
  .stock-modal.modal-content .modal-body {
    padding: 10px max(10px, env(safe-area-inset-right)) calc(12px + env(safe-area-inset-bottom)) max(10px, env(safe-area-inset-left));
    overscroll-behavior: contain;
  }
}
</style>
