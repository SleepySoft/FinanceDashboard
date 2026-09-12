<template>
  <div class="stock-panel">
    <div v-if="loadError" class="card empty">
      数据加载失败：{{ loadError }}
      <button class="ghost" @click="load">重试</button>
    </div>
    <!-- Header -->
    <div v-if="!embedded" class="panel-header card">
      <div class="title-row compact">
        <div class="header-main">
          <span class="header-code">{{ meta.code }}</span>
          <span class="header-name">{{ meta.name }}</span>
          <span v-if="meta.sector" class="header-sector">· {{ meta.sector }}</span>
          <span v-if="lastViewedInfo" :class="['lv-tag', { stale: lastViewedInfo.stale }]" :title="lastViewedInfo.full">👁 上次浏览 {{ lastViewedInfo.text }}</span>
          <span :class="['dim-badge-sm', 'dim-' + dim('quality')]">质</span>
          <span :class="['dim-badge-sm', 'dim-' + dim('valuation')]">估</span>
          <span :class="['dim-badge-sm', 'dim-' + dim('timing')]">时</span>
          <span :class="['dim-badge-sm', 'dim-' + dim('risk')]">险</span>
        </div>
        <div v-if="providerOptions.length" class="provider-jump">
          <select v-model="selectedProvider" class="pj-select" title="选择数据网站">
            <option v-for="l in providerOptions" :key="l.id" :value="l.id">{{ l.icon }} {{ l.name }}</option>
          </select>
          <a v-if="selectedLink" class="pj-open" :href="selectedLink.url" target="_blank" rel="noopener">跳转 ↗</a>
          <button v-if="!readonly && selectedLink && selectedProvider !== providerDefault" class="pj-set" @click="setDefaultProvider" title="设为默认跳转网站">★</button>
        </div>
        <div v-if="!readonly" class="actions">
          <select v-model="statusForm.status" @change="updateStatus" title="投资状态">
            <option v-if="statusUnknown" :value="statusForm.status" disabled>{{ statusLabel(statusForm.status) }}</option>
            <option v-for="c in statusCategories" :key="c.key" :value="c.key">{{ c.label }}</option>
          </select>
          <button :class="['tag-toggle', { active: tagForm.watchlist }]" @click="toggleWatchlist">
            {{ tagForm.watchlist ? '已关注' : '关注' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Info Bar (for embedded mode) -->
    <div v-else class="info-bar card">
      <div class="info-main">
        <span class="info-price" :class="priceClass(meta.change_pct)">
          {{ meta.last_price != null ? '¥' + meta.last_price.toFixed(2) : '--' }}
        </span>
        <span v-if="meta.change_pct != null" class="info-pct" :class="priceClass(meta.change_pct)">
          {{ meta.change_pct > 0 ? '+' : '' }}{{ meta.change_pct.toFixed(2) }}%
        </span>
        <span :class="['status-tag', statusBadgeClass(meta.status || 'unassessed')]" :title="statusCats.statusDesc(meta.status || 'unassessed')">
          {{ statusLabel(meta.status) }}
        </span>
        <span v-if="meta.tags?.watchlist" class="watch-tag">已关注</span>
        <span v-if="lastViewedInfo" :class="['lv-tag', { stale: lastViewedInfo.stale }]" :title="lastViewedInfo.full">👁 上次浏览 {{ lastViewedInfo.text }}</span>
      </div>
      <div class="info-dims">
        <span :class="['dim-badge', 'dim-' + dim('quality')]">质</span>
        <span :class="['dim-badge', 'dim-' + dim('valuation')]">估</span>
        <span :class="['dim-badge', 'dim-' + dim('timing')]">时</span>
        <span :class="['dim-badge', 'dim-' + dim('risk')]">险</span>
        <span :class="['verdict-badge', 'verdict-' + (meta.dimensions?.verdict || meta.overall)]">
          {{ verdictLabel }}
        </span>
      </div>
      <div v-if="!readonly" class="actions">
        <select v-model="statusForm.status" @change="updateStatus" title="投资状态">
          <option v-if="statusUnknown" :value="statusForm.status" disabled>{{ statusLabel(statusForm.status) }}</option>
          <option v-for="c in statusCategories" :key="c.key" :value="c.key">{{ c.label }}</option>
        </select>
        <button :class="['tag-toggle', { active: tagForm.watchlist }]" @click="toggleWatchlist">
          {{ tagForm.watchlist ? '已关注' : '关注' }}
        </button>
      </div>
      <div v-if="providerOptions.length" class="provider-jump">
        <select v-model="selectedProvider" class="pj-select" title="选择数据网站">
          <option v-for="l in providerOptions" :key="l.id" :value="l.id">{{ l.icon }} {{ l.name }}</option>
        </select>
        <a v-if="selectedLink" class="pj-open" :href="selectedLink.url" target="_blank" rel="noopener">跳转 ↗</a>
        <button v-if="!readonly && selectedLink && selectedProvider !== providerDefault" class="pj-set" @click="setDefaultProvider" title="设为默认跳转网站">★</button>
      </div>
    </div>

    <!-- 统一时间线 -->
    <div class="card" style="padding: 0; overflow: visible">
      <div class="analysis-header" style="padding: 14px 16px">
        <div class="analysis-title">
          <span class="analysis-icon">📋</span>
          <div>
            <h3>记录时间线</h3>
            <p class="analysis-status">笔记 · 报告 · 标记</p>
          </div>
        </div>
        <div class="header-right">
          <button v-if="!readonly" class="primary" @click.stop="analyze('fundamental')" :disabled="analyzing.fundamental">
            {{ analyzing.fundamental ? '分析中...' : '基本面' }}
          </button>
          <button v-if="!readonly" class="primary" @click.stop="analyze('technical')" :disabled="analyzing.technical" style="margin-left: 6px">
            {{ analyzing.technical ? '分析中...' : '技术面' }}
          </button>
        </div>
      </div>

      <!-- 笔记输入框 -->
      <div v-if="!readonly" class="timeline-note-input">
        <textarea
          v-model="newNote"
          rows="3"
          placeholder="记录你的想法… 支持多行，Ctrl+Enter 快速保存"
          @keydown.ctrl.enter="addNote"
        ></textarea>
        <div class="note-input-footer">
          <span class="note-char-count">{{ newNote.trim() ? newNote.length + ' 字' : '' }}</span>
          <button class="primary" @click="addNote" :disabled="!newNote.trim()">保存笔记</button>
        </div>
      </div>

      <!-- 时间线列表 -->
      <div v-if="timelineItems.length > 0" class="report-timeline">
        <div
          v-for="(item, idx) in timelineItems"
          :key="item.key"
          :class="['timeline-item', { expanded: expandedTimelineId === item.key }]"
        >
          <div class="timeline-line" v-if="idx < timelineItems.length - 1"></div>
          <div class="timeline-dot" :class="item.type"></div>
          <div class="timeline-header-row" :class="{ clickable: isItemExpandable(item) }" @click="onTimelineItemClick(item)">
            <span :class="['timeline-badge', item.type]">{{ item.badge }}</span>
            <span class="timeline-time">{{ item.timeStr }}</span>
            <span :class="['timeline-latest', { placeholder: idx !== 0 }]">{{ idx === 0 ? '最新' : '' }}</span>
            <span class="timeline-record-price">{{ formatRecordPrice(item.price) }}</span>
            <!-- 笔记/标记的摘要 -->
            <span v-if="item.kind === 'note'" class="timeline-preview">{{ item.preview }}</span>
            <span v-if="item.kind === 'mark'" class="timeline-preview mark-preview">
              {{ item.raw.label }} ¥{{ item.raw.price?.toFixed(2) }}
            </span>
            <span class="timeline-row-actions">
              <span v-if="isItemExpandable(item)" class="timeline-expand-icon">{{ expandedTimelineId === item.key ? '▼' : '▶' }}</span>
              <button v-if="!readonly && item.kind === 'report'" class="btn-delete" @click.stop="confirmDelete(item.raw)" title="删除">🗑</button>
              <button v-if="!readonly && item.kind === 'note'" class="btn-delete" @click.stop="deleteNote(item.raw)" title="删除笔记">🗑</button>
            </span>
          </div>

          <!-- 展开内容 -->
          <div v-show="expandedTimelineId === item.key" class="timeline-content">
            <!-- 报告内容 -->
            <div v-if="item.kind === 'report'" v-html="renderMarkdown(reportContents[item.raw.id] || '加载中...')"></div>
            <!-- 笔记内容 -->
            <div v-if="item.kind === 'note'" class="timeline-note-body">{{ item.raw.content }}</div>
            <!-- 标记内容 -->
            <div v-if="item.kind === 'mark'" class="timeline-mark-body">
              <span :class="['mark-label', 'mark-' + item.raw.type]">{{ item.raw.label }}</span>
              <span class="mark-price">¥{{ item.raw.price.toFixed(2) }}</span>
              <span v-if="meta.last_price != null" :class="['mark-diff', diffClass(meta.last_price - item.raw.price)]">
                {{ meta.last_price >= item.raw.price ? '+' : '' }}{{ (meta.last_price - item.raw.price).toFixed(2) }}
              </span>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="empty" style="padding: 20px">暂无记录</div>
    </div>

    <!-- 股友反馈（登录即可参与，含只读账号；POW 防刷屏） -->
    <div class="card">
      <div class="section-header">
        <h3>🗳 股友反馈</h3>
        <button v-if="isAdmin && feedback.entries.length" class="fb-clear" @click="clearFeedback" title="删除全部反馈">清空</button>
        <span v-if="!commentsAdminOnly || isAdmin" class="fb-tally">
          <span class="fb-up">👍 {{ feedback.up }}</span>
          <span class="fb-down">👎 {{ feedback.down }}</span>
        </span>
      </div>
      <p v-if="commentsAdminOnly && !isAdmin" class="fb-login-tip">
        评论仅管理员可见；你仍可提交，并更新或撤回自己的反馈。
      </p>
      <div v-else-if="feedback.entries.length" class="fb-list">
        <div v-for="v in feedback.entries" :key="v.username" class="fb-entry">
          <div class="fb-entry-head">
            <span class="fb-vote-tag">{{ v.vote === 'up' ? '👍' : '👎' }}</span>
            <span class="fb-user">{{ feedbackUserName(v.username) }}</span>
            <span class="fb-time">{{ fmtFbTime(v.updated_at) }}</span>
            <button v-if="isAdmin" class="fb-del" @click="removeFeedback(v.username)" title="删除该反馈">🗑</button>
          </div>
          <div v-if="v.comment" class="fb-comment">{{ v.comment }}</div>
        </div>
      </div>
      <div v-else class="fb-empty">还没有人反馈过</div>

      <div v-if="canSubmitFeedback" class="fb-form">
        <div class="fb-vote-row">
          <button :class="['fb-vote-btn', { active: fbVote === 'up' }]" @click="fbVote = 'up'">👍 赞同</button>
          <button :class="['fb-vote-btn', 'down', { active: fbVote === 'down' }]" @click="fbVote = 'down'">👎 反对</button>
          <button v-if="feedback.my_vote" class="fb-withdraw" @click="withdrawFeedback" :disabled="fbSubmitting">撤回我的反馈</button>
        </div>
        <textarea v-model="fbComment" class="fb-input" rows="2" maxlength="500" placeholder="评论（可选，≤500 字）"></textarea>
        <PowPanel v-if="fbPowVisible" ref="fbPowPanel" scope="feedback" />
        <div class="fb-actions">
          <button class="primary" @click="submitFeedback" :disabled="fbSubmitting || !fbPowPanel?.powReady">
            {{ fbSubmitting ? '验证并提交中...' : (feedback.my_vote ? '更新我的反馈' : '提交反馈') }}
          </button>
        </div>
        <p v-if="fbError" class="fb-error">{{ fbError }}</p>
        <p v-if="!isAuthenticated" class="fb-login-tip">
          未登录反馈绑定当前浏览器身份，可更新和撤回。
        </p>
      </div>
      <div v-else class="fb-login-tip">登录后可投票和评论</div>
    </div>

    <!-- 价格阶梯：买入/卖出计划价位，临近/触及提醒（来源：手动/策略/AI） -->
    <div class="card">
      <div class="section-header">
        <h3>🎚 价格阶梯</h3>
        <span v-if="ladder.strategy" class="ld-strategy-tag" :title="`策略参数：${JSON.stringify(ladder.strategy.params)}`">
          {{ ladder.strategy.type === 'grid' ? '网格策略' : ladder.strategy.type }}
        </span>
      </div>
      <template v-if="ladder.levels.length">
        <div class="ld-list">
          <div v-for="lv in ladderSellLevels" :key="lv.id"
               :class="['ld-row', 'ld-sell', 'ld-st-' + lv.state]"
               :title="lv.note || ''">
            <span class="ld-side">卖出</span>
            <span class="ld-price">¥{{ lv.price.toFixed(2) }}</span>
            <span class="ld-diff">{{ fmtLadderDiff(lv) }}</span>
            <span v-if="lv.qty" class="ld-qty">{{ lv.qty }}股</span>
            <span :class="['ld-src', 'ld-src-' + lv.source]">{{ ladderSourceLabel(lv.source) }}</span>
            <span v-if="lv.note" class="ld-note">{{ lv.note }}</span>
            <span class="ld-state">{{ ladderStateLabel(lv) }}</span>
            <span v-if="!readonly && lv.source === 'manual'" class="ld-ops">
              <button class="ld-op" @click="startEditLevel(lv)" title="编辑">✎</button>
              <button class="ld-op" @click="removeLevel(lv)" title="删除">🗑</button>
            </span>
          </div>
          <div class="ld-current">
            <span class="ld-side">现价</span>
            <span class="ld-price">{{ ladder.current_price ? '¥' + ladder.current_price.toFixed(2) : '--' }}</span>
            <span class="ld-time">{{ fmtLadderTime(ladder.price_updated) }}</span>
          </div>
          <div v-for="lv in ladderBuyLevels" :key="lv.id"
               :class="['ld-row', 'ld-buy', 'ld-st-' + lv.state]"
               :title="lv.note || ''">
            <span class="ld-side">买入</span>
            <span class="ld-price">¥{{ lv.price.toFixed(2) }}</span>
            <span class="ld-diff">{{ fmtLadderDiff(lv) }}</span>
            <span v-if="lv.qty" class="ld-qty">{{ lv.qty }}股</span>
            <span :class="['ld-src', 'ld-src-' + lv.source]">{{ ladderSourceLabel(lv.source) }}</span>
            <span v-if="lv.note" class="ld-note">{{ lv.note }}</span>
            <span class="ld-state">{{ ladderStateLabel(lv) }}</span>
            <span v-if="!readonly && lv.source === 'manual'" class="ld-ops">
              <button class="ld-op" @click="startEditLevel(lv)" title="编辑">✎</button>
              <button class="ld-op" @click="removeLevel(lv)" title="删除">🗑</button>
            </span>
          </div>
        </div>
      </template>
      <div v-else class="ld-empty">还没有价格阶梯 — 可手动添加、用网格策略生成，或让 AI 计算压力位/支撑位后填入</div>

      <div v-if="!readonly" class="ld-edit">
        <div class="ld-form-row">
          <select v-model="ldForm.side" class="ld-input ld-side-sel">
            <option value="buy">买入</option>
            <option value="sell">卖出</option>
          </select>
          <input v-model.number="ldForm.price" class="ld-input" type="number" step="0.01" min="0" placeholder="价格" />
          <input v-model.number="ldForm.qty" class="ld-input" type="number" step="100" min="0" placeholder="数量(可空)" />
          <input v-model="ldForm.note" class="ld-input ld-note-input" maxlength="100" placeholder="备注(可空)" />
          <button class="primary" @click="saveLevel" :disabled="ldSaving || !ldForm.price">
            {{ ldEditingId ? '保存' : '添加' }}
          </button>
          <button v-if="ldEditingId" @click="cancelEditLevel">取消</button>
        </div>
        <div class="ld-form-row">
          <span class="ld-grid-label">网格：</span>
          <input v-model.number="ldGrid.base_price" class="ld-input" type="number" step="0.01" min="0"
                 :placeholder="ladder.current_price ? `基准(默认${ladder.current_price.toFixed(2)})` : '基准价'" />
          <input v-model.number="ldGrid.step_pct" class="ld-input ld-sm" type="number" step="0.5" min="0.1" max="50" placeholder="步长%" />
          <input v-model.number="ldGrid.up" class="ld-input ld-sm" type="number" step="1" min="0" max="20" placeholder="上档" />
          <input v-model.number="ldGrid.down" class="ld-input ld-sm" type="number" step="1" min="0" max="20" placeholder="下档" />
          <button @click="applyGrid" :disabled="ldSaving">{{ ladder.strategy ? '重算网格' : '生成网格' }}</button>
          <button v-if="ladder.strategy" @click="clearStrategyLevels" :disabled="ldSaving">清除策略档</button>
          <button v-if="ladderHasAgent" @click="clearAgentLevels" :disabled="ldSaving">清除 AI 档</button>
        </div>
        <p v-if="ldError" class="ld-error">{{ ldError }}</p>
      </div>
    </div>

    <!-- Delete Confirm Modal -->
    <div v-if="showDeleteConfirm" class="modal-overlay" @click="showDeleteConfirm = false">
      <div class="confirm-box" @click.stop>
        <p>确认删除 {{ reportToDelete?.created_at }} 的{{ reportTypeLabel(reportToDelete?.type) }}报告？</p>
        <p class="confirm-warning">此操作不可恢复</p>
        <div class="confirm-actions">
          <button class="btn-cancel" @click="showDeleteConfirm = false">取消</button>
          <button class="btn-danger" @click="doDelete">删除</button>
        </div>
      </div>
    </div>

    <!-- Price Marks -->
    <div class="card">
      <div class="section-header">
        <h3>📌 价格标记</h3>
      </div>
      <div class="price-marks">
        <div v-for="m in meta.price_marks" :key="m.id" class="price-mark">
          <span :class="['mark-label', 'mark-' + m.type]">{{ m.label }}</span>
          <span class="mark-price">¥{{ m.price.toFixed(2) }}</span>
          <span v-if="meta.last_price != null" :class="['mark-diff', diffClass(meta.last_price - m.price)]">
            {{ meta.last_price >= m.price ? '+' : '' }}{{ (meta.last_price - m.price).toFixed(2) }}
            ({{ ((meta.last_price - m.price) / m.price * 100).toFixed(1) }}%)
          </span>
          <button v-if="!readonly" class="ghost" style="padding:2px 8px;font-size:12px" @click.stop="removeMark(m.id)">×</button>
        </div>
      </div>
      <div v-if="meta.price_marks?.length === 0" class="empty" style="margin-bottom:12px">暂无价格标记</div>
      <div v-if="!readonly" class="add-mark">
        <div class="preset-labels">
          <span class="preset-label" @click="newMark.label = '目标买入'; newMark.type = 'target_buy'">目标买入</span>
          <span class="preset-label" @click="newMark.label = '止损'; newMark.type = 'stop_loss'">止损</span>
          <span class="preset-label" @click="newMark.label = '止盈'; newMark.type = 'take_profit'">止盈</span>
          <span class="preset-label" @click="newMark.label = '加仓'; newMark.type = 'add'">加仓</span>
          <span class="preset-label" @click="newMark.label = '减仓'; newMark.type = 'reduce'">减仓</span>
          <span class="preset-label" @click="newMark.label = '标记'; newMark.type = 'mark'">标记</span>
          <span class="preset-label preset-trade" @click="fillLastTrade('buy')">最后买入</span>
          <span class="preset-label preset-trade" @click="fillLastTrade('sell')">最后卖出</span>
        </div>
        <div class="add-mark-row">
          <input v-model="newMark.label" placeholder="标签（可自定义）" style="flex:1" />
          <div class="price-input-group">
            <button class="ghost price-shortcut" @click="fillPrice(-0.1)">-10%</button>
            <button class="ghost price-shortcut" @click="fillPrice(0)">当前</button>
            <button class="ghost price-shortcut" @click="fillPrice(0.1)">+10%</button>
            <input v-model.number="newMark.price" placeholder="价格" type="number" step="0.01" style="width:100px" />
          </div>
          <button class="primary" @click="addMark" :disabled="!newMark.label || !newMark.price">添加</button>
        </div>
      </div>
    </div>

    <!-- Holdings -->
    <div class="card holdings-card">
      <div class="holdings-header" @click="showHoldings = !showHoldings">
        <div class="holdings-title">
          <span class="holdings-icon">📦</span>
          <div>
            <h3>持仓记录</h3>
            <p v-if="holdingsData.summary" class="holdings-count">
              {{ holdingsData.summary.total_quantity }}股 @ ¥{{ holdingsData.summary.avg_cost.toFixed(2) }}
              <span v-if="holdingsData.summary.realized_pnl > 0" class="t-profit">已落袋 +{{ holdingsData.summary.realized_pnl.toFixed(0) }}</span>
            </p>
            <p v-else class="holdings-count">暂无持仓记录</p>
          </div>
        </div>
        <span class="collapse-btn">{{ showHoldings ? '▼' : '▶' }}</span>
      </div>
      <div v-show="showHoldings" class="holdings-content">
        <div v-if="holdingsData.trades?.length > 0">
          <!-- Summary -->
          <div v-if="holdingsData.summary" class="holdings-summary">
            <div class="hs-row">
              <span class="hs-label">持仓</span>
              <span class="hs-value">{{ holdingsData.summary.total_quantity }}股 @ ¥{{ holdingsData.summary.avg_cost.toFixed(2) }}</span>
            </div>
            <div class="hs-row">
              <span class="hs-label">市值</span>
              <span class="hs-value">¥{{ ((meta.last_price || 0) * holdingsData.summary.total_quantity).toFixed(0) }}</span>
              <span v-if="holdingsData.summary.total_quantity > 0 && meta.last_price" :class="['hs-pnl', meta.last_price >= holdingsData.summary.avg_cost ? 'up' : 'down']">
                {{ meta.last_price >= holdingsData.summary.avg_cost ? '+' : '' }}{{ ((meta.last_price - holdingsData.summary.avg_cost) * holdingsData.summary.total_quantity).toFixed(0) }}
                ({{ (((meta.last_price - holdingsData.summary.avg_cost) / holdingsData.summary.avg_cost) * 100).toFixed(1) }}%)
              </span>
            </div>
            <div v-if="holdingsData.summary.realized_pnl > 0" class="hs-row">
              <span class="hs-label">已落袋</span>
              <span class="hs-value t-profit">+{{ holdingsData.summary.realized_pnl.toFixed(0) }}</span>
            </div>
          </div>
          <!-- Trades table -->
          <div class="trades-table-wrap">
            <table class="trades-table">
              <thead>
                <tr>
                  <th>日期</th>
                  <th>类型</th>
                  <th>价格</th>
                  <th>数量</th>
                  <th>手续费</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="t in holdingsData.trades" :key="t.id">
                  <td>{{ t.date }}</td>
                  <td :class="t.type === 'buy' ? 'up' : 'down'">{{ t.type === 'buy' ? '买入' : '卖出' }}</td>
                  <td>¥{{ t.price.toFixed(2) }}</td>
                  <td>{{ t.quantity }}</td>
                  <td>{{ t.fee?.toFixed(2) || '-' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <div v-else class="empty">暂无交易记录</div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api.js'
import { readState, writeState } from '../composables/useSession.js'
import statusCats from '../composables/useStatusCategories.js'
import auth from '../composables/useAuth.js'
import PowPanel from '../powbox/PowPanel.vue'

const props = defineProps({
  code: { type: String, required: true },
  embedded: { type: Boolean, default: false },
  readonly: { type: Boolean, default: false }
})
const emit = defineEmits(['loaded'])
const route = useRoute()
const router = useRouter()
// 独立详情页额外把展开项同步到 URL；弹窗只使用会话状态，避免覆盖看板 query。
const isStandalone = !props.embedded

const meta = ref({ cache: { fundamental: {}, technical: {} }, price_marks: [], reports: [] })
const notes = ref([])
const analyzing = ref({ fundamental: false, technical: false })
const loadError = ref('')

const fundamentalContent = ref('')
const technicalContent = ref('')
const fundVersionContent = ref('')
const techVersionContent = ref('')
const expandedReportId = ref(null)
const fundExpandedIndex = ref(-1)
const techExpandedIndex = ref(-1)


const tagForm = ref({ watchlist: false })
const statusForm = ref({ status: 'neutral' })

// 分类列表来自「设置」页配置（useStatusCategories）；当前 status 不在列表中时
// （如被删分类迁入的「无分类」），下拉额外显示一个禁用的当前项
const statusCategories = statusCats.categories
const statusBadgeClass = statusCats.statusBadgeClass
const statusUnknown = computed(() => !statusCats.categoryKeys.value.has(statusForm.value.status))

// 股友反馈（登录即可参与，含只读账号；每股每人一票，可改票；POW 防刷屏）
const isAuthenticated = auth.isAuthenticated
const isAdmin = auth.isAdmin
const commentsRequireLogin = computed(() => auth.config.value.comments_require_login ?? true)
const commentsAdminOnly = computed(() => (auth.config.value.comments_visibility ?? 'public') === 'admin')
const canSubmitFeedback = computed(() => auth.isAuthenticated.value || !commentsRequireLogin.value)
const feedback = ref({ up: 0, down: 0, entries: [], my_vote: null })
const fbVote = ref('up')
const fbComment = ref('')
const fbSubmitting = ref(false)
const fbError = ref('')
const fbPowVisible = ref(true)
const fbPowPanel = ref(null)

async function loadFeedback() {
  try {
    const fb = await api.feedback.get(props.code)
    feedback.value = fb && typeof fb === 'object' && Array.isArray(fb.entries)
      ? fb
      : { up: 0, down: 0, entries: [], my_vote: null }
    if (feedback.value.my_vote) {
      fbVote.value = feedback.value.my_vote.vote === 'down' ? 'down' : 'up'
      fbComment.value = feedback.value.my_vote.comment || ''
    }
  } catch {
    feedback.value = { up: 0, down: 0, entries: [], my_vote: null }
  }
}

function applyFeedback(res) {
  if (res && Array.isArray(res.entries)) {
    feedback.value = { up: res.up || 0, down: res.down || 0, entries: res.entries, my_vote: res.my_vote || null }
  } else {
    loadFeedback()
  }
}

async function submitFeedback() {
  fbError.value = ''
  fbSubmitting.value = true
  try {
    await nextTick() // 等 PowPanel 挂载后再取 ref
    const comment = fbComment.value.trim()
    // POW 绑定内容须与后端一致：code|vote|comment
    const bound = `${props.code}|${fbVote.value}|${comment}`
    const pow = await fbPowPanel.value.obtainPow(bound)
    const res = await api.feedback.submit(props.code, fbVote.value, comment, pow)
    applyFeedback(res)
  } catch (e) {
    if (e.message !== '已取消') fbError.value = e.message || '提交失败'
  } finally {
    fbSubmitting.value = false
  }
}

async function withdrawFeedback() {
  fbError.value = ''
  try {
    const res = await api.feedback.withdraw(props.code)
    applyFeedback(res)
    fbComment.value = ''
  } catch (e) {
    fbError.value = e.message || '撤回失败'
  }
}

async function removeFeedback(name) {
  if (!window.confirm(`删除「${name}」的反馈？`)) return
  try {
    const res = await api.feedback.remove(props.code, name)
    applyFeedback(res)
  } catch (e) {
    fbError.value = e.message || '删除失败'
  }
}

async function clearFeedback() {
  if (!window.confirm('删除这只股票的全部反馈？此操作不可恢复。')) return
  try {
    const res = await api.feedback.clearAll(props.code)
    applyFeedback(res)
  } catch (e) {
    fbError.value = e.message || '清空失败'
  }
}

function fmtFbTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleString()
}

function feedbackUserName(username) {
  if (typeof username === 'string' && username.startsWith('guest:')) {
    return `\u6e38\u5ba2\u00b7${username.slice(-4)}`
  }
  return username
}

// 价格阶梯：买入/卖出计划价位 + 临近/触及提醒；manual/strategy/agent 三来源分区管理
const ladder = ref({ current_price: null, price_updated: null, alert_threshold_pct: 2, strategy: null, levels: [] })
const ldForm = ref({ side: 'buy', price: null, qty: null, note: '' })
const ldGrid = ref({ base_price: null, step_pct: 3, up: 3, down: 3 })
const ldEditingId = ref(null)
const ldSaving = ref(false)
const ldError = ref('')

const ladderSellLevels = computed(() => ladder.value.levels.filter(l => l.side === 'sell'))
const ladderBuyLevels = computed(() => ladder.value.levels.filter(l => l.side === 'buy'))
const ladderHasAgent = computed(() => ladder.value.levels.some(l => l.source === 'agent'))

// 最后浏览时间：展示的是「上次」打开的时间（本次打开会在加载后记录）；超过阈值闪烁
const staleViewDays = computed(() => auth.config.value?.stale_view_days ?? 7)
const lastViewedInfo = computed(() => {
  if (!auth.isAdmin.value) return null
  const ts = meta.value.last_viewed
  if (!ts) return null
  const t = new Date(ts)
  if (Number.isNaN(t.getTime())) return null
  const diffMs = Date.now() - t.getTime()
  const days = diffMs / 86400000
  const text = days >= 1 ? `${Math.floor(days)}天前` : diffMs >= 3600000 ? `${Math.floor(diffMs / 3600000)}小时前` : '刚刚'
  return { text, stale: staleViewDays.value > 0 && days > staleViewDays.value, full: t.toLocaleString() }
})

async function loadLadder() {
  try {
    const d = await api.ladder.get(props.code)
    ladder.value = d && typeof d === 'object' && Array.isArray(d.levels)
      ? d
      : { current_price: null, price_updated: null, alert_threshold_pct: 2, strategy: null, levels: [] }
  } catch {
    ladder.value = { current_price: null, price_updated: null, alert_threshold_pct: 2, strategy: null, levels: [] }
  }
}

function ladderSourceLabel(s) {
  return { manual: '手动', strategy: '策略', agent: 'AI' }[s] || s
}

function ladderStateLabel(lv) {
  return { triggered: '⚡ 触及', near: '临近', disabled: '已停用' }[lv.state] || ''
}

function fmtLadderDiff(lv) {
  if (lv.diff_pct === null || lv.diff_pct === undefined) return '--'
  return (lv.diff_pct > 0 ? '+' : '') + lv.diff_pct.toFixed(1) + '%'
}

function fmtLadderTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleString()
}

function applyLadder(res) {
  if (res && typeof res === 'object' && Array.isArray(res.levels)) ladder.value = res
}

async function saveLevel() {
  ldError.value = ''
  if (!ldForm.value.price || ldForm.value.price <= 0) {
    ldError.value = '请填写有效的价格'
    return
  }
  ldSaving.value = true
  try {
    const body = {
      side: ldForm.value.side,
      price: ldForm.value.price,
      qty: ldForm.value.qty || null,
      note: (ldForm.value.note || '').trim(),
    }
    const res = ldEditingId.value
      ? await api.ladder.updateLevel(props.code, ldEditingId.value, body)
      : await api.ladder.addLevel(props.code, body)
    applyLadder(res)
    cancelEditLevel()
  } catch (e) {
    ldError.value = e.message || '保存失败'
  } finally {
    ldSaving.value = false
  }
}

function startEditLevel(lv) {
  ldEditingId.value = lv.id
  ldForm.value = { side: lv.side, price: lv.price, qty: lv.qty, note: lv.note || '' }
}

function cancelEditLevel() {
  ldEditingId.value = null
  ldForm.value = { side: 'buy', price: null, qty: null, note: '' }
}

async function removeLevel(lv) {
  if (!window.confirm(`删除 ${lv.side === 'buy' ? '买入' : '卖出'}档 ¥${lv.price.toFixed(2)}？`)) return
  ldError.value = ''
  try {
    applyLadder(await api.ladder.deleteLevel(props.code, lv.id))
  } catch (e) {
    ldError.value = e.message || '删除失败'
  }
}

async function applyGrid() {
  ldError.value = ''
  if (ladder.value.strategy && !window.confirm('重算将替换现有策略档位（手动/AI 档不受影响），继续？')) return
  ldSaving.value = true
  try {
    const params = {
      base_price: ldGrid.value.base_price || null,
      step_pct: ldGrid.value.step_pct || 3,
      up: ldGrid.value.up ?? 3,
      down: ldGrid.value.down ?? 3,
    }
    applyLadder(await api.ladder.applyStrategy(props.code, 'grid', params))
  } catch (e) {
    ldError.value = e.message || '生成失败'
  } finally {
    ldSaving.value = false
  }
}

async function clearStrategyLevels() {
  if (!window.confirm('清除策略生成的所有档位？')) return
  ldError.value = ''
  try {
    applyLadder(await api.ladder.clearStrategy(props.code))
  } catch (e) {
    ldError.value = e.message || '清除失败'
  }
}

async function clearAgentLevels() {
  if (!window.confirm('清除 AI 填入的所有档位？')) return
  ldError.value = ''
  try {
    applyLadder(await api.ladder.clearAgent(props.code))
  } catch (e) {
    ldError.value = e.message || '清除失败'
  }
}
const newMark = ref({ label: '', price: null, type: 'mark' })
const newNote = ref('')

const holdingsData = ref({ trades: [], summary: null })
const showHoldings = ref(false)

const providerLinks = ref([])
const providerDefault = ref('')
const selectedProvider = ref('')

const providerOptions = computed(() => {
  const seen = new Set()
  const out = []
  for (const l of providerLinks.value) {
    if (seen.has(l.id)) continue
    seen.add(l.id)
    out.push(l)
  }
  return out
})
const selectedLink = computed(() => providerOptions.value.find(l => l.id === selectedProvider.value) || null)

async function loadProviders() {
  try {
    const res = await api.providers.links(props.code)
    providerLinks.value = res.links || []
    providerDefault.value = res.default_provider || ''
    selectedProvider.value = providerDefault.value || ''
  } catch {
    providerLinks.value = []
  }
}

async function setDefaultProvider() {
  if (!selectedProvider.value) return
  try {
    const res = await api.providers.setDefault(selectedProvider.value)
    providerDefault.value = res.default_provider
  } catch {
    // error toast already shown by api.js
  }
}

const fundamentalReports = computed(() =>
  (meta.value.reports || [])
    .filter(r => r.type === 'fundamental' || r.type === 'full')
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
)

const technicalReports = computed(() =>
  (meta.value.reports || [])
    .filter(r => r.type === 'technical' || r.type === 'full')
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
)

const fundamentalStatus = computed(() => {
  const c = meta.value.cache?.fundamental
  if (!c?.last) return '未分析'
  return c.expired ? `已过期（${fmtDate(c.last)}）` : `有效（${fmtDate(c.last)}）`
})

const technicalStatus = computed(() => {
  const c = meta.value.cache?.technical
  if (!c?.last) return '未分析'
  return c.expired ? `已过期（${fmtDate(c.last)}）` : `有效（${fmtDate(c.last)}）`
})

const verdictLabel = computed(() => {
  const v = meta.value.dimensions?.verdict || meta.value.overall
  const map = { green: '看好', yellow: '观望', red: '回避', none: '-' }
  return map[v] || '-'
})

function dim(key) {
  const dims = meta.value.dimensions || meta.value.tags || {}
  return dims[key] || 'none'
}

function priceClass(pct) {
  if (pct == null) return ''
  return pct >= 0 ? 'up' : 'down'
}

function diffClass(diff) {
  return diff >= 0 ? 'up' : 'down'
}

function formatRecordPrice(price) {
  const value = Number(price)
  return Number.isFinite(value) && value > 0 ? `¥${value.toFixed(2)}` : '--'
}

function statusLabel(status) {
  return statusCats.statusLabel(status)
}

async function load() {
  loadError.value = ''
  let data
  try {
    data = await api.stocks.get(props.code)
    if (!data || Array.isArray(data) || typeof data !== 'object') {
      throw new Error('股票详情响应格式错误')
    }
  } catch (error) {
    loadError.value = error.message || '无法加载股票详情'
    emit('loaded')
    return
  }
  meta.value = data
  await loadProviders()
  tagForm.value = { watchlist: data.tags?.watchlist || false }
  statusForm.value = { status: data.status || 'neutral' }
  // 用户打开面板即视为已读：清除未读标记（只读模式下不发起写请求）
  if (!props.readonly && data.tags?.unread) {
    meta.value.tags.unread = false
    api.stocks.updateTags(props.code, { unread: false }).catch(() => {})
  }
  // 记录最后浏览时间（仅管理员；只读账号与匿名只读不记录）
  if (auth.isAdmin.value) {
    api.stocks.markViewed(props.code).catch(() => {})
  }
  try {
    const noteData = await api.stocks.getNotes(props.code)
    notes.value = Array.isArray(noteData?.notes) ? noteData.notes : []
  } catch {
    notes.value = []
  }
  // Load holdings
  try {
    const h = await api.holdings.get(props.code)
    if (h.has_data) {
      holdingsData.value.summary = h.summary
    }
    const t = await api.holdings.getTrades(props.code)
    holdingsData.value.trades = t.trades || []
  } catch (e) {
    holdingsData.value = { trades: [], summary: null }
  }
  await loadFeedback()
  await loadLadder()
  await loadLatestFundamental()
  await loadLatestTechnical()
  emit('loaded')
}

// Timeline report functions
const showDeleteConfirm = ref(false)
const reportToDelete = ref(null)
const reportContents = ref({})

const allReports = computed(() =>
  (meta.value.reports || [])
    .slice().sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
)

// 统一时间线：笔记 + 报告 + 标记
const timelineItems = computed(() => {
  const items = []

  // 笔记
  notes.value.forEach(n => {
    const d = new Date(n.time.replace(' ', 'T'))
    items.push({
      key: 'note-' + n.time,
      kind: 'note',
      type: 'note',
      badge: '💭 笔记',
      time: d,
      timeStr: n.time,
      raw: n,
      price: n.price,
      preview: n.content.length > 60 ? n.content.slice(0, 60) + '…' : n.content
    })
  })

  // 报告
  allReports.value.forEach(r => {
    const d = new Date(r.created_at)
    items.push({
      key: 'report-' + r.id,
      kind: 'report',
      type: reportTypeClass(r.type),
      badge: '📊 ' + reportTypeLabel(r.type),
      time: d,
      timeStr: fmtDateTime(r.created_at),
      price: r.price,
      raw: r
    })
  })

  // 价格标记
  ;(meta.value.price_marks || []).forEach(m => {
    const d = new Date(m.created_at || Date.now())
    items.push({
      key: 'mark-' + m.id,
      kind: 'mark',
      type: 'mark',
      badge: '📌 标记',
      time: d,
      timeStr: fmtDateTime(m.created_at),
      price: null,
      raw: m
    })
  })

  return items.sort((a, b) => b.time - a.time)
})

const expandedTimelineId = ref(null)

function toggleTimelineItem(item) {
  if (expandedTimelineId.value === item.key) {
    expandedTimelineId.value = null
    return
  }
  expandedTimelineId.value = item.key
  if (item.kind === 'report' && !reportContents.value[item.raw.id]) {
    loadReportContent(item.raw)
  }
}

async function loadReportContent(r) {
  try {
    const data = await api.stocks.getReport(props.code, r.id)
    reportContents.value[r.id] = data.content
  } catch (e) {
    reportContents.value[r.id] = '加载失败'
  }
}

function confirmDelete(r) {
  reportToDelete.value = r
  showDeleteConfirm.value = true
}

async function doDelete() {
  if (!reportToDelete.value) return
  try {
    await api.stocks.deleteReport(props.code, reportToDelete.value.id)
    meta.value.reports = (meta.value.reports || []).filter(x => x.id !== reportToDelete.value.id)
    delete reportContents.value[reportToDelete.value.id]
    if (expandedReportId.value === reportToDelete.value.id) {
      expandedReportId.value = null
    }
  } catch (e) {
    alert('删除失败: ' + e.message)
  } finally {
    showDeleteConfirm.value = false
    reportToDelete.value = null
  }
}

function reportTypeLabel(type) {
  const map = { fundamental: '基本面', technical: '技术面', full: '综合' }
  return map[type] || type
}

function reportTypeClass(type) {
  const map = { fundamental: 'badge-fund', technical: 'badge-tech', full: 'badge-full' }
  return map[type] || 'badge-full'
}

async function loadLatestFundamental() {
  const reps = fundamentalReports.value
  if (reps.length === 0) { fundamentalContent.value = ''; return }
  try {
    const data = await api.stocks.getReport(props.code, reps[0].id)
    fundamentalContent.value = data.content
  } catch (e) { fundamentalContent.value = '' }
}

async function loadLatestTechnical() {
  const reps = technicalReports.value
  if (reps.length === 0) { technicalContent.value = ''; return }
  try {
    const data = await api.stocks.getReport(props.code, reps[0].id)
    technicalContent.value = data.content
  } catch (e) { technicalContent.value = '' }
}

async function toggleFundVersion(idx) {
  if (fundExpandedIndex.value === idx) { fundExpandedIndex.value = -1; return }
  fundExpandedIndex.value = idx
  const reps = fundamentalReports.value
  if (idx >= reps.length) return
  try {
    const data = await api.stocks.getReport(props.code, reps[idx].id)
    fundVersionContent.value = data.content
  } catch (e) { fundVersionContent.value = '加载失败' }
}

async function toggleTechVersion(idx) {
  if (techExpandedIndex.value === idx) { techExpandedIndex.value = -1; return }
  techExpandedIndex.value = idx
  const reps = technicalReports.value
  if (idx >= reps.length) return
  try {
    const data = await api.stocks.getReport(props.code, reps[idx].id)
    techVersionContent.value = data.content
  } catch (e) { techVersionContent.value = '加载失败' }
}

async function updateStatus() {
  await api.stocks.updateStatus(props.code, statusForm.value.status)
}

async function toggleWatchlist() {
  const newVal = !tagForm.value.watchlist
  tagForm.value.watchlist = newVal
  await api.stocks.updateTags(props.code, { watchlist: newVal })
}

async function analyze(type) {
  analyzing.value[type] = true
  try {
    const task = await api.requests.submit(props.code, meta.value.name, meta.value.sector, '', type)
    const poll = setInterval(async () => {
      const tasks = await api.agent.tasks()
      const t = tasks.find(x => x.id === task.id)
      if (!t || t.status === 'completed' || t.status === 'failed') {
        clearInterval(poll)
        analyzing.value[type] = false
        await load()
      }
    }, 3000)
  } catch (e) {
    analyzing.value[type] = false
    alert('提交分析请求失败: ' + e.message)
  }
}

async function addMark() {
  await api.stocks.addPriceMark(props.code, newMark.value)
  newMark.value = { label: '', price: null, type: 'mark' }
  await load()
}

async function removeMark(id) {
  await api.stocks.deletePriceMark(props.code, id)
  await load()
}

async function addNote() {
  if (!newNote.value.trim()) return
  try {
    await api.stocks.addNote(props.code, newNote.value)
    newNote.value = ''
    await load()
  } catch (e) {
    alert('保存失败: ' + e.message)
  }
}

async function deleteNote(note) {
  if (!confirm(`删除这条笔记？\n\n${note.content.slice(0, 50)}${note.content.length > 50 ? '…' : ''}`)) return
  try {
    await api.stocks.deleteNote(props.code, note.time)
    notes.value = notes.value.filter(n => n.time !== note.time)
  } catch (e) {
    alert('删除失败: ' + e.message)
  }
}

// 报告总是可展开；笔记仅长文（预览被截断）时可展开
function isItemExpandable(item) {
  if (item.kind === 'report') return true
  if (item.kind === 'note') return item.raw.content.length > 60
  return false
}

function onTimelineItemClick(item) {
  if (item.kind === 'report') { toggleTimelineItem(item); return }
  if (item.kind === 'note' && isItemExpandable(item)) {
    expandedTimelineId.value = expandedTimelineId.value === item.key ? null : item.key
  }
}

function renderMarkdown(md) {
  if (!md) return ''
  return md
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/^\|(.+)\|$/gim, (match) => {
      const cells = match.split('|').filter(c => c.trim()).map(c => `<td>${c.trim()}</td>`).join('')
      return `<tr>${cells}</tr>`
    })
    .replace(/(<tr>.*<\/tr>\n?)+/g, '<table style="border-collapse:collapse;margin:10px 0;width:100%">$&</table>')
    .replace(/\n/g, '<br>')
}

function fillPrice(offset) {
  const base = newMark.value.price || meta.value.last_price
  if (base == null) return
  newMark.value.price = Number((base * (1 + offset)).toFixed(2))
}

// 最后买入/最后卖出：从持仓交易记录取价自动填充；无记录则提示录入
function fillLastTrade(kind) {
  const summary = holdingsData.value?.summary
  const price = kind === 'buy' ? summary?.last_buy_price : summary?.last_sell_price
  const label = kind === 'buy' ? '最后买入' : '最后卖出'
  if (price == null) {
    alert(`暂无${label}记录，请先在「持仓」中录入交易后再试`)
    return
  }
  newMark.value = { label, price, type: kind === 'buy' ? 'last_buy' : 'last_sell' }
}

function fmtDate(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
}

function fmtDateTime(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}

// ---- 会话恢复：草稿/展开状态/滚动位置，防止手机切后台刷新后丢失 ----
function panelKey(name) {
  return `panel:${name}:${props.code}`
}

function restorePanelState() {
  newNote.value = readState(panelKey('note'), '')
  newMark.value = readState(panelKey('mark'), { label: '', price: null, type: 'mark' })
  const urlOpen = isStandalone && typeof route.query.open === 'string' ? route.query.open : ''
  const savedExpanded = readState(panelKey('expanded'), null)
  expandedTimelineId.value = urlOpen || savedExpanded
  if (expandedTimelineId.value && expandedTimelineId.value.startsWith('report-')) {
    const id = expandedTimelineId.value.slice('report-'.length)
    if (!reportContents.value[id]) loadReportContent({ id })
  }
  showHoldings.value = readState(panelKey('holdings'), false)
}

function persistPanelState() {
  writeState(panelKey('note'), newNote.value)
  writeState(panelKey('mark'), newMark.value)
  writeState(panelKey('expanded'), expandedTimelineId.value)
  writeState(panelKey('holdings'), showHoldings.value)
}

watch([newNote, newMark, expandedTimelineId, showHoldings], persistPanelState, { deep: true })
if (isStandalone) {
  // 阅读位置写入 URL（?open=...），刷新/分享后可直达同一条目
  watch(expandedTimelineId, (v) => {
    router.replace({ query: v ? { open: v } : {} })
  })
}

function handleCodeChange() {
  restorePanelState()
  load()
}

watch(() => props.code, handleCodeChange)
onMounted(handleCodeChange)
</script>

<style scoped>
.stock-panel { display: flex; flex-direction: column; gap: 12px; }

/* Header */
.panel-header { margin-bottom: 0; }
.title-row { display: flex; justify-content: space-between; align-items: center; }
.title-row.compact { align-items: center; margin-bottom: 0; }

.header-main { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.header-code { font-size: 15px; font-weight: 600; color: #60a5fa; }
.header-name { font-size: 16px; font-weight: 600; color: #e2e8f0; }
.header-sector { font-size: 12px; color: #64748b; }

.dim-badge-sm { display: inline-block; padding: 1px 5px; border-radius: 3px; font-size: 11px; font-weight: 600; }
.dim-green { background: #064e3b; color: #34d399; }
.dim-yellow { background: #713f12; color: #fbbf24; }
.dim-red { background: #7f1d1d; color: #f87171; }
.dim-none { background: #334155; color: #64748b; }

.actions { display: flex; gap: 10px; align-items: center; }
.provider-jump { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.pj-select {
  padding: 5px 8px;
  border-radius: 6px;
  border: 1px solid #334155;
  background: #1e293b;
  color: #e2e8f0;
  font-size: 12px;
  max-width: 150px;
}
.pj-open {
  padding: 5px 10px;
  border-radius: 6px;
  border: 1px solid #334155;
  color: #93c5fd;
  font-size: 12px;
  text-decoration: none;
  white-space: nowrap;
}
.pj-open:hover { background: #1e293b; border-color: #475569; color: white; }
.pj-set {
  background: transparent;
  border: 1px solid #475569;
  color: #fbbf24;
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 12px;
  cursor: pointer;
}
.pj-set:hover { background: #713f12; }
.tag-toggle { padding: 6px 14px; border-radius: 6px; border: 1px solid #475569; background: transparent; color: #94a3b8; font-size: 13px; cursor: pointer; }
.tag-toggle.active { background: #fbbf24; color: #1e293b; border-color: #fbbf24; }

/* Info bar (embedded) */
.info-bar { display: flex; justify-content: space-between; align-items: center; padding: 12px 14px; gap: 10px; flex-wrap: wrap; }
.info-main { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.info-price { font-size: 24px; font-weight: 700; }
.info-pct { font-size: 13px; font-weight: 500; }
.status-tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }
.status-tracking { background: #1e3a5f; color: #60a5fa; }
.status-bullish { background: #064e3b; color: #34d399; }
.status-neutral { background: #713f12; color: #fbbf24; }
.status-avoid { background: #7f1d1d; color: #f87171; }
.status-no_interest { background: #334155; color: #94a3b8; }
.status-blacklist { background: #000000; color: #f87171; }
.status-waiting { background: #3d2c12; color: #fbbf24; }
.status-archive { background: #334155; color: #94a3b8; }
.status-custom { background: #334155; color: #cbd5e1; }

/* ── 股友反馈 ── */
.fb-tally { margin-left: auto; display: flex; gap: 10px; font-size: 13px; }
.fb-up { color: #4ade80; }
.fb-down { color: #f87171; }
.fb-list { margin-bottom: 10px; }
.fb-entry { padding: 8px 0; border-bottom: 1px dashed #334155; }
.fb-entry:last-child { border-bottom: none; }
.fb-entry-head { display: flex; align-items: center; gap: 8px; }
.fb-user { color: #60a5fa; font-size: 13px; font-weight: 600; }
.fb-time { color: #64748b; font-size: 12px; }
.fb-del { margin-left: auto; background: none; border: none; cursor: pointer; opacity: 0.6; }
.fb-del:hover { opacity: 1; }
.fb-clear {
  margin-left: auto; padding: 2px 8px; border: 1px solid #475569; border-radius: 5px;
  background: transparent; color: #94a3b8; cursor: pointer; font-size: 11px;
}
.fb-clear:hover { color: #f87171; border-color: #f87171; }
.fb-comment { color: #cbd5e1; font-size: 13px; margin-top: 4px; white-space: pre-wrap; line-height: 1.5; }
.fb-empty { color: #64748b; font-size: 13px; padding: 6px 0 10px; }
.fb-form { margin-top: 8px; border-top: 1px solid #334155; padding-top: 10px; }
.fb-vote-row { display: flex; gap: 8px; margin-bottom: 8px; align-items: center; }
.fb-vote-btn {
  padding: 5px 14px; border: 1px solid #334155; border-radius: 6px;
  background: transparent; color: #94a3b8; cursor: pointer; font-size: 13px;
}
.fb-vote-btn.active { border-color: #3b82f6; color: #60a5fa; background: rgba(59, 130, 246, 0.1); }
.fb-vote-btn.down.active { border-color: #ef4444; color: #f87171; background: rgba(239, 68, 68, 0.1); }
.fb-withdraw { margin-left: auto; background: none; border: none; color: #64748b; cursor: pointer; font-size: 12px; }
.fb-withdraw:hover { color: #f87171; }
.fb-input {
  width: 100%; box-sizing: border-box; background: #0f172a; border: 1px solid #334155;
  border-radius: 8px; color: #e2e8f0; padding: 8px 10px; font-size: 13px; resize: vertical;
}
.fb-actions { margin-top: 8px; display: flex; justify-content: flex-end; }
.fb-error { color: #f87171; font-size: 12px; margin-top: 6px; }
.fb-login-tip { color: #64748b; font-size: 12px; margin-top: 8px; }
.watch-tag { display: inline-block; padding: 1px 6px; border-radius: 4px; background: #fbbf24; color: #1e293b; font-size: 10px; font-weight: 600; }
.info-dims { display: flex; gap: 4px; flex-wrap: wrap; }
.dim-badge { display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.verdict-badge { display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.verdict-green { background: #064e3b; color: #34d399; }
.verdict-yellow { background: #713f12; color: #fbbf24; }
.verdict-red { background: #7f1d1d; color: #f87171; }
.verdict-none { background: #334155; color: #64748b; }
.info-bar .provider-jump { margin-left: auto; }

/* Analysis */
.analysis-grid { display: flex; flex-direction: column; gap: 12px; }
.analysis-card h3 { font-size: 16px; margin-bottom: 2px; }
.analysis-header { display: flex; justify-content: space-between; align-items: center; cursor: pointer; padding-bottom: 14px; transition: background 0.15s; }
.analysis-header:hover { background: #1e293b; }
.analysis-title { display: flex; align-items: center; gap: 12px; pointer-events: none; }
.analysis-icon { font-size: 24px; }
.analysis-status { font-size: 12px; color: #64748b; margin-top: 2px; }
.analysis-status.expired { color: #f87171; }
.analysis-content { min-height: 40px; }
.empty { color: #475569; font-size: 13px; padding: 12px 0; text-align: center; }

.header-right { display: flex; align-items: center; gap: 10px; pointer-events: auto; }
.collapse-btn { font-size: 14px; color: #64748b; cursor: pointer; padding: 4px; min-width: 20px; text-align: center; }
.collapse-btn:hover { color: #e2e8f0; }

/* Report */
.report-latest { margin-bottom: 16px; }
.report-badge-row { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
.report-time { font-size: 12px; color: #94a3b8; }
.report-body { line-height: 1.8; font-size: 14px; }
.report-body h1 { font-size: 18px; font-weight: 700; margin: 16px 0 10px; color: #e2e8f0; }
.report-body h2 { font-size: 15px; font-weight: 600; margin: 14px 0 8px; color: #94a3b8; border-bottom: 1px solid #334155; padding-bottom: 4px; }
.report-body h3 { font-size: 13px; font-weight: 600; margin: 10px 0 6px; color: #60a5fa; }
.report-body strong { color: #e2e8f0; }
.report-body table { width: 100%; margin: 10px 0; font-size: 12px; }
.report-body td { padding: 5px 8px; border: 1px solid #334155; }
.report-body tr:first-child td { background: #1e293b; font-weight: 600; }

.older-versions { border-top: 1px solid #334155; padding-top: 12px; }
.older-toggle { display: flex; align-items: center; gap: 8px; padding: 8px 12px; background: #0f172a; border-radius: 6px; cursor: pointer; font-size: 13px; color: #94a3b8; transition: background 0.15s; }
.older-toggle:hover { background: #1e293b; }
.timeline-collapsed { margin-top: 10px; }
.timeline-collapsed-item { margin-bottom: 8px; }
.tci-header { display: flex; align-items: center; gap: 10px; padding: 8px 12px; background: #0f172a; border: 1px solid #334155; border-radius: 6px; cursor: pointer; font-size: 13px; transition: all 0.15s; }
.tci-header:hover { background: #1e293b; border-color: #475569; }
.tci-dot { width: 8px; height: 8px; border-radius: 50%; background: #475569; flex-shrink: 0; }
.tci-time { color: #94a3b8; }
.tci-body { padding: 12px; border: 1px solid #334155; border-top: none; border-radius: 0 0 6px 6px; font-size: 14px; line-height: 1.8; }

.timeline-badge { font-size: 11px; padding: 1px 4px; border-radius: 4px; font-weight: 500; text-align: center; white-space: nowrap; }
.badge-fund { background: #1e3a5f; color: #60a5fa; }
.badge-tech { background: #3f2c1d; color: #fbbf24; }
.badge-full { background: #14532d; color: #34d399; }
.timeline-latest { font-size: 11px; padding: 1px 4px; border-radius: 4px; background: #3b82f6; color: white; font-weight: 500; text-align: center; }
.timeline-latest.placeholder { visibility: hidden; }

/* Report Timeline - new unified view */
.report-timeline { position: relative; padding-left: 6px; }
.report-timeline::before {
  content: '';
  position: absolute;
  left: 2px;
  top: 6px;
  bottom: 6px;
  width: 1px;
  background: #334155;
}
.timeline-item { position: relative; margin-bottom: 6px; }
.timeline-item:last-child { margin-bottom: 0; }
.timeline-item.expanded .timeline-header-row { background: #1e293b; border-color: #475569; }
.timeline-line {
  position: absolute;
  left: -4px;
  top: 14px;
  bottom: -6px;
  width: 1px;
  background: #334155;
}
.timeline-dot {
  position: absolute;
  left: -7px;
  top: 6px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #475569;
  border: 1.5px solid #0f172a;
  z-index: 1;
}
.timeline-dot.badge-fund { background: #60a5fa; }
.timeline-dot.badge-tech { background: #fbbf24; }
.timeline-dot.badge-full { background: #34d399; }
.timeline-header-row {
  display: grid;
  grid-template-columns: 64px 128px 38px 78px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  padding: 8px 10px 8px 6px;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.15s;
}
.timeline-header-row:hover { background: #1e293b; border-color: #475569; }
.timeline-time { color: #94a3b8; font-size: 12px; }
.timeline-record-price { color: #e2e8f0; font-size: 12px; font-variant-numeric: tabular-nums; text-align: right; white-space: nowrap; }
.timeline-row-actions { display: flex; align-items: center; justify-content: flex-end; gap: 3px; min-width: 18px; }
.timeline-expand-icon { color: #64748b; font-size: 11px; }
.btn-delete {
  background: transparent;
  border: none;
  color: #64748b;
  cursor: pointer;
  font-size: 13px;
  padding: 2px 4px;
  border-radius: 4px;
  opacity: 1;
  transition: opacity 0.15s;
}
.timeline-header-row:hover .btn-delete { opacity: 1; }
.btn-delete:hover { color: #f87171; background: #7f1d1d; }
.timeline-content {
  padding: 10px 10px 10px 12px;
  border: 1px solid #334155;
  border-top: none;
  border-radius: 0 0 6px 6px;
  font-size: 14px;
  line-height: 1.8;
}

/* 笔记输入区 */
.timeline-note-input { padding: 0 16px 14px; }
.timeline-note-input textarea {
  width: 100%;
  resize: vertical;
  min-height: 64px;
  line-height: 1.6;
  border-radius: 8px;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.timeline-note-input textarea:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}
.note-input-footer { display: flex; justify-content: space-between; align-items: center; margin-top: 8px; }
.note-char-count { font-size: 12px; color: #475569; }

/* 笔记条目 */
.timeline-header-row.clickable { cursor: pointer; }
.timeline-header-row:not(.clickable) { cursor: default; }
.timeline-preview { color: #cbd5e1; font-size: 13px; line-height: 1.5; word-break: break-all; }
.timeline-note-body { white-space: pre-wrap; color: #e2e8f0; }

/* Delete confirm modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}
.confirm-box {
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 10px;
  padding: 20px 24px;
  max-width: 320px;
  width: 90%;
}
.confirm-box p { margin: 0 0 8px; font-size: 14px; color: #e2e8f0; }
.confirm-warning { font-size: 12px !important; color: #f87171 !important; }
.confirm-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 16px;
}
.btn-cancel {
  padding: 6px 14px;
  border-radius: 6px;
  border: 1px solid #475569;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  font-size: 13px;
}
.btn-danger {
  padding: 6px 14px;
  border-radius: 6px;
  border: none;
  background: #7f1d1d;
  color: #f87171;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
}
.btn-danger:hover { background: #991b1b; }

/* Price marks */
.price-marks { margin-bottom: 12px; }
.price-mark { display: flex; align-items: center; gap: 10px; padding: 6px 0; border-bottom: 1px solid #334155; flex-wrap: wrap; }
.price-mark:last-child { border-bottom: none; }
.mark-label { padding: 2px 10px; border-radius: 4px; font-size: 12px; font-weight: 500; }
.mark-target_buy { background: #064e3b; color: #34d399; }
.mark-stop_loss { background: #7f1d1d; color: #f87171; }
.mark-take_profit { background: #1e3a5f; color: #60a5fa; }
.mark-add { background: #064e3b; color: #34d399; }
.mark-reduce { background: #7f1d1d; color: #f87171; }
.mark-mark { background: #334155; color: #94a3b8; }
.mark-last_buy { background: #3b2f06; color: #fbbf24; }
.mark-last_sell { background: #312e81; color: #a5b4fc; }
.mark-price { font-size: 14px; font-weight: 600; }
.mark-diff { font-size: 12px; font-weight: 500; }
.up { color: #f87171; }
.down { color: #34d399; }

.section-header { margin-bottom: 12px; }
.section-header h3 { margin: 0; }

.preset-labels { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.preset-label { display: inline-block; padding: 4px 12px; border-radius: 6px; background: #1e293b; color: #94a3b8; font-size: 12px; cursor: pointer; border: 1px solid #334155; transition: all 0.15s; }
.preset-label:hover { background: #334155; color: #e2e8f0; }
.add-mark-row { display: flex; gap: 8px; align-items: center; }

.price-input-group { display: flex; align-items: center; gap: 4px; }
.price-shortcut { padding: 2px 6px; font-size: 12px; border-radius: 4px; }

/* Notes */
.notes-card { margin-top: 0; }
.note-input { display: flex; gap: 10px; margin-bottom: 16px; }
.note-input textarea { flex: 1; resize: vertical; }
.notes-list { max-height: 400px; overflow-y: auto; }
.note-item { padding: 12px 0; border-bottom: 1px solid #334155; }
.note-time { font-size: 12px; color: #64748b; margin-bottom: 4px; }
.note-content { font-size: 14px; line-height: 1.6; white-space: pre-wrap; }

/* Holdings */
.holdings-card { margin-top: 0; }
.holdings-header { display: flex; justify-content: space-between; align-items: center; cursor: pointer; padding-bottom: 14px; transition: background 0.15s; }
.holdings-header:hover { background: #1e293b; }
.holdings-title { display: flex; align-items: center; gap: 12px; pointer-events: none; }
.holdings-icon { font-size: 22px; }
.holdings-count { font-size: 12px; color: #64748b; margin-top: 2px; }
.holdings-content { padding-top: 4px; }
.holdings-summary { background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 10px 14px; margin-bottom: 12px; }
.hs-row { display: flex; align-items: center; gap: 10px; padding: 4px 0; flex-wrap: wrap; }
.hs-label { font-size: 12px; color: #94a3b8; min-width: 40px; }
.hs-value { font-size: 14px; font-weight: 600; color: #e2e8f0; }
.hs-pnl { font-size: 13px; font-weight: 600; }
.trades-table-wrap { overflow-x: auto; }
.trades-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.trades-table th { text-align: left; padding: 8px 10px; border-bottom: 1px solid #334155; color: #94a3b8; font-weight: 500; }
.trades-table td { padding: 8px 10px; border-bottom: 1px solid #1e293b; }
.trades-table tr:last-child td { border-bottom: none; }
.t-profit { color: #fbbf24; font-weight: 600; }

/* Mobile */
@media (max-width: 640px) {
  .add-mark { flex-direction: column; align-items: stretch; gap: 8px; }
  .preset-labels { flex-wrap: wrap; }
  .add-mark-row { flex-direction: column; }
  .add-mark-row input, .add-mark-row select, .add-mark-row button { width: 100% !important; }

  .title-row { flex-direction: column; gap: 10px; }
  .title-row.compact { flex-direction: column; align-items: stretch; }
  .header-main { gap: 6px; }
  .header-name { font-size: 15px; }
  .actions { flex-wrap: wrap; }
  .analysis-header { flex-direction: column; gap: 8px; align-items: stretch; padding-bottom: 12px; }
  .analysis-header button { width: 100%; }
  .header-right { width: 100%; justify-content: space-between; }

  .report-badge-row { gap: 6px; }
  .report-body { font-size: 13px; }
  .report-body h1 { font-size: 16px; }
  .report-body h2 { font-size: 14px; }
  .report-body table { font-size: 11px; }
  .report-body td { padding: 4px 6px; }

  .timeline-header-row { grid-template-columns: 54px 104px 30px 66px minmax(0, 1fr) auto; gap: 4px; }
  .timeline-time, .timeline-record-price { font-size: 11px; }
  .timeline-preview { grid-column: 1 / -1; }

  .older-toggle { padding: 10px; font-size: 12px; }
  .tci-header { padding: 10px; font-size: 12px; }
  .tci-body { font-size: 13px; padding: 10px; }

  .note-input { flex-direction: column; }
  .note-input button { width: 100%; }
  .notes-list { max-height: 300px; }
  .price-input-group { flex-wrap: wrap; justify-content: flex-end; }
  .price-shortcut { flex: 1; min-width: 50px; }

  .mark-diff { font-size: 11px; }

  .info-bar { padding: 10px 12px; }
  .info-price { font-size: 20px; }
}

/* ── 价格阶梯 ── */
.ld-strategy-tag { margin-left: auto; font-size: 11px; color: #a78bfa; border: 1px solid #4c1d95; border-radius: 4px; padding: 1px 7px; cursor: default; }
.ld-list { display: flex; flex-direction: column; gap: 4px; }
.ld-row {
  display: flex; align-items: center; gap: 8px; font-size: 13px;
  padding: 5px 10px; border-radius: 6px; background: #0f172a; border: 1px solid transparent;
}
.ld-sell .ld-side { color: #4ade80; }
.ld-buy .ld-side { color: #f87171; }
.ld-side { font-size: 12px; font-weight: 600; min-width: 28px; }
.ld-price { font-weight: 600; color: #e2e8f0; font-variant-numeric: tabular-nums; }
.ld-diff { color: #94a3b8; font-size: 12px; min-width: 52px; font-variant-numeric: tabular-nums; }
.ld-qty { color: #64748b; font-size: 12px; }
.ld-src { font-size: 10px; border-radius: 4px; padding: 0 5px; border: 1px solid #334155; color: #94a3b8; }
.ld-src-strategy { color: #a78bfa; border-color: #4c1d95; }
.ld-src-agent { color: #38bdf8; border-color: #075985; }
.ld-note { color: #64748b; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; min-width: 0; }
.ld-state { margin-left: auto; font-size: 11px; color: #64748b; }
.ld-ops { margin-left: auto; display: flex; gap: 2px; }
.ld-state + .ld-ops { margin-left: 0; }
.ld-op { background: none; border: none; cursor: pointer; opacity: 0.6; padding: 0 3px; font-size: 12px; }
.ld-op:hover { opacity: 1; }
.ld-st-near { border-color: #a16207; background: rgba(161, 98, 7, 0.12); }
.ld-st-near .ld-state { color: #fbbf24; }
.ld-st-triggered { border-color: #dc2626; background: rgba(220, 38, 38, 0.15); }
.ld-st-triggered .ld-state { color: #f87171; font-weight: 600; }
.ld-st-disabled { opacity: 0.45; }
.ld-current {
  display: flex; align-items: center; gap: 8px; font-size: 13px;
  padding: 6px 10px; border-radius: 6px; background: #1e293b; border: 1px solid #334155;
}
.ld-current .ld-side { color: #60a5fa; }
.ld-current .ld-price { color: #60a5fa; }
.ld-time { color: #64748b; font-size: 11px; margin-left: auto; }
.ld-empty { color: #64748b; font-size: 13px; padding: 6px 0 10px; }
.ld-edit { margin-top: 8px; border-top: 1px solid #334155; padding-top: 10px; }
.ld-form-row { display: flex; gap: 6px; margin-bottom: 8px; align-items: center; flex-wrap: wrap; }
.ld-input {
  background: #0f172a; border: 1px solid #334155; border-radius: 6px;
  color: #e2e8f0; padding: 6px 8px; font-size: 13px; width: 90px;
}
.ld-side-sel { width: 64px; }
.ld-note-input { flex: 1; min-width: 100px; }
.ld-sm { width: 60px; }
.ld-grid-label { color: #64748b; font-size: 12px; }
.ld-error { color: #f87171; font-size: 12px; margin: 4px 0 0; }

/* 最后浏览时间 */
.lv-tag { font-size: 11px; color: #64748b; }
.lv-tag.stale { color: #fbbf24; animation: lv-blink 1.2s ease-in-out infinite; }
@keyframes lv-blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.25; } }
</style>
