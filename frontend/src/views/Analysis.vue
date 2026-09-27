<!-- TradingAgents-Calv v3.0 | 教育用途，不构成投资建议 -->
<template>
  <div class="analysis-page">
    <el-alert type="warning" :closable="false" class="disclaimer"
              title="本系统仅用于学习研究，不构成投资建议" />

    <el-card class="start-card">
      <template #header><span>发起分析</span></template>
      <el-form @submit.prevent>
        <el-form-item label="股票代码">
          <el-input v-model="codeInput" placeholder="单个代码如 600519；多个用英文逗号分隔批量发起，如 600519,000001,00700,AAPL"
                    clearable style="max-width: 640px" />
        </el-form-item>
        <el-form-item label="提示词变体">
          <el-radio-group v-model="variant">
            <el-radio-button value="default">默认</el-radio-button>
            <el-radio-button value="conservative">保守</el-radio-button>
            <el-radio-button value="aggressive">激进</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="starting" @click="startOne">发起分析</el-button>
          <el-button :loading="starting" @click="startBatch">批量发起</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="history-card">
      <template #header>
        <div class="card-header">
          <span>历史分析</span>
          <el-button size="small" @click="loadHistory">刷新</el-button>
        </div>
      </template>
      <el-table :data="history" v-loading="loading" @row-click="goDetail">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="code" label="股票代码" width="120" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="决策" width="120">
          <template #default="{ row }">
            <span v-if="row.decision">{{ row.decision.action }} 目标价 {{ row.decision.target_price }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="发起时间" />
        <el-table-column prop="finished_at" label="完成时间" />
        <el-table-column label="操作" width="110">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click.stop="goDetail(row)">查看详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

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

interface AnalysisRow {
  id: number
  code: string
  status: string
  decision: { action?: string; target_price?: number } | null
  created_at?: string
  finished_at?: string
}

const router = useRouter()
const codeInput = ref('')
const variant = ref('default')
const starting = ref(false)
const history = ref<AnalysisRow[]>([])
const loading = ref(false)

function statusType(s: string) {
  return { pending: 'info', running: 'warning', done: 'success', failed: 'danger' }[s] as any || 'info'
}
function statusText(s: string) {
  return { pending: '排队中', running: '运行中', done: '已完成', failed: '失败' }[s] || s
}

// 发起单个分析
async function startOne() {
  const code = codeInput.value.split(',')[0]?.trim()
  if (!code) {
    ElMessage.warning('请输入股票代码')
    return
  }
  starting.value = true
  try {
    const data = await api('/analysis/start', {
      method: 'POST',
      body: JSON.stringify({ code, variant: variant.value }),
    })
    ElMessage.success(`已发起分析 #${data.analysis_id}`)
    goDetail({ id: data.analysis_id } as AnalysisRow)
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    starting.value = false
  }
}

// 批量发起：代码逗号分隔
async function startBatch() {
  const codes = codeInput.value.split(',').map((s) => s.trim()).filter(Boolean)
  if (codes.length === 0) {
    ElMessage.warning('请输入一个或多个股票代码（逗号分隔）')
    return
  }
  starting.value = true
  let okCount = 0
  const errors: string[] = []
  for (const code of codes) {
    try {
      await api('/analysis/start', {
        method: 'POST',
        body: JSON.stringify({ code, variant: variant.value }),
      })
      okCount++
    } catch (e: any) {
      errors.push(`${code}: ${e.message}`)
    }
  }
  starting.value = false
  if (errors.length > 0) {
    ElMessage.warning(`成功 ${okCount} 个，失败 ${errors.length} 个：${errors.join('；')}`)
  } else {
    ElMessage.success(`已批量发起 ${okCount} 个分析`)
  }
  loadHistory()
}

async function loadHistory() {
  loading.value = true
  try {
    history.value = await api<AnalysisRow[]>('/analysis')
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

function goDetail(row: AnalysisRow) {
  router.push(`/analysis/${row.id}`)
}

onMounted(loadHistory)
</script>

<style scoped>
.disclaimer {
  margin-bottom: 16px;
}
.start-card {
  margin-bottom: 16px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
