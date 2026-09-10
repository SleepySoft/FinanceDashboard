import { computed } from 'vue'
import auth from './useAuth.js'

/**
 * 股票分类标签（投资状态）全局配置（单例）。
 * 数据源：GET /api/auth/config 返回的 status_categories（在「设置」页维护，
 * 支持改名/新增/删除/拖动排序），配置缺失时回退到默认列表。
 *
 * 内置兜底分类 NONE_KEY（无分类）：不可删除、不出现在状态选择下拉中；
 * 删除有股票的分类时，后端把这些股票的 status 改写为 NONE_KEY；
 * 看板仅当其中有股票时才显示该分组（未知/残留状态同样归入此组）。
 */
export const NONE_KEY = 'none'
export const NONE_LABEL = '无分类'

const DEFAULT_CATEGORIES = [
  { key: 'unassessed', label: '未分析' },
  { key: 'tracking', label: '跟踪中' },
  { key: 'bullish', label: '看好' },
  { key: 'neutral', label: '观望' },
  { key: 'waiting', label: '伺机' },
  { key: 'core_position', label: '底仓备选' },
  { key: 'avoid', label: '回避' },
  { key: 'no_interest', label: '无兴趣' },
  { key: 'archive', label: '归档' },
  { key: 'blacklist', label: '黑名单' },
]

// 有专属徽章配色的 key；自定义 key 统一用 status-custom
const KNOWN_BADGE_KEYS = new Set(DEFAULT_CATEGORIES.map(c => c.key))

const categories = computed(() => {
  const raw = auth.config.value.status_categories
  return Array.isArray(raw) ? raw : DEFAULT_CATEGORIES
})

const categoryKeys = computed(() => new Set(categories.value.map(c => c.key)))

function statusLabel(key) {
  const hit = categories.value.find(c => c.key === key)
  return hit ? hit.label : NONE_LABEL
}

function statusBadgeClass(key) {
  return KNOWN_BADGE_KEYS.has(key) ? `status-${key}` : 'status-custom'
}

function statusDesc(key) {
  const hit = categories.value.find(c => c.key === key)
  return hit && typeof hit.desc === 'string' ? hit.desc : ''
}

export default {
  categories,
  categoryKeys,
  statusLabel,
  statusBadgeClass,
  statusDesc,
  NONE_KEY,
  NONE_LABEL,
}
