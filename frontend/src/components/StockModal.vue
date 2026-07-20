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
        <!-- Price row -->
        <div class="modal-price-row">
          <span class="modal-price" :class="priceClass(stock.change_pct)">
            {{ stock.last_price != null ? '¥' + stock.last_price.toFixed(2) : '--' }}
          </span>
          <span v-if="stock.change_pct != null" :class="priceClass(stock.change_pct)">
            {{ stock.change_pct > 0 ? '+' : '' }}{{ stock.change_pct.toFixed(2) }}%
          </span>
          <span class="modal-dims">
            <span :class="['dim-badge', 'dim-' + dim('quality')]">质</span>
            <span :class="['dim-badge', 'dim-' + dim('valuation')]">估</span>
            <span :class="['dim-badge', 'dim-' + dim('timing')]">时</span>
            <span :class="['dim-badge', 'dim-' + dim('risk')]">险</span>
          </span>
        </div>
        <!-- Price marks preview -->
        <div v-if="stock.price_marks?.length > 0" class="modal-marks">
          <div v-for="m in stock.price_marks" :key="m.id" class="modal-mark">
            <span :class="['mark-label', 'mark-' + m.type]">{{ m.label }}</span>
            <span>¥{{ m.price.toFixed(2) }}</span>
            <span v-if="m.diff != null" :class="['mark-diff', m.diff >= 0 ? 'up' : 'down']">
              {{ m.diff > 0 ? '+' : '' }}{{ m.diff.toFixed(2) }}
            </span>
          </div>
        </div>
        <!-- Link to full detail -->
        <div class="modal-footer">
          <router-link :to="'/stock/' + stock.code" class="modal-full-link">
            查看完整详情 →
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  show: Boolean,
  stock: { type: Object, default: () => ({}) }
})
const emit = defineEmits(['close'])

const isMobile = computed(() => window.innerWidth <= 768)

function close() {
  emit('close')
}

function priceClass(pct) {
  if (pct == null) return ''
  return pct >= 0 ? 'up' : 'down'
}

function dim(key) {
  const d = props.stock.dimensions || props.stock.tags || {}
  return d[key] || 'none'
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
  background: #151e2e; border: 1px solid #334155; border-radius: 12px;
  width: 100%; max-width: 480px; max-height: 80vh;
  display: flex; flex-direction: column;
  overflow: hidden;
}
.modal-content.mobile {
  max-width: 100%; max-height: 100%; border-radius: 0;
}
.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px; border-bottom: 1px solid #334155;
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
.modal-body { padding: 16px 20px; overflow-y: auto; }
.modal-price-row {
  display: flex; align-items: baseline; gap: 10px; margin-bottom: 12px; flex-wrap: wrap;
}
.modal-price { font-size: 28px; font-weight: 700; }
.modal-dims { display: flex; gap: 6px; margin-left: auto; }
.dim-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }
.dim-green { background: #064e3b; color: #34d399; }
.dim-yellow { background: #713f12; color: #fbbf24; }
.dim-red { background: #7f1d1d; color: #f87171; }
.dim-none { background: #334155; color: #64748b; }
.modal-marks { margin-bottom: 16px; }
.modal-mark { display: flex; align-items: center; gap: 10px; padding: 4px 0; font-size: 13px; }
.mark-label { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }
.mark-target_buy { background: #064e3b; color: #34d399; }
.mark-stop_loss { background: #7f1d1d; color: #f87171; }
.mark-take_profit { background: #1e3a5f; color: #60a5fa; }
.mark-add { background: #064e3b; color: #34d399; }
.mark-reduce { background: #7f1d1d; color: #f87171; }
.mark-mark { background: #334155; color: #94a3b8; }
.up { color: #f87171; }
.down { color: #34d399; }
.modal-footer { text-align: center; padding-top: 12px; border-top: 1px solid #334155; }
.modal-full-link {
  color: #60a5fa; text-decoration: none; font-size: 14px;
}
.modal-full-link:hover { color: #93c5fd; }
</style>
