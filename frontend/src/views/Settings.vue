// TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
<template>
  <div class="settings-page">
    <el-alert type="error" :closable="false" show-icon
      title="本系统仅用于学习研究，不构成投资建议。任何输出均不应作为真实交易依据。"
      class="disclaimer" />

    <el-card class="block">
      <template #header><span>LLM 模式</span></template>
      <div class="row">
        <span class="label">运行模式</span>
        <el-tag :type="health?.modeGuess === 'live' ? 'success' : 'warning'">
          {{ health?.modeGuess === 'live' ? 'LIVE（真实 LLM）' : 'MOCK（离线确定性演示）' }}
        </el-tag>
      </div>
      <el-descriptions :column="1" border class="desc">
        <el-descriptions-item label="判断方式">
          后端未配置 LLM_BASE_URL / LLM_API_KEY 时自动进入 MOCK 模式，所有 Agent 输出为确定性演示文本，全流程可离线运行。
        </el-descriptions-item>
        <el-descriptions-item label="启用真实 LLM">
          在 backend 环境变量中配置 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL（OpenAI 兼容协议），重启后生效。
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card class="block">
      <template #header><span>数据源配置（Tushare / 自定义中转站）</span></template>
      <el-descriptions :column="1" border class="desc">
        <el-descriptions-item label="当前数据源">
          <el-tag :type="ds?.active_source === 'tushare' ? 'success' : 'warning'">
            {{ ds?.active_source === 'tushare' ? 'Tushare' : 'Mock（未配置 token）' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="接口地址">{{ ds?.tushare_api || '—' }}</el-descriptions-item>
        <el-descriptions-item label="Token">
          {{ ds?.token_configured ? `已配置（${ds.tushare_token_masked}）` : '未配置' }}
        </el-descriptions-item>
        <el-descriptions-item label="股票池">{{ ds?.tushare_codes || '—' }}</el-descriptions-item>
        <el-descriptions-item label="界面覆盖项">
          {{ ds?.overridden_keys?.length ? ds.overridden_keys.join('、') : '（无，按 .env/默认运行）' }}
        </el-descriptions-item>
      </el-descriptions>

      <el-form label-width="110px" class="ds-form">
        <el-form-item label="接口地址">
          <el-input v-model="dsForm.api"
            :placeholder="`留空保持当前（${ds?.tushare_api || 'http://api.tushare.pro'}）；中转站形如 https://your-relay.example.com`" />
        </el-form-item>
        <el-form-item label="Token">
          <el-input v-model="dsForm.token" type="password" show-password
            :placeholder="ds?.token_configured ? '留空保持不变；填写则覆盖当前 token' : '填写 Tushare / 中转站 token'" />
        </el-form-item>
        <el-form-item label="股票池">
          <el-input v-model="dsForm.codes"
            :placeholder="`留空保持当前；逗号分隔 6 位 A 股代码（当前：${ds?.tushare_codes || '—'}）`" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="saveDatasource">保存并应用</el-button>
          <el-button :loading="testing" @click="testDatasource">测试连接</el-button>
          <el-button type="danger" plain :disabled="!ds?.overridden_keys?.length"
            @click="resetDatasource">恢复默认（.env）</el-button>
          <span v-if="testResult" class="test-result" :class="testResult.ok ? 'ok' : 'bad'">
            {{ testResult.msg }}
          </span>
        </el-form-item>
      </el-form>
      <div class="hint">
        界面配置保存后<b>立即生效（无需重启）</b>，优先级高于 .env；点「恢复默认」即可整体回退 .env 配置。
        行情为 A 股日线数据；未覆盖代码与调用失败自动回退 Mock。仅用于学习研究，不构成投资建议。
      </div>
    </el-card>

    <el-card class="block">
      <template #header><span>系统状态</span></template>
      <el-descriptions :column="1" border class="desc">
        <el-descriptions-item label="后端健康">{{ healthStatus }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card class="block">
      <template #header><span>数据源说明</span></template>
      <el-descriptions :column="1" border class="desc">
        <el-descriptions-item label="默认数据源">MockDataSource：内置 20 只 CN/HK/US 示例股票，价格与估值为确定性演示数据。</el-descriptions-item>
        <el-descriptions-item label="可选数据源">TushareSource：配置 TUSHARE_TOKEN 后启用（A 股日线数据）；未覆盖代码或调用失败自动降级回 Mock。</el-descriptions-item>
        <el-descriptions-item label="模拟盘汇率">HKD→CNY 0.92，USD→CNY 7.2（固定折算，仅用于演示）。</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card class="block">
      <template #header><span>合规声明</span></template>
      <div class="legal">
        <p>1. 本系统（TradingAgents-Calv v3.0）为开源学习项目，仅用于教学与研究多智能体分析流程，<b>不构成任何投资建议</b>。</p>
        <p>2. 系统中的行情、新闻、估值与 Agent 输出可能是模型生成或演示数据，不保证真实性、准确性、完整性。</p>
        <p>3. 模拟盘撮合与盈亏统计仅用于训练复盘，与实际交易存在滑点、流动性、规则等重大差异。</p>
        <p>4. 任何基于本系统内容作出真实投资决策所产生的后果，由使用者自行承担。</p>
      </div>
    </el-card>

    <el-card class="block">
      <template #header><span>关于</span></template>
      <el-descriptions :column="1" border class="desc">
        <el-descriptions-item label="项目">TradingAgents-Calv v3.0</el-descriptions-item>
        <el-descriptions-item label="主题">13 Agent 多智能体分析 → 计划 → 触发器 → 模拟盘 → 复盘 学习闭环</el-descriptions-item>
        <el-descriptions-item label="技术栈">Vue 3 + Element Plus + ECharts / FastAPI + SQLAlchemy + SQLite + SSE</el-descriptions-item>
        <el-descriptions-item label="后端版本">{{ health?.version || '—' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api/client'
import { settingsApi } from '../api'

interface HealthInfo { version?: string; modeGuess?: 'mock' | 'live' }
interface DatasourceInfo {
  tushare_api?: string
  tushare_token_masked?: string | null
  token_configured?: boolean
  tushare_codes?: string
  overridden_keys?: string[]
  active_source?: string
}

const health = ref<HealthInfo | null>(null)
const healthStatus = ref('查询中……')

const ds = ref<DatasourceInfo | null>(null)
const dsForm = reactive({ api: '', token: '', codes: '' })
const saving = ref(false)
const testing = ref(false)
const testResult = ref<{ ok: boolean; msg: string } | null>(null)

async function loadDatasource() {
  const res = await api.get('/settings/datasource')
  ds.value = res.data
}

async function saveDatasource() {
  const body: Record<string, unknown> = {}
  if (dsForm.api.trim()) body.tushare_api = dsForm.api.trim()
  if (dsForm.token.trim()) body.tushare_token = dsForm.token.trim()
  if (dsForm.codes.trim()) {
    body.tushare_codes = dsForm.codes.split(/[,，]/).map(s => s.trim()).filter(Boolean)
  }
  if (!Object.keys(body).length) {
    ElMessage.info('未填写任何修改项（留空字段不会被修改）')
    return
  }
  saving.value = true
  try {
    const res = await settingsApi.updateDatasource(body as {
      tushare_api?: string; tushare_token?: string; tushare_codes?: string[]
    })
    await loadDatasource()
    dsForm.api = ''; dsForm.token = ''; dsForm.codes = ''
    testResult.value = null
    ElMessage.success(res.msg || '已保存并生效')
  } finally {
    saving.value = false
  }
}

async function testDatasource() {
  const body: Record<string, unknown> = {}
  if (dsForm.api.trim()) body.tushare_api = dsForm.api.trim()
  if (dsForm.token.trim()) body.tushare_token = dsForm.token.trim()
  testing.value = true
  testResult.value = null
  try {
    const res = await settingsApi.testDatasource(body as { tushare_api?: string; tushare_token?: string })
    testResult.value = { ok: !!res.data?.ok, msg: res.data?.msg || '未知结果' }
    if (res.data?.ok) ElMessage.success('连接成功')
    else ElMessage.error(res.data?.msg || '连接失败')
  } finally {
    testing.value = false
  }
}

async function resetDatasource() {
  await ElMessageBox.confirm('将清除全部界面覆盖项，回退 .env / 默认配置，确定？', '恢复默认', {
    type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消'
  })
  const res = await settingsApi.resetDatasource()
  await loadDatasource()
  testResult.value = null
  ElMessage.success(res.msg || '已恢复默认')
}

onMounted(async () => {
  try {
    const res = await api.get('/health')
    const data = res.data?.data || {}
    // 后端现阶段未暴露 LLM 模式字段；未配置密钥即 MOCK（见 llm.py）
    health.value = { version: data.version, modeGuess: 'mock' }
    healthStatus.value = data.status === 'ok' ? '正常' : '异常'
  } catch {
    healthStatus.value = '后端不可达'
  }
  loadDatasource().catch(() => {})
})
</script>

<style scoped>
.disclaimer { margin-bottom: 16px; }
.block { margin-bottom: 16px; }
.row { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.label { color: #606266; }
.desc :deep(.el-descriptions__label) { width: 120px; }
.legal p { margin: 6px 0; color: #606266; line-height: 1.7; }
.ds-form { margin-top: 16px; max-width: 640px; }
.test-result { margin-left: 12px; font-size: 13px; }
.test-result.ok { color: #67c23a; }
.test-result.bad { color: #f56c6c; }
.hint { color: #909399; font-size: 13px; line-height: 1.8; margin-top: 8px; }
</style>
