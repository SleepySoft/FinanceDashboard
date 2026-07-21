<template>
  <div class="detail">
    <StockPanel :code="code" />
  </div>
</template>

<script setup>
import { useRoute } from 'vue-router'
import StockPanel from '../components/StockPanel.vue'

const route = useRoute()
const code = route.params.code
</script>

<style scoped>
.detail { padding: 20px; }
@media (max-width: 640px) {
  .detail { padding: 12px; }
}
</style>
