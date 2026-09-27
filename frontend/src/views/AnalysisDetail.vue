<!-- TradingAgents-Calv v3.0 | 教育用途，不构成投资建议 -->
<template>
  <div class="detail-page">
    <el-alert type="warning" :closable="false" class="disclaimer"
              title="本系统仅用于学习研究，不构成投资建议" />

    <el-card v-if="analysis">
      <template #header>
        <div class="header">
          <span>分析 #{{ analysis.id }} —— {{ analysis.code }}</span>
          <div>
            <el-tag :type="statusType(analysis.status)">{{ statusText(analysis.status) }}</el-tag>
            <el-tag v-if="sseConnected" type="success" effect="plain" style="margin-left:8px">实时连接中</el-tag>
          </div>
        </div>
      </template>

      <div class="layout">
        <!-- 左侧：Agent 时间线 -->
        <div class="timeline-col">
          <el-scrollbar height="70vh">
            <el-timeline>
              <el-timeline-item v-for="ev in events" :key="ev.seq"
                                :timestamp="ev.created_at" placement="top"
                                :type="kindColor(ev.kind)">
                <div class="event-head">
                  <b>{{ agentLabel(ev.agent) }}</b>
                  <el-tag size="small" :type="kindColor(ev.kind)" effect="plain" style="margin-left:8px">
                    {{ kindLabel(ev.kind) }}
                  </el-tag>
                </div>
                <div class="event-content">{{ ev.content }}</div>
              </el-timeline-item>
              <el-timeline-item v-if="done" timestamp="流程完成" type="success">
                分析流水线已全部执行完毕
              </el-timeline-item>
            </el-timeline>
          </el-scrollbar>
        </div>

        <!-- 右侧：决策卡 + 报告 -->
        <div class="side-col">
          <el-card v-if="decision" class="decision-card">
            <template #header><span>投资决策</span></template>
            <div class="decision-grid">
              <div class="dec-item">
                <div class="label">操作建议</div>
                <div class="value" :class="actionClass">{{ actionText }}</div>
              </div>
              <div class="dec-item">
                <div class="label">目标价</div>
                <div class="value price">{{ fmt(decision.target_price) }}</div>
              </div>
              <div class="dec-item">
                <div class="label">置信度</div>
                <el-progress :percentage="confPct" :color="confColor" />
              </div>
              <div class="dec-item">
                <div class="label">风险分</div>
                <div class="value risk" :style="{ background: riskColor }">
                  {{ fmt(decision.risk_score) }} / 10
                </div>
              </div>
            </div>
            <p v-if="decision.summary" class="summary">{{ decision.summary }}</p>
            <el-button type="primary" :loading="makingPlan" @click="makePlan">
              生成交易计划
            </el-button>
          </el-card>

          <el-card v-if="reportHtml" class="report-card">
            <template #header><span>分析报告</span></template>
            <!-- eslint-disable-next-line vue/no-v-html -->
            <div class="markdown-body" v-html="reportHtml"></div>
          </el-card>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'

