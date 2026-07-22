<template>
  <div class="dashboard">
    <!-- Overlay when status menu is open -->
    <div v-if="statusMenuCode" class="status-overlay" @click="statusMenuCode = null"></div>

    <!-- Controls row: view tabs + filters + refresh -->
    <div class="dash-header">
      <div class="view-tabs mini">
        <button
          v-for="v in views"
          :key="v.key"
          :class="['tab', { active: viewMode === v.key }]"
          @click="viewMode = v.key"
        >
          {{ v.label }}
        </button>
      </div>
      <div class="toolbar-inline">
        <router-link to="/anomalies" class="anomaly-link">📡 异动雷达</router-link>
        <div class="group-tabs" v-if="viewMode === 'grouped'">
          <button
            v-for="gm in groupModes"
            :key="gm.key"
            :class="['group-tab', { active: groupMode === gm.key }]"
            @click="groupMode = gm.key"
          >
            {{ gm.label }}
          </button>
        </div>
        <label class="filter-check">
          <input type="checkbox" v-model="filterWatchlist" />
          仅关注
        </label>
        <label class="filter-check">
          <input type="checkbox" v-model="filterHoldings" />
          只看持仓
        </label>
        <button class="ghost" @click="refreshPrices" :disabled="loading">
          {{ loading ? '...' : '🔄' }}
        </button>
      </div>
    </div>

    <!-- Holdings Summary Bar -->
    <div v-if="holdingsSummary.count > 0" class="holdings-summary-bar">
      <span class="hs-label">📊 持仓</span>
      <span class="hs-item">{{ holdingsSummary.count }} 只</span>
      <span class="hs-item">市值 ¥{{ holdingsSummary.marketValue.toLocaleString('zh-CN', {minimumFractionDigits: 0, maximumFractionDigits: 0}) }}</span>
      <span class="hs-item">成本 ¥{{ holdingsSummary.cost.toLocaleString('zh-CN', {minimumFractionDigits: 0, maximumFractionDigits: 0}) }}</span>
      <span :class="['hs-item', 'hs-pnl', holdingsSummary.pnl >= 0 ? 'up' : 'down']">
        浮动 {{ holdingsSummary.pnl >= 0 ? '+' : '' }}¥{{ holdingsSummary.pnl.toLocaleString('zh-CN', {minimumFractionDigits: 0, maximumFractionDigits: 0}) }}
        ({{ holdingsSummary.pnlPct >= 0 ? '+' : '' }}{{ holdingsSummary.pnlPct.toFixed(2) }}%)
      </span>
      <span class="hs-item" style="color: #94a3b8;">|</span>
      <span class="hs-item t-profit">
        已落袋 +¥{{ holdingsSummary.realized.toLocaleString('zh-CN', {minimumFractionDigits: 0, maximumFractionDigits: 0}) }}
      </span>
      <span class="hs-item" style="color: #94a3b8;">|</span>
      <span :class="['hs-item', (holdingsSummary.pnl + holdingsSummary.realized) >= 0 ? 'up' : 'down']">
        合计 {{ (holdingsSummary.pnl + holdingsSummary.realized) >= 0 ? '+' : '' }}¥{{ (holdingsSummary.pnl + holdingsSummary.realized).toLocaleString('zh-CN', {minimumFractionDigits: 0, maximumFractionDigits: 0}) }}
      </span>
      <router-link to="/holdings" class="hs-link">📦 持仓管理 →</router-link>
    </div>

    <!-- Loading -->
    <div v-if="loading && stocks.length === 0" class="card empty">加载中...</div>

    <!-- VIEW 1: Grouped -->
    <template v-if="viewMode === 'grouped'">
      <!-- By Status -->
      <template v-if="groupMode === 'status'">
        <div v-for="group in statusGroups" :key="group.key" class="sector-group">
          <div class="sector-header" @click="toggleGroup('status-' + group.key)">
            <span :class="['tag-badge', 'tag-' + group.key]">{{ group.label }}</span>
            <span class="sector-count">{{ group.stocks.length }} 只</span>
            <span class="collapse-icon">{{ collapsedGroups.has('status-' + group.key) ? '▸' : '▾' }}</span>
          </div>
          <div v-show="!collapsedGroups.has('status-' + group.key)" class="stock-grid">
            <div
              v-for="s in group.stocks"
              :key="s.code"
              class="stock-card card"
              @click="openStock(s.code)"
            >
              <div class="stock-main">
                <div class="stock-title-row">
                  <span class="stock-code">{{ s.code }}</span>
                  <span class="stock-name">{{ s.name }}</span>
                  <span class="stock-sector">{{ s.sector }}</span>
                  <span v-if="s.watchlist" class="tag-badge tag-watch">关注</span>
                  <span :class="['status-badge', 'status-' + (s.status || 'neutral')]" @click.stop="toggleStatusMenu(s.code)">{{ statusShort(s.status) }}</span>
                  <button class="trade-btn" @click.stop="openTradeModal(s)" title="录入成交">记</button>
                  <div v-if="statusMenuCode === s.code" class="status-dropdown" @click.stop>
                    <div v-for="st in statusOptions" :key="st.key" :class="['status-option', { active: (s.status || 'neutral') === st.key }]" @click="setStatus(s, st.key)">{{ st.label }}</div>
                  </div>
                </div>
                <div class="stock-price-row">
                  <span class="price-current" :class="priceClass(s.change_pct)">
                    {{ s.last_price != null ? '¥' + s.last_price.toFixed(2) : '--' }}
                  </span>
                  <span v-if="s.change_pct != null" class="price-change" :class="priceClass(s.change_pct)">
                    {{ s.change_pct > 0 ? '+' : '' }}{{ s.change_pct.toFixed(2) }}%
                  </span>
                </div>
                <div class="stock-dims">
                  <span :class="['dim-badge', 'dim-' + dim(s, 'quality')]">质</span>
                  <span :class="['dim-badge', 'dim-' + dim(s, 'valuation')]">估</span>
                  <span :class="['dim-badge', 'dim-' + dim(s, 'timing')]">时</span>
                  <span :class="['dim-badge', 'dim-' + dim(s, 'risk')]">险</span>
                </div>
              </div>
              <div v-if="s.price_marks?.length > 0" class="marks-section">
                <div v-for="m in s.price_marks" :key="m.id" class="mark-row">
                  <span class="mark-label">{{ m.label }}</span>
                  <span class="mark-target">¥{{ m.price.toFixed(2) }}</span>
                  <span v-if="m.diff != null" :class="['mark-diff', m.diff >= 0 ? 'up' : 'down']">
                    {{ m.diff > 0 ? '+' : '' }}{{ m.diff.toFixed(2) }} ({{ m.diff_pct > 0 ? '+' : '' }}{{ m.diff_pct.toFixed(1) }}%)
                  </span>
                </div>
              </div>
              <!-- Holdings Summary -->
              <div v-if="holdingsMap[s.code]?.quantity > 0" class="holdings-section">
                <div class="holdings-row">
                  <span class="holdings-label">持仓</span>
                  <span class="holdings-value">{{ holdingsMap[s.code].quantity }}股 @ ¥{{ holdingsMap[s.code].avg_cost.toFixed(2) }}</span>
                  <span v-if="s.last_price" :class="['holdings-pnl', holdingsMap[s.code].avg_cost < s.last_price ? 'up' : 'down']">
                    {{ holdingsMap[s.code].avg_cost < s.last_price ? '+' : '' }}{{ ((s.last_price - holdingsMap[s.code].avg_cost) * holdingsMap[s.code].quantity).toFixed(0) }}
                  </span>
                </div>
                <div v-if="holdingsMap[s.code].realized_pnl > 0" class="holdings-row">
                  <span class="holdings-label">已落袋</span>
                  <span class="holdings-value t-profit">+{{ holdingsMap[s.code].realized_pnl.toFixed(0) }}</span>
                </div>
                <div v-if="holdingsMap[s.code].last_buy_price != null" class="holdings-row">
                  <span class="holdings-label">最后买</span>
                  <span class="holdings-value price-tag" @click="openTradeModal(s, 'buy', holdingsMap[s.code].last_buy_price)">¥{{ holdingsMap[s.code].last_buy_price.toFixed(2) }}</span>
                </div>
                <div v-if="holdingsMap[s.code].last_sell_price != null" class="holdings-row">
                  <span class="holdings-label">最后卖</span>
                  <span class="holdings-value price-tag" @click="openTradeModal(s, 'sell', holdingsMap[s.code].last_sell_price)">¥{{ holdingsMap[s.code].last_sell_price.toFixed(2) }}</span>
                </div>
              </div>
              <div class="stock-footer">
                <span>报告: {{ s.report_count }}</span>
                <span v-if="s.last_analysis" :class="{ expired: isExpired(s.last_analysis) }">
                  分析: {{ fmtDate(s.last_analysis) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- By Rating -->
      <template v-if="groupMode === 'rating'">
        <div v-for="group in ratingGroups" :key="group.key" class="sector-group">
          <div class="sector-header" @click="toggleGroup('rating-' + group.key)">
            <span :class="['tag-badge', 'tag-' + group.key]">{{ group.label }}</span>
            <span class="sector-count">{{ group.stocks.length }} 只</span>
            <span class="collapse-icon">{{ collapsedGroups.has('rating-' + group.key) ? '▸' : '▾' }}</span>
          </div>
          <div v-show="!collapsedGroups.has('rating-' + group.key)" class="stock-grid">
            <div
              v-for="s in group.stocks"
              :key="s.code"
              class="stock-card card"
              @click="openStock(s.code)"
            >
              <div class="stock-main">
                <div class="stock-title-row">
                  <span class="stock-code">{{ s.code }}</span>
                  <span class="stock-name">{{ s.name }}</span>
                  <span class="stock-sector">{{ s.sector }}</span>
                  <span v-if="s.watchlist" class="tag-badge tag-watch">关注</span>
                  <span :class="['status-badge', 'status-' + (s.status || 'neutral')]" @click.stop="toggleStatusMenu(s.code)">{{ statusShort(s.status) }}</span>
                  <button class="trade-btn" @click.stop="openTradeModal(s)" title="录入成交">记</button>
                  <div v-if="statusMenuCode === s.code" class="status-dropdown" @click.stop>
                    <div v-for="st in statusOptions" :key="st.key" :class="['status-option', { active: (s.status || 'neutral') === st.key }]" @click="setStatus(s, st.key)">{{ st.label }}</div>
                  </div>
                </div>
                <div class="stock-price-row">
                  <span class="price-current" :class="priceClass(s.change_pct)">
                    {{ s.last_price != null ? '¥' + s.last_price.toFixed(2) : '--' }}
                  </span>
                  <span v-if="s.change_pct != null" class="price-change" :class="priceClass(s.change_pct)">
                    {{ s.change_pct > 0 ? '+' : '' }}{{ s.change_pct.toFixed(2) }}%
                  </span>
                </div>
                <div class="stock-dims">
                  <span :class="['dim-badge', 'dim-' + dim(s, 'quality')]">质</span>
                  <span :class="['dim-badge', 'dim-' + dim(s, 'valuation')]">估</span>
                  <span :class="['dim-badge', 'dim-' + dim(s, 'timing')]">时</span>
                  <span :class="['dim-badge', 'dim-' + dim(s, 'risk')]">险</span>
                </div>
              </div>
              <div v-if="s.price_marks?.length > 0" class="marks-section">
                <div v-for="m in s.price_marks" :key="m.id" class="mark-row">
                  <span class="mark-label">{{ m.label }}</span>
                  <span class="mark-target">¥{{ m.price.toFixed(2) }}</span>
                  <span v-if="m.diff != null" :class="['mark-diff', m.diff >= 0 ? 'up' : 'down']">
                    {{ m.diff > 0 ? '+' : '' }}{{ m.diff.toFixed(2) }} ({{ m.diff_pct > 0 ? '+' : '' }}{{ m.diff_pct.toFixed(1) }}%)
                  </span>
                </div>
              </div>
              <!-- Holdings Summary -->
              <div v-if="holdingsMap[s.code]?.quantity > 0" class="holdings-section">
                <div class="holdings-row">
                  <span class="holdings-label">持仓</span>
                  <span class="holdings-value">{{ holdingsMap[s.code].quantity }}股 @ ¥{{ holdingsMap[s.code].avg_cost.toFixed(2) }}</span>
                  <span v-if="s.last_price" :class="['holdings-pnl', holdingsMap[s.code].avg_cost < s.last_price ? 'up' : 'down']">
                    {{ holdingsMap[s.code].avg_cost < s.last_price ? '+' : '' }}{{ ((s.last_price - holdingsMap[s.code].avg_cost) * holdingsMap[s.code].quantity).toFixed(0) }}
                  </span>
                </div>
                <div v-if="holdingsMap[s.code].realized_pnl > 0" class="holdings-row">
                  <span class="holdings-label">已落袋</span>
                  <span class="holdings-value t-profit">+{{ holdingsMap[s.code].realized_pnl.toFixed(0) }}</span>
                </div>
                <div v-if="holdingsMap[s.code].last_buy_price != null" class="holdings-row">
                  <span class="holdings-label">最后买</span>
                  <span class="holdings-value price-tag" @click="openTradeModal(s, 'buy', holdingsMap[s.code].last_buy_price)">¥{{ holdingsMap[s.code].last_buy_price.toFixed(2) }}</span>
                </div>
                <div v-if="holdingsMap[s.code].last_sell_price != null" class="holdings-row">
                  <span class="holdings-label">最后卖</span>
                  <span class="holdings-value price-tag" @click="openTradeModal(s, 'sell', holdingsMap[s.code].last_sell_price)">¥{{ holdingsMap[s.code].last_sell_price.toFixed(2) }}</span>
                </div>
              </div>
              <div class="stock-footer">
                <span>报告: {{ s.report_count }}</span>
                <span v-if="s.last_analysis" :class="{ expired: isExpired(s.last_analysis) }">
                  分析: {{ fmtDate(s.last_analysis) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- By Sector -->
      <template v-if="groupMode === 'sector'">
        <div v-for="group in sectorGroups" :key="group.sector" class="sector-group">
          <div class="sector-header" @click="toggleGroup('sector-' + group.sector)">
            <span class="sector-name">{{ group.sector || '未分类' }}</span>
            <span class="sector-count">{{ group.stocks.length }} 只</span>
            <span class="collapse-icon">{{ collapsedGroups.has('sector-' + group.sector) ? '▸' : '▾' }}</span>
          </div>
          <div v-show="!collapsedGroups.has('sector-' + group.sector)" class="stock-grid">
            <div
              v-for="s in group.stocks"
              :key="s.code"
              class="stock-card card"
              @click="openStock(s.code)"
            >
              <div class="stock-main">
                <div class="stock-title-row">
                  <span class="stock-code">{{ s.code }}</span>
                  <span class="stock-name">{{ s.name }}</span>
                  <span v-if="s.watchlist" class="tag-badge tag-watch">关注</span>
                  <span :class="['status-badge', 'status-' + (s.status || 'neutral')]" @click.stop="toggleStatusMenu(s.code)">{{ statusShort(s.status) }}</span>
                  <button class="trade-btn" @click.stop="openTradeModal(s)" title="录入成交">记</button>
                  <div v-if="statusMenuCode === s.code" class="status-dropdown" @click.stop>
                    <div v-for="st in statusOptions" :key="st.key" :class="['status-option', { active: (s.status || 'neutral') === st.key }]" @click="setStatus(s, st.key)">{{ st.label }}</div>
                  </div>
                </div>
                <div class="stock-price-row">
                  <span class="price-current" :class="priceClass(s.change_pct)">
                    {{ s.last_price != null ? '¥' + s.last_price.toFixed(2) : '--' }}
                  </span>
                  <span v-if="s.change_pct != null" class="price-change" :class="priceClass(s.change_pct)">
                    {{ s.change_pct > 0 ? '+' : '' }}{{ s.change_pct.toFixed(2) }}%
                  </span>
                </div>
                <div class="stock-dims">
                  <span :class="['dim-badge', 'dim-' + dim(s, 'quality')]">质</span>
                  <span :class="['dim-badge', 'dim-' + dim(s, 'valuation')]">估</span>
                  <span :class="['dim-badge', 'dim-' + dim(s, 'timing')]">时</span>
                  <span :class="['dim-badge', 'dim-' + dim(s, 'risk')]">险</span>
                  <span :class="['verdict-badge', 'verdict-' + (s.dimensions?.verdict || s.overall)]">{{ verdictLabel(s) }}</span>
                </div>
              </div>
              <div v-if="s.price_marks?.length > 0" class="marks-section">
                <div v-for="m in s.price_marks" :key="m.id" class="mark-row">
                  <span class="mark-label">{{ m.label }}</span>
                  <span class="mark-target">¥{{ m.price.toFixed(2) }}</span>
                  <span v-if="m.diff != null" :class="['mark-diff', m.diff >= 0 ? 'up' : 'down']">
                    {{ m.diff > 0 ? '+' : '' }}{{ m.diff.toFixed(2) }} ({{ m.diff_pct > 0 ? '+' : '' }}{{ m.diff_pct.toFixed(1) }}%)
                  </span>
                </div>
              </div>
              <!-- Holdings Summary -->
              <div v-if="holdingsMap[s.code]?.quantity > 0" class="holdings-section">
                <div class="holdings-row">
                  <span class="holdings-label">持仓</span>
                  <span class="holdings-value">{{ holdingsMap[s.code].quantity }}股 @ ¥{{ holdingsMap[s.code].avg_cost.toFixed(2) }}</span>
                  <span v-if="s.last_price" :class="['holdings-pnl', holdingsMap[s.code].avg_cost < s.last_price ? 'up' : 'down']">
                    {{ holdingsMap[s.code].avg_cost < s.last_price ? '+' : '' }}{{ ((s.last_price - holdingsMap[s.code].avg_cost) * holdingsMap[s.code].quantity).toFixed(0) }}
                  </span>
                </div>
                <div v-if="holdingsMap[s.code].realized_pnl > 0" class="holdings-row">
                  <span class="holdings-label">已落袋</span>
                  <span class="holdings-value t-profit">+{{ holdingsMap[s.code].realized_pnl.toFixed(0) }}</span>
                </div>
                <div v-if="holdingsMap[s.code].last_buy_price != null" class="holdings-row">
                  <span class="holdings-label">最后买</span>
                  <span class="holdings-value price-tag" @click="openTradeModal(s, 'buy', holdingsMap[s.code].last_buy_price)">¥{{ holdingsMap[s.code].last_buy_price.toFixed(2) }}</span>
                </div>
                <div v-if="holdingsMap[s.code].last_sell_price != null" class="holdings-row">
                  <span class="holdings-label">最后卖</span>
                  <span class="holdings-value price-tag" @click="openTradeModal(s, 'sell', holdingsMap[s.code].last_sell_price)">¥{{ holdingsMap[s.code].last_sell_price.toFixed(2) }}</span>
                </div>
              </div>
              <div class="stock-footer">
                <span>报告: {{ s.report_count }}</span>
                <span v-if="s.last_analysis" :class="{ expired: isExpired(s.last_analysis) }">
                  分析: {{ fmtDate(s.last_analysis) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </template>
    </template>

    <!-- VIEW 2: Matrix (Quality × Valuation) -->
    <template v-if="viewMode === 'matrix'">
      <!-- Unassessed stocks -->
      <div v-if="unassessedStocks.length > 0" class="unassessed-banner card">
        <div class="ua-title">⚪ 未评估（{{ unassessedStocks.length }} 只）— 建议补充分析</div>
        <div class="ua-stocks">
          <div
            v-for="s in unassessedStocks"
            :key="s.code"
            class="matrix-stock"
            @click="openStock(s.code)"
          >
            <div class="ms-code">{{ s.code }}</div>
            <div class="ms-name">{{ s.name }}</div>
            <div class="ms-price" :class="priceClass(s.change_pct)">
              {{ s.last_price != null ? '¥' + s.last_price.toFixed(1) : '--' }}
              <span v-if="s.change_pct != null">{{ s.change_pct > 0 ? '+' : '' }}{{ s.change_pct.toFixed(1) }}%</span>
            </div>
          </div>
        </div>
      </div>

      <div class="matrix-container">
        <div class="matrix-labels">
          <div class="matrix-y-label">质量好 ↑</div>
          <div class="matrix-y-label-bottom">质量差 ↓</div>
        </div>
        <div class="matrix-grid">
          <div class="matrix-x-labels">
            <span>估值便宜 ←</span>
            <span>→ 估值贵</span>
          </div>
          <div class="matrix-quadrant q-accumulate">
            <div class="q-title">🟢 重仓区</div>
            <div class="q-sub">质量好 + 估值便宜</div>
            <div class="q-stocks">
              <div
                v-for="s in matrixQ1"
                :key="s.code"
                class="matrix-stock"
                @click="openStock(s.code)"
              >
                <div class="ms-code">{{ s.code }}</div>
                <div class="ms-name">{{ s.name }}</div>
                <div class="ms-price" :class="priceClass(s.change_pct)">
                  {{ s.last_price != null ? '¥' + s.last_price.toFixed(1) : '--' }}
                  <span v-if="s.change_pct != null">{{ s.change_pct > 0 ? '+' : '' }}{{ s.change_pct.toFixed(1) }}%</span>
                </div>
              </div>
              <div v-if="matrixQ1.length === 0" class="q-empty">暂无</div>
            </div>
          </div>
          <div class="matrix-quadrant q-hold">
            <div class="q-title">🔵 持有区</div>
            <div class="q-sub">质量好 + 估值合理/贵</div>
            <div class="q-stocks">
              <div
                v-for="s in matrixQ2"
                :key="s.code"
                class="matrix-stock"
                @click="openStock(s.code)"
              >
                <div class="ms-code">{{ s.code }}</div>
                <div class="ms-name">{{ s.name }}</div>
                <div class="ms-price" :class="priceClass(s.change_pct)">
                  {{ s.last_price != null ? '¥' + s.last_price.toFixed(1) : '--' }}
                  <span v-if="s.change_pct != null">{{ s.change_pct > 0 ? '+' : '' }}{{ s.change_pct.toFixed(1) }}%</span>
                </div>
              </div>
              <div v-if="matrixQ2.length === 0" class="q-empty">暂无</div>
            </div>
          </div>
          <div class="matrix-quadrant q-speculate">
            <div class="q-title">🟡 投机区</div>
            <div class="q-sub">质量一般 + 估值便宜</div>
            <div class="q-stocks">
              <div
                v-for="s in matrixQ3"
                :key="s.code"
                class="matrix-stock"
                @click="openStock(s.code)"
              >
                <div class="ms-code">{{ s.code }}</div>
                <div class="ms-name">{{ s.name }}</div>
                <div class="ms-price" :class="priceClass(s.change_pct)">
                  {{ s.last_price != null ? '¥' + s.last_price.toFixed(1) : '--' }}
                  <span v-if="s.change_pct != null">{{ s.change_pct > 0 ? '+' : '' }}{{ s.change_pct.toFixed(1) }}%</span>
                </div>
              </div>
              <div v-if="matrixQ3.length === 0" class="q-empty">暂无</div>
            </div>
          </div>
          <div class="matrix-quadrant q-avoid">
            <div class="q-title">🔴 回避区</div>
            <div class="q-sub">质量差 或 估值离谱</div>
            <div class="q-stocks">
              <div
                v-for="s in matrixQ4"
                :key="s.code"
                class="matrix-stock"
                @click="openStock(s.code)"
              >
                <div class="ms-code">{{ s.code }}</div>
                <div class="ms-name">{{ s.name }}</div>
                <div class="ms-price" :class="priceClass(s.change_pct)">
                  {{ s.last_price != null ? '¥' + s.last_price.toFixed(1) : '--' }}
                  <span v-if="s.change_pct != null">{{ s.change_pct > 0 ? '+' : '' }}{{ s.change_pct.toFixed(1) }}%</span>
                </div>
              </div>
              <div v-if="matrixQ4.length === 0" class="q-empty">暂无</div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- VIEW 3: Compact List -->
    <template v-if="viewMode === 'list'">
      <div class="list-table card">
        <table>
          <thead>
            <tr>
              <th @click="sortBy('code')">代码 {{ sortIcon('code') }}</th>
              <th @click="sortBy('name')">名称 {{ sortIcon('name') }}</th>
              <th @click="sortBy('sector')">行业 {{ sortIcon('sector') }}</th>
              <th @click="sortBy('last_price')">价格 {{ sortIcon('last_price') }}</th>
              <th @click="sortBy('change_pct')">涨跌 {{ sortIcon('change_pct') }}</th>
              <th @click="sortByDim('quality')">质量 {{ sortIconDim('quality') }}</th>
              <th @click="sortByDim('valuation')">估值 {{ sortIconDim('valuation') }}</th>
              <th @click="sortByDim('timing')">时机 {{ sortIconDim('timing') }}</th>
              <th @click="sortByDim('risk')">风险 {{ sortIconDim('risk') }}</th>
              <th @click="sortByDim('verdict')">综合 {{ sortIconDim('verdict') }}</th>
              <th @click="sortBy('report_count')">报告 {{ sortIcon('report_count') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="s in sortedStocks"
              :key="s.code"
              class="list-row"
              @click="openStock(s.code)"
            >
              <td class="cell-code">{{ s.code }}</td>
              <td class="cell-name">{{ s.name }}</td>
              <td class="cell-sector">{{ s.sector }}</td>
              <td :class="['cell-price', priceClass(s.change_pct)]">
                {{ s.last_price != null ? '¥' + s.last_price.toFixed(2) : '--' }}
              </td>
              <td :class="['cell-pct', priceClass(s.change_pct)]">
                {{ s.change_pct != null ? (s.change_pct > 0 ? '+' : '') + s.change_pct.toFixed(2) + '%' : '--' }}
              </td>
              <td><span :class="['dim-dot', 'dim-' + dim(s, 'quality')]"></span></td>
              <td><span :class="['dim-dot', 'dim-' + dim(s, 'valuation')]"></span></td>
              <td><span :class="['dim-dot', 'dim-' + dim(s, 'timing')]"></span></td>
              <td><span :class="['dim-dot', 'dim-' + dim(s, 'risk')]"></span></td>
              <td><span :class="['verdict-badge', 'verdict-' + (s.dimensions?.verdict || s.overall)]">{{ verdictLabel(s) }}</span></td>
              <td class="cell-reports">{{ s.report_count }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <div v-if="filteredStocks.length === 0 && !loading" class="card empty">
      没有匹配的股票。调整筛选条件试试。
    </div>
    <StockModal :show="showModal" :stock="selectedStock" @close="closeModal" />

    <!-- Trade Entry Modal -->
    <div v-if="showTradeModal" class="modal-overlay" @click.self="closeTradeModal">
      <div class="modal-panel trade-modal">
        <div class="modal-header">
          <h3>录入成交 — {{ tradeStock?.code }}</h3>
          <button class="modal-close" @click="closeTradeModal">×</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>日期</label>
            <input type="date" v-model="tradeForm.date" />
          </div>
          <div class="form-row">
            <label>时间</label>
            <input type="time" v-model="tradeForm.time" />
          </div>
          <div class="form-row">
            <label>方向</label>
            <div class="btn-group">
              <button :class="{active: tradeForm.type === 'buy'}" @click="tradeForm.type = 'buy'">买入</button>
              <button :class="{active: tradeForm.type === 'sell'}" @click="tradeForm.type = 'sell'">卖出</button>
            </div>
          </div>
          <div class="form-row">
            <label>价格</label>
            <input type="number" v-model.number="tradeForm.price" step="0.01" placeholder="¥" />
          </div>
          <div class="form-row">
            <label>数量</label>
            <input type="number" v-model.number="tradeForm.quantity" step="100" placeholder="股" />
          </div>
          <div class="form-row">
            <label>备注</label>
            <input type="text" v-model="tradeForm.note" placeholder="可选" />
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-primary" @click="submitTrade" :disabled="tradeSubmitting">
            {{ tradeSubmitting ? '...' : '确认录入' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, shallowRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api.js'
import StockModal from '../components/StockModal.vue'

const route = useRoute()
const router = useRouter()

const stocks = shallowRef([])
const loading = ref(false)
const lastRefresh = ref(null)
const viewMode = ref('grouped')
const filterSector = ref('')
const filterVerdict = ref('')
const filterWatchlist = ref(false)
const filterHoldings = ref(false)
const sortKey = ref('code')
const sortAsc = ref(true)
const selectedStock = ref(null)
const showModal = ref(false)

// Trade entry modal
const showTradeModal = ref(false)
const tradeStock = ref(null)
const tradeForm = ref({
  date: new Date().toISOString().slice(0, 10),
  time: '10:00',
  type: 'buy',
  price: 0,
  quantity: 0,
  note: '',
})
const tradeSubmitting = ref(false)

// Status tag quick-edit
const statusMenuCode = ref(null)
const statusOptions = [
  { key: 'core_position', label: '💎 底仓备选' },
  { key: 'tracking', label: '🔭 跟踪中' },
  { key: 'bullish', label: '看好' },
  { key: 'neutral', label: '观望' },
  { key: 'waiting', label: '伺机' },
  { key: 'avoid', label: '回避' },
  { key: 'no_interest', label: '无兴趣' },
  { key: 'blacklist', label: '黑名单' },
  { key: 'archive', label: '📁 归档' },
]
function statusShort(status) {
  const map = {
    core_position: '💎', tracking: '🔭', bullish: '看好', neutral: '观望',
    waiting: '伺机', avoid: '回避', no_interest: '无感', blacklist: '拉黑', archive: '归档'
  }
  return map[status] || '观望'
}
function toggleStatusMenu(code) {
  statusMenuCode.value = statusMenuCode.value === code ? null : code
}
async function setStatus(stock, newStatus) {
  try {
    await api.stocks.updateStatus(stock.code, newStatus)
    stock.status = newStatus
    statusMenuCode.value = null
  } catch (e) {
    console.error(e)
    alert('更新失败')
  }
}

// Read view from URL query
const queryView = route.query.view
if (queryView && ['grouped', 'matrix', 'list'].includes(queryView)) {
  viewMode.value = queryView
}

// Sync view to URL when changed
watch(viewMode, (v) => {
  router.replace({ query: { ...route.query, view: v } })
})

const groupMode = ref('status')
const views = [
  { key: 'grouped', label: '分组' },
  { key: 'matrix', label: '矩阵' },
  { key: 'list', label: '列表' }
]

const groupModes = [
  { key: 'status', label: '状态' },
  { key: 'sector', label: '行业' },
  { key: 'rating', label: '评级' }
]

const collapsedGroups = ref(new Set())
function toggleGroup(key) {
  if (collapsedGroups.value.has(key)) {
    collapsedGroups.value.delete(key)
  } else {
    collapsedGroups.value.add(key)
  }
}

const holdingsMap = ref({})

async function load() {
  loading.value = true
  try {
    const [data, hList] = await Promise.all([
      api.dashboard.get(),
      api.holdings.list().catch(() => [])
    ])
    stocks.value = data.stocks || []
    lastRefresh.value = data.price_data_time || data.last_update
    // Build holdings map
    const map = {}
    for (const h of hList) {
      map[h.code] = h
    }
    holdingsMap.value = map
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function refreshPrices() {
  loading.value = true
  try {
    await api.prices.refresh()
    await load()
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function startAutoRefresh() {
  autoTimer = setInterval(() => load(), 30000)
}
function stopAutoRefresh() {
  if (autoTimer) { clearInterval(autoTimer); autoTimer = null }
}

function openStock(code) {
  const stock = stocks.value.find(s => s.code === code)
  if (stock) {
    selectedStock.value = stock
    showModal.value = true
  }
}
function closeModal() {
  showModal.value = false
  selectedStock.value = null
}

// ── Trade Entry ──
function openTradeModal(stock, presetType = 'buy', presetPrice = null) {
  tradeStock.value = stock
  tradeForm.value = {
    date: new Date().toISOString().slice(0, 10),
    time: new Date().toTimeString().slice(0, 5),
    type: presetType,
    price: presetPrice ?? stock?.last_price ?? 0,
    quantity: 100,
    note: '',
  }
  showTradeModal.value = true
}
function closeTradeModal() {
  showTradeModal.value = false
  tradeStock.value = null
}
async function submitTrade() {
  if (!tradeStock.value) return
  tradeSubmitting.value = true
  try {
    await api.holdings.addTrade(tradeStock.value.code, {
      ...tradeForm.value,
      time: tradeForm.value.time + ':00',
    })
    closeTradeModal()
    await load()  // Refresh holdings
  } catch (e) {
    alert('录入失败: ' + e.message)
  } finally {
    tradeSubmitting.value = false
  }
}

// ── Filtered stocks ──
const filteredStocks = computed(() => {
  return stocks.value.filter(s => {
    if (filterSector.value && s.sector !== filterSector.value) return false
    const verdict = s.dimensions?.verdict || s.overall
    if (filterVerdict.value && verdict !== filterVerdict.value) return false
    if (filterWatchlist.value && !s.watchlist) return false
    if (filterHoldings.value) {
      const h = holdingsMap.value[s.code]
      if (!h || h.quantity <= 0) return false
    }
    return true
  })
})

// ── Holdings Summary ──
const holdingsSummary = computed(() => {
  let count = 0
  let marketValue = 0
  let cost = 0
  let realized = 0
  for (const s of stocks.value) {
    const h = holdingsMap.value[s.code]
    if (!h) continue
    realized += h.realized_pnl || 0
    if (h.quantity <= 0) continue
    count++
    const price = s.last_price || 0
    marketValue += h.quantity * price
    cost += h.quantity * h.avg_cost
  }
  const pnl = marketValue - cost
  const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0
  return { count, marketValue, cost, pnl, pnlPct, realized }
})

const sectors = computed(() => {
  const set = new Set(stocks.value.map(s => s.sector).filter(Boolean))
  return Array.from(set).sort()
})

// ── Status groups ──
const statusGroups = computed(() => {
  const order = ['core_position', 'tracking', 'bullish', 'neutral', 'waiting', 'avoid', 'no_interest', 'blacklist', 'archive']
  const labels = { core_position: '💎 底仓备选', tracking: '🔭 跟踪中', bullish: '看好', neutral: '观望', waiting: '伺机', avoid: '回避', no_interest: '无兴趣', blacklist: '黑名单', archive: '📁 归档' }
  return order.map(key => ({
    key,
    label: labels[key],
    stocks: filteredStocks.value.filter(s => (s.status || 'neutral') === key)
  })).filter(g => g.stocks.length > 0)
})

// ── Rating groups (default) ──
const ratingGroups = computed(() => {
  const order = ['green', 'yellow', 'red', 'none']
  const labels = { green: '看好', yellow: '观望', red: '回避', none: '未评级' }
  return order.map(key => ({
    key,
    label: labels[key],
    stocks: filteredStocks.value.filter(s => {
      const v = s.dimensions?.verdict || s.overall
      return v === key
    })
  })).filter(g => g.stocks.length > 0)
})

// ── Sector groups ──
const sectorGroups = computed(() => {
  const map = {}
  for (const s of filteredStocks.value) {
    const sec = s.sector || '未分类'
    if (!map[sec]) map[sec] = []
    map[sec].push(s)
  }
  return Object.entries(map)
    .map(([sector, stocks]) => ({ sector, stocks }))
    .sort((a, b) => b.stocks.length - a.stocks.length)
})

// ── Matrix view ──
function isAssessed(s) {
  const q = s.dimensions?.quality || s.tags?.moat || s.tags?.fundamental || 'none'
  const v = s.dimensions?.valuation || s.tags?.valuation || 'none'
  return q !== 'none' && v !== 'none'
}
function isGoodQuality(s) {
  const q = s.dimensions?.quality || s.tags?.moat || s.tags?.fundamental || 'none'
  return q === 'green'
}
function isCheap(s) {
  const v = s.dimensions?.valuation || s.tags?.valuation || 'none'
  return v === 'green'
}
function isExpensive(s) {
  const v = s.dimensions?.valuation || s.tags?.valuation || 'none'
  return v === 'red'
}

const matrixQ1 = computed(() => filteredStocks.value.filter(s => isAssessed(s) && isGoodQuality(s) && isCheap(s)))
const matrixQ2 = computed(() => filteredStocks.value.filter(s => isAssessed(s) && isGoodQuality(s) && !isCheap(s)))
const matrixQ3 = computed(() => filteredStocks.value.filter(s => isAssessed(s) && !isGoodQuality(s) && isCheap(s)))
const matrixQ4 = computed(() => filteredStocks.value.filter(s => isAssessed(s) && !isGoodQuality(s) && !isCheap(s)))
const unassessedStocks = computed(() => filteredStocks.value.filter(s => !isAssessed(s)))

// ── List view ──
const dimOrder = { green: 3, yellow: 2, red: 1, none: 0 }

function sortBy(key) {
  if (sortKey.value === key) {
    sortAsc.value = !sortAsc.value
  } else {
    sortKey.value = key
    sortAsc.value = true
  }
}
function sortByDim(dimKey) {
  const key = 'dim:' + dimKey
  if (sortKey.value === key) {
    sortAsc.value = !sortAsc.value
  } else {
    sortKey.value = key
    sortAsc.value = true
  }
}
function sortIcon(key) {
  if (sortKey.value !== key) return ''
  return sortAsc.value ? '↑' : '↓'
}
function sortIconDim(dimKey) {
  if (sortKey.value !== 'dim:' + dimKey) return ''
  return sortAsc.value ? '↑' : '↓'
}
const sortedStocks = computed(() => {
  const arr = [...filteredStocks.value]
  const key = sortKey.value
  arr.sort((a, b) => {
    let av, bv
    if (key.startsWith('dim:')) {
      const dk = key.slice(4)
      av = dimOrder[dim(a, dk)] ?? 0
      bv = dimOrder[dim(b, dk)] ?? 0
    } else {
      av = a[key]
      bv = b[key]
      if (av == null) av = -Infinity
      if (bv == null) bv = -Infinity
    }
    return sortAsc.value ? (av > bv ? 1 : -1) : (av > bv ? -1 : 1)
  })
  return arr
})

// ── Helpers ──
function dim(s, key) {
  return s.dimensions?.[key] || s.tags?.[key] || 'none'
}
function verdictLabel(s) {
  const v = s.dimensions?.verdict || s.overall
  const labels = { green: '看好', yellow: '观望', red: '回避', none: '-' }
  return labels[v] || '-'
}
function priceClass(pct) {
  if (pct == null) return ''
  return pct >= 0 ? 'up' : 'down'
}
function fmtDate(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()}`
}
function fmtTime(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}
function isExpired(iso) {
  return iso && (Date.now() - new Date(iso).getTime()) > 7 * 86400000
}

onMounted(() => {
  load()
  startAutoRefresh()
  // Default collapse: 回避, 无兴趣, 黑名单, 伺机
  for (const key of ['status-avoid', 'status-no_interest', 'status-blacklist', 'status-waiting']) {
    collapsedGroups.value.add(key)
  }
})
onUnmounted(stopAutoRefresh)
</script>

<style scoped>
.dash-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }

.view-tabs { display: flex; gap: 2px; background: #0f172a; padding: 3px; border-radius: 6px; flex-shrink: 0; }
.view-tabs.mini .tab { padding: 3px 10px; border-radius: 4px; font-size: 12px; }
.tab { padding: 6px 14px; border-radius: 6px; font-size: 13px; cursor: pointer; background: transparent; color: #94a3b8; border: none; }
.tab.active { background: #1e3a5f; color: #60a5fa; font-weight: 600; }

.toolbar-inline { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.btn-holdings { display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px; border-radius: 6px; background: #1e3a5f; color: #60a5fa; font-size: 12px; font-weight: 500; text-decoration: none; transition: background 0.15s; }
.btn-holdings:hover { background: #2563eb; color: white; }
.hs-link { margin-left: auto; padding: 3px 10px; border-radius: 5px; background: #1e293b; color: #60a5fa; font-size: 12px; font-weight: 500; text-decoration: none; transition: background 0.15s; white-space: nowrap; }
.hs-link:hover { background: #334155; color: #93c5fd; }

.anomaly-link {
  font-size: 12px;
  color: #fbbf24;
  text-decoration: none;
  padding: 4px 10px;
  background: #1e293b;
  border-radius: 4px;
  margin-right: 8px;
  transition: background 0.15s;
  white-space: nowrap;
}
.anomaly-link:hover {
  background: #334155;
}

.group-tabs { display: flex; gap: 2px; background: #0f172a; padding: 2px; border-radius: 5px; flex-shrink: 0; }
.group-tab { padding: 3px 8px; border-radius: 4px; font-size: 11px; cursor: pointer; background: transparent; color: #94a3b8; border: 1px solid #334155; white-space: nowrap; }
.group-tab.active { background: #1e3a5f; color: #60a5fa; border-color: #1e3a5f; font-weight: 600; }

.filter-check { display: flex; align-items: center; gap: 3px; font-size: 12px; color: #94a3b8; cursor: pointer; white-space: nowrap; }
.filter-check input { accent-color: #3b82f6; width: 14px; height: 14px; }

/* ── Grouped view ── */
.sector-group { margin-bottom: 20px; }
.sector-header { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; cursor: pointer; user-select: none; }
.collapse-icon { font-size: 12px; color: #64748b; margin-left: auto; }
.sector-name { font-size: 15px; font-weight: 600; color: #e2e8f0; }
.sector-count { font-size: 12px; color: #64748b; }

.stock-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }

.stock-card { cursor: pointer; transition: transform 0.12s, border-color 0.12s; padding: 14px; }
.stock-card:hover { transform: translateY(-1px); border-color: #3b82f6; }

.stock-main { margin-bottom: 10px; }
.stock-title-row { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; flex-wrap: wrap; }
.stock-code { font-size: 14px; font-weight: 600; color: #60a5fa; }
.stock-name { font-size: 15px; font-weight: 600; color: #e2e8f0; }
.stock-sector { font-size: 11px; color: #64748b; }

.stock-price-row { display: flex; align-items: baseline; gap: 8px; margin-bottom: 8px; }
.price-current { font-size: 22px; font-weight: 700; }
.price-change { font-size: 13px; font-weight: 500; }
.up { color: #f87171; }
.down { color: #34d399; }

.stock-dims { display: flex; gap: 6px; margin-bottom: 8px; }
.dim-badge { display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 11px; font-weight: 600; }
.dim-green { background: #064e3b; color: #34d399; }
.dim-yellow { background: #713f12; color: #fbbf24; }
.dim-red { background: #7f1d1d; color: #f87171; }
.dim-none { background: #334155; color: #64748b; }

.verdict-badge { display: inline-block; padding: 1px 8px; border-radius: 3px; font-size: 11px; font-weight: 600; }
.verdict-green { background: #064e3b; color: #34d399; }
.verdict-yellow { background: #713f12; color: #fbbf24; }
.verdict-red { background: #7f1d1d; color: #f87171; }
.verdict-none { background: #334155; color: #64748b; }

.tag-badge { display: inline-block; padding: 3px 12px; border-radius: 4px; font-size: 13px; font-weight: 600; }
.tag-green { background: #064e3b; color: #34d399; }
.tag-yellow { background: #713f12; color: #fbbf24; }
.tag-red { background: #7f1d1d; color: #f87171; }
.tag-none { background: #334155; color: #94a3b8; }
.tag-tracking { background: #1e3a5f; color: #60a5fa; }
.tag-bullish { background: #064e3b; color: #34d399; }
.tag-neutral { background: #713f12; color: #fbbf24; }
.tag-avoid { background: #7f1d1d; color: #f87171; }
.tag-no_interest { background: #334155; color: #94a3b8; }
.tag-blacklist { background: #000000; color: #f87171; }
.tag-waiting { background: #3d2c12; color: #fbbf24; }
.tag-archive { background: #334155; color: #94a3b8; }
.tag-watch { background: #1e3a5f; color: #60a5fa; font-size: 11px; padding: 1px 8px; }

.marks-section { border-top: 1px solid #334155; padding-top: 8px; margin-bottom: 8px; }
.mark-row { display: flex; align-items: center; gap: 8px; padding: 3px 0; font-size: 12px; }
.mark-label { color: #94a3b8; min-width: 50px; }
.mark-target { font-weight: 600; color: #e2e8f0; }
.mark-diff { font-size: 11px; }

.stock-footer { display: flex; gap: 12px; font-size: 11px; color: #64748b; border-top: 1px solid #334155; padding-top: 8px; }
.stock-footer .expired { color: #f87171; }

/* ── Holdings ── */
.holdings-section { margin-top: 8px; padding: 8px 0; border-top: 1px dashed #334155; }
.holdings-row { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.holdings-label { color: #64748b; min-width: 32px; }
.holdings-value { color: #e2e8f0; }
.holdings-value.t-profit { color: #22c55e; }
.holdings-value.price-tag { cursor: pointer; color: #60a5fa; text-decoration: underline; text-decoration-style: dotted; }
.holdings-value.price-tag:hover { color: #93c5fd; }
.holdings-pnl { font-size: 11px; margin-left: auto; }
.holdings-pnl.up { color: #22c55e; }
.holdings-pnl.down { color: #ef4444; }

.trade-btn {
  margin-left: auto;
  background: transparent;
  border: 1px solid #475569;
  color: #94a3b8;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  cursor: pointer;
}
.trade-btn:hover { border-color: #3b82f6; color: #3b82f6; }

/* ── Trade Modal ── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: 16px;
}
.trade-modal {
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 10px;
  width: 100%;
  max-width: 380px;
  max-height: 90vh;
  overflow-y: auto;
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #334155;
}
.modal-header h3 { margin: 0; font-size: 15px; color: #e2e8f0; }
.modal-close {
  background: transparent;
  border: none;
  color: #64748b;
  font-size: 20px;
  cursor: pointer;
}
.modal-body { padding: 16px; }
.form-row { margin-bottom: 14px; }
.form-row label { display: block; font-size: 12px; color: #94a3b8; margin-bottom: 4px; }
.form-row input {
  width: 100%;
  padding: 8px 10px;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 6px;
  color: #e2e8f0;
  font-size: 14px;
  box-sizing: border-box;
}
.form-row input:focus { outline: none; border-color: #3b82f6; }
.btn-group { display: flex; gap: 8px; }
.btn-group button {
  flex: 1;
  padding: 8px;
  background: #1e293b;
  border: 1px solid #334155;
  color: #94a3b8;
  border-radius: 6px;
  cursor: pointer;
}
.btn-group button.active {
  background: #1e40af;
  border-color: #3b82f6;
  color: #fff;
}
.modal-footer {
  padding: 0 16px 16px;
  display: flex;
  justify-content: flex-end;
}
.btn-primary {
  padding: 10px 20px;
  background: #3b82f6;
  border: none;
  border-radius: 6px;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
}
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.unassessed-banner { margin-bottom: 16px; padding: 12px 16px; border: 1px dashed #475569; }
.ua-title { font-size: 14px; font-weight: 600; color: #94a3b8; margin-bottom: 10px; }
.ua-stocks { display: flex; flex-wrap: wrap; gap: 6px; }

/* ── Matrix view ── */
.matrix-container { display: flex; gap: 12px; }
.matrix-labels { display: flex; flex-direction: column; justify-content: center; align-items: center; width: 30px; flex-shrink: 0; }
.matrix-y-label { writing-mode: vertical-rl; text-orientation: mixed; font-size: 13px; color: #94a3b8; font-weight: 600; }
.matrix-y-label-bottom { writing-mode: vertical-rl; text-orientation: mixed; font-size: 13px; color: #94a3b8; margin-top: auto; }

.matrix-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; flex: 1; }
.matrix-x-labels { grid-column: 1 / -1; display: flex; justify-content: space-between; font-size: 12px; color: #64748b; padding: 0 8px; }

.matrix-quadrant { border: 1px solid #334155; border-radius: 10px; padding: 12px; min-height: 160px; }
.matrix-quadrant.q-accumulate { background: rgba(6, 78, 59, 0.15); border-color: #064e3b; }
.matrix-quadrant.q-hold { background: rgba(30, 58, 95, 0.15); border-color: #1e3a5f; }
.matrix-quadrant.q-speculate { background: rgba(113, 63, 18, 0.15); border-color: #713f12; }
.matrix-quadrant.q-avoid { background: rgba(127, 29, 29, 0.15); border-color: #7f1d1d; }

.q-title { font-size: 14px; font-weight: 700; margin-bottom: 2px; }
.q-sub { font-size: 11px; color: #64748b; margin-bottom: 8px; }
.q-stocks { display: flex; flex-wrap: wrap; gap: 6px; }
.q-empty { font-size: 12px; color: #64748b; font-style: italic; }

.matrix-stock { background: #0f172a; border: 1px solid #334155; border-radius: 6px; padding: 8px 10px; cursor: pointer; min-width: 100px; }
.matrix-stock:hover { border-color: #3b82f6; }
.ms-code { font-size: 12px; font-weight: 600; color: #60a5fa; }
.ms-name { font-size: 11px; color: #94a3b8; margin-bottom: 2px; }
.ms-price { font-size: 13px; font-weight: 600; }

/* ── List view ── */
.list-table { padding: 0; overflow-x: auto; }
.list-table table { width: 100%; border-collapse: collapse; font-size: 13px; }
.list-table th { text-align: left; padding: 10px 12px; color: #94a3b8; font-weight: 600; border-bottom: 1px solid #334155; cursor: pointer; user-select: none; white-space: nowrap; }
.list-table th:hover { color: #e2e8f0; }
.list-table td { padding: 8px 12px; border-bottom: 1px solid #1e293b; white-space: nowrap; }
.list-row { cursor: pointer; }
.list-row:hover { background: #1e293b; }

.cell-code { font-weight: 600; color: #60a5fa; }
.cell-name { color: #e2e8f0; }
.cell-sector { color: #94a3b8; font-size: 12px; }
.cell-price { font-weight: 600; }
.cell-pct { font-weight: 500; }
.cell-reports { color: #64748b; }

.dim-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; }

.empty { text-align: center; padding: 40px; color: #64748b; }

/* Mobile */
@media (max-width: 768px) {
  .dash-header { gap: 6px; }
  .toolbar-inline { gap: 4px; width: 100%; justify-content: flex-end; }
  .view-tabs.mini .tab { padding: 3px 8px; font-size: 11px; }
  .group-tab { padding: 2px 6px; font-size: 10px; }
  .filter-check { font-size: 11px; }
  .stock-grid { grid-template-columns: 1fr; gap: 10px; }
  .stock-card { padding: 14px; }
  .stock-title-row { gap: 6px; }
  .stock-code { font-size: 15px; }
  .stock-name { font-size: 16px; }
  .stock-sector { font-size: 11px; }
  .price-current { font-size: 24px; }
  .price-change { font-size: 14px; }
  .stock-dims { gap: 6px; }
  .dim-badge { padding: 2px 8px; font-size: 12px; }
  .matrix-container { flex-direction: column; }
  .matrix-labels { display: none; }
  .matrix-grid { grid-template-columns: 1fr; }
  .list-table { font-size: 13px; }
  .list-table th, .list-table td { padding: 8px 10px; }
  .holdings-summary-bar { font-size: 12px; gap: 8px; padding: 8px 10px; }
}

/* ── Holdings Summary Bar ── */
.holdings-summary-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 14px;
  background: #0f172a;
  border: 1px solid #1e293b;
  border-radius: 8px;
  margin-bottom: 12px;
  font-size: 13px;
  flex-wrap: wrap;
}
.holdings-summary-bar .hs-label { font-weight: 600; color: #60a5fa; }
.holdings-summary-bar .hs-item { color: #94a3b8; white-space: nowrap; }
.holdings-summary-bar .hs-pnl { font-weight: 600; }
.holdings-summary-bar .t-profit { color: #fbbf24; font-weight: 600; }

/* ── Status badge & dropdown ── */
.status-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  cursor: pointer;
  user-select: none;
  transition: opacity 0.15s;
  white-space: nowrap;
}
.status-badge:hover { opacity: 0.8; }
.status-core_position { background: rgba(168, 85, 247, 0.2); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3); }
.status-tracking { background: rgba(6, 182, 212, 0.15); color: #22d3ee; border: 1px solid rgba(6, 182, 212, 0.25); }
.status-bullish { background: rgba(34, 197, 94, 0.15); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.25); }
.status-neutral { background: rgba(148, 163, 184, 0.15); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.25); }
.status-waiting { background: rgba(251, 191, 36, 0.15); color: #fbbf24; border: 1px solid rgba(251, 191, 36, 0.25); }
.status-avoid { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.25); }
.status-no_interest { background: rgba(100, 116, 139, 0.15); color: #64748b; border: 1px solid rgba(100, 116, 139, 0.25); }
.status-blacklist { background: rgba(127, 29, 29, 0.25); color: #fca5a5; border: 1px solid rgba(127, 29, 29, 0.4); }
.status-archive { background: rgba(71, 85, 105, 0.2); color: #64748b; border: 1px solid rgba(71, 85, 105, 0.3); }

.status-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  z-index: 90;
  background: rgba(0,0,0,0.15);
}

.status-dropdown {
  position: absolute;
  top: 28px;
  right: 0;
  background-color: #0f172a;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 4px;
  min-width: 120px;
  z-index: 100;
  box-shadow: 0 8px 24px rgba(0,0,0,0.5);
}
.status-option {
  padding: 6px 10px;
  font-size: 12px;
  color: #e2e8f0;
  cursor: pointer;
  border-radius: 4px;
  white-space: nowrap;
}
.status-option:hover { background: #1e293b; }
.status-option.active { background: #1e3a5f; color: #60a5fa; font-weight: 600; }

.stock-title-row { position: relative; }
</style>
