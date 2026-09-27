// TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
<template>
  <div class="journal-page">
    <el-alert type="warning" :closable="false" show-icon
      title="本系统仅用于学习研究，不构成投资建议" class="disclaimer" />

    <!-- 近 30 天统计卡片 -->
    <el-row :gutter="16" class="stats-cards">
      <el-col :span="6">
        <el-card>
          <div class="stat-label">近 30 天成交订单</div>
          <div class="stat-value">{{ stats.order_count ?? 0 }}</div>
          <div class="stat-sub">卖出 {{ stats.sell_order_count ?? 0 }} 笔</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <div class="stat-label">卖出胜率</div>
          <div class="stat-value">
            {{ stats.win_rate === null || stats.win_rate === undefined ? '—' : pct(stats.win_rate) }}
          </div>
          <div class="stat-sub">盈利卖出 {{ stats.win_count ?? 0 }} 笔</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <div class="stat-label">平均单笔 PnL (CNY)</div>
          <div class="stat-value" :class="(stats.avg_pnl_per_sell ?? 0) >= 0 ? 'pos' : 'neg'">
            {{ (stats.avg_pnl_per_sell ?? 0).toFixed(2) }}
          </div>
          <div class="stat-sub">合计 {{ (stats.total_pnl ?? 0).toFixed(2) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <div class="stat-label">按计划执行率</div>
          <div class="stat-value">
            {{ stats.plan_adherence === null || stats.plan_adherence === undefined ? '—' : pct(stats.plan_adherence) }}
          </div>
          <div class="stat-sub">带计划订单 {{ stats.orders_with_plan ?? 0 }} 笔</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="block">
      <template #header>
        <div class="card-header">
          <span>复盘日记</span>
          <div>
            <el-button type="primary" @click="openEditor()">写复盘</el-button>
            <el-button @click="loadAll" :loading="loading">刷新</el-button>
          </div>
        </div>
      </template>
      <el-table :data="entries" v-loading="loading" empty-text="还没有复盘记录">
        <el-table-column prop="created_at" label="时间" width="170">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
        <el-table-column label="盈亏" width="110">
          <template #default="{ row }">
            <span v-if="row.pnl !== null && row.pnl !== undefined"
              :class="row.pnl >= 0 ? 'pos' : 'neg'">
              {{ Number(row.pnl).toFixed(2) }}
            </span>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column label="执行评分" width="100">
          <template #default="{ row }">
            {{ row.adherence_score ?? '—' }}
          </template>
        </el-table-column>
        <el-table-column prop="plan_id" label="关联计划" width="90">
          <template #default="{ row }">{{ row.plan_id ?? '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="170">
          <template #default="{ row }">
            <el-button size="small" @click="openEditor(row)">编辑</el-button>
            <el-button size="small" type="danger" plain @click="removeEntry(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 编辑器对话框 -->
    <el-dialog v-model="editorVisible" :title="editingId ? '编辑复盘' : '写复盘'" width="640px">
      <el-form label-width="90px">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" maxlength="100" placeholder="例如：600519 追高复盘" />
        </el-form-item>
        <el-form-item label="内容">
          <el-input v-model="form.content" type="textarea" :rows="8"
            placeholder="记录决策依据、执行偏差、情绪与改进点……" />
        </el-form-item>
        <el-form-item label="盈亏">
          <el-input-number v-model="form.pnl" :precision="2" />
        </el-form-item>
        <el-form-item label="执行评分">
          <el-slider v-model="form.adherence_score" :min="0" :max="100" show-input />
        </el-form-item>
        <el-form-item label="关联计划 ID">
          <el-input-number v-model="form.plan_id" :min="1" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editorVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveEntry">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api/client'

interface Entry {
  id: number; plan_id: number | null; title: string; content: string | null
  pnl: number | null; adherence_score: number | null; created_at: string | null
}
interface Stats {
  win_rate: number | null; avg_pnl_per_sell: number; total_pnl: number
  order_count: number; sell_order_count: number; win_count: number
  orders_with_plan: number; plan_adherence: number | null
}

const entries = ref<Entry[]>([])
const stats = ref<Partial<Stats>>({})
const loading = ref(false)
const saving = ref(false)
const editorVisible = ref(false)
const editingId = ref<number | null>(null)
const form = reactive<{
  title: string; content: string; pnl?: number; adherence_score: number; plan_id?: number
}>({ title: '', content: '', adherence_score: 80 })

const pct = (v: number) => `${(v * 100).toFixed(1)}%`
const fmtTime = (t?: string | null) => (t ? t.replace('T', ' ').slice(0, 19) : '')

async function loadAll() {
  loading.value = true
  try {
    const [list, st] = await Promise.all([
      api.get('/journal'),
      api.get('/journal/stats'),
    ])
    entries.value = list.data.data || []
    stats.value = st.data.data || {}
  } finally {
    loading.value = false
  }
}

function openEditor(row?: Entry) {
  if (row) {
    editingId.value = row.id
    form.title = row.title
    form.content = row.content || ''
    form.pnl = row.pnl ?? undefined
    form.adherence_score = row.adherence_score ?? 80
    form.plan_id = row.plan_id ?? undefined
  } else {
    editingId.value = null
    form.title = ''
    form.content = ''
    form.pnl = undefined
    form.adherence_score = 80
    form.plan_id = undefined
  }
  editorVisible.value = true
}

async function saveEntry() {
  if (!form.title.trim()) {
    ElMessage.warning('标题不能为空')
    return
  }
  saving.value = true
  try {
    const body = {
      title: form.title.trim(),
      content: form.content,
      pnl: form.pnl ?? null,
      adherence_score: form.adherence_score,
      plan_id: form.plan_id ?? null,
    }
    if (editingId.value) {
      await api.put(`/journal/${editingId.value}`, body)
      ElMessage.success('已更新')
    } else {
      await api.post('/journal', body)
      ElMessage.success('已保存')
    }
    editorVisible.value = false
    loadAll()
  } finally {
    saving.value = false
  }
}

async function removeEntry(row: Entry) {
  await ElMessageBox.confirm(`确定删除复盘「${row.title}」？`, '确认删除', { type: 'warning' })
  await api.delete(`/journal/${row.id}`)
  ElMessage.success('已删除')
  loadAll()
}

onMounted(loadAll)
</script>

<style scoped>
.disclaimer { margin-bottom: 16px; }
.stats-cards { margin-bottom: 16px; }
.stat-label { color: #909399; font-size: 13px; margin-bottom: 6px; }
.stat-value { font-size: 24px; font-weight: 600; }
.stat-sub { color: #c0c4cc; font-size: 12px; margin-top: 4px; }
.block { margin-bottom: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.pos { color: #f56c6c; }
.neg { color: #67c23a; }
</style>