// 通用 API 请求：统一 {code,data,msg} 解包，带 Bearer token
const API_BASE = '/api'
function token(): string {
  return localStorage.getItem('token') || ''
}
async function api<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token()}`,
      ...(options.headers || {}),
    },
  })
  const body = await res.json()
  if (body.code !== 0) {
    throw new Error(body.msg || '请求失败')
  }
  return body.data as T
}

interface AgentEvent {
  seq: number
  agent: string
  kind: string
  content: string
  created_at?: string
}
interface Decision {
  action?: string
  target_price?: number
  confidence?: number
  risk_score?: number
  summary?: string
}
interface AnalysisData {
  id: number
  code: string
  status: string
  decision?: Decision | null
  report_md?: string | null
  events?: AgentEvent[]
}

const route = useRoute()
const router = useRouter()
const analysisId = Number(route.params.id)

const analysis = ref<AnalysisData | null>(null)
const events = ref<AgentEvent[]>([])
const decision = ref<Decision | null>(null)
const done = ref(false)
const sseConnected = ref(false)
const makingPlan = ref(false)
let es: EventSource | null = null

// ---------- 展示辅助 ----------
function statusType(s: string) {
  return ({ pending: 'info', running: 'warning', done: 'success', failed: 'danger' } as any)[s] || 'info'
}
function statusText(s: string) {
  return ({ pending: '排队中', running: '运行中', done: '已完成', failed: '失败' } as any)[s] || s
}
function kindColor(kind: string) {
  // analyst 蓝 / researcher 灰 / debator 橙 / manager 绿 / trader 红
  return ({
    analyst: 'primary',
    researcher: 'info',
    debator: 'warning',
    manager: 'success',
    trader: 'danger',
  } as any)[kind] || 'info'
}
function kindLabel(kind: string) {
  return ({
    analyst: '分析师',
    researcher: '研究员',
    debator: '辩手',
    manager: '管理层',
    trader: '交易员',
  } as any)[kind] || kind
}
function agentLabel(name: string) {
  const map: Record<string, string> = {
    fundamentals: '基本面分析师',
    market: '市场分析师',
    news: '新闻分析师',
    social_media: '社媒分析师',
    bull: '多头研究员',
    bear: '空头研究员',
    research_manager: '研究经理',
    trader: '交易员',
    conservative_debator: '保守辩手',
    neutral_debator: '中立辩手',
    aggressive_debator: '激进辩手',
    risk_manager: '风控经理',
    final_summary: '总结',
  }
  return map[name] || name
}
function fmt(v: any) {
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(2) : '-'
}

// ---------- 决策卡派生状态 ----------
const actionText = computed(() => {
  const a = decision.value?.action || ''
  return ({ buy: '买入', hold: '持有', reduce: '减仓', sell: '卖出' } as any)[a] || a || '-'
})
const actionClass = computed(() => {
  const a = decision.value?.action
  return a === 'buy' ? 'act-buy' : a === 'sell' ? 'act-sell' : 'act-hold'
})
const confPct = computed(() => {
  const c = Number(decision.value?.confidence ?? 0)
  // 兼容 0~1 与 0~100 两种写法
  return Math.round(c <= 1 ? c * 100 : c)
})
const confColor = computed(() => (confPct.value >= 70 ? '#67c23a' : confPct.value >= 40 ? '#e6a23c' : '#f56c6c'))
const riskColor = computed(() => {
  const r = Number(decision.value?.risk_score ?? 0)
  return r >= 7 ? '#f56c6c' : r >= 4 ? '#e6a23c' : '#67c23a'
})
const reportHtml = computed(() => {
  const md = analysis.value?.report_md
  return md ? marked.parse(md) as string : ''
})

// ---------- 数据加载 ----------
async function loadDetail() {
  try {
    const data = await api<AnalysisData>(`/analysis/${analysisId}`)
    analysis.value = data
    events.value = (data.events || []).sort((a, b) => a.seq - b.seq)
    if (data.decision) decision.value = data.decision
    if (data.status === 'done' || data.status === 'failed') done.value = true
  } catch (e: any) {
    ElMessage.error(e.message)
  }
}

// ---------- SSE 实时订阅 ----------
// 原生 EventSource 不支持自定义 header，token 通过 URL query 传递
function connectSSE() {
  const url = `${location.origin}/sse/analysis/${analysisId}?token=${encodeURIComponent(token())}`
  es = new EventSource(url)
  es.onopen = () => {
    sseConnected.value = true
  }
  es.onmessage = (msg) => {
    try {
      const payload = JSON.parse(msg.data)
      if (payload.type === 'agent') {
        // 去重：按 seq 判断是否已存在
        if (!events.value.some((e) => e.seq === payload.seq)) {
          events.value.push({
            seq: payload.seq,
            agent: payload.agent,
            kind: payload.kind,
            content: payload.content,
            created_at: new Date().toISOString(),
          })
        }
        if (analysis.value) analysis.value.status = 'running'
      } else if (payload.type === 'decision') {
        decision.value = payload
      } else if (payload.type === 'done') {
        done.value = true
        loadDetail() // 拉取最终报告与完整决策
        closeSSE()
      }
    } catch {
      // 心跳等非 JSON 消息忽略
    }
  }
  es.onerror = () => {
    sseConnected.value = false
    // EventSource 自动重连；若已结束则关闭
    if (done.value) closeSSE()
  }
}
function closeSSE() {
  if (es) {
    es.close()
    es = null
  }
  sseConnected.value = false
}

// ---------- 生成交易计划 ----------
async function makePlan() {
  makingPlan.value = true
  try {
    await api(`/plans/from-analysis/${analysisId}`, { method: 'POST' })
    ElMessage.success('已生成交易计划')
    router.push('/plans')
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    makingPlan.value = false
  }
}

onMounted(async () => {
  await loadDetail()
  // 未完成时订阅 SSE 实时推送
  if (!done.value) connectSSE()
})
onBeforeUnmount(closeSSE)
</script>

<style scoped>
.disclaimer {
  margin-bottom: 16px;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.layout {
  display: grid;
  grid-template-columns: 1fr 380px;
  gap: 16px;
}
.event-head {
  margin-bottom: 4px;
}
.event-content {
  white-space: pre-wrap;
  color: #555;
  font-size: 13px;
}
.decision-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 12px;
}
.dec-item .label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}
.dec-item .value {
  font-size: 20px;
  font-weight: 600;
}
.value.price {
  color: #409eff;
}
.value.risk {
  display: inline-block;
  color: #fff;
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 16px;
}
.act-buy {
  color: #67c23a;
}
.act-sell {
  color: #f56c6c;
}
.act-hold {
  color: #e6a23c;
}
.summary {
  color: #606266;
  font-size: 13px;
  white-space: pre-wrap;
}
.decision-card,
.report-card {
  margin-bottom: 16px;
}
.markdown-body {
  font-size: 14px;
  line-height: 1.7;
  word-break: break-word;
}
</style>
