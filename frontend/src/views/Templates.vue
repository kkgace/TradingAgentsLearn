// TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
<template>
  <div class="templates-page">
    <el-alert type="warning" :closable="false" show-icon
      title="提示词模板影响 13 位 Agent 的分析输出，本系统仅用于学习研究，不构成投资建议" class="disclaimer" />

    <el-card v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>Agent 提示词模板（13 个 Agent）</span>
          <el-button @click="loadAll" :loading="loading">刷新</el-button>
        </div>
      </template>
      <el-collapse v-model="activeGroups">
        <el-collapse-item v-for="group in grouped" :key="group.agent" :name="group.agent">
          <template #title>
            <span class="agent-name">{{ agentLabel(group.agent) }}</span>
            <el-tag size="small" effect="plain">{{ group.agent }}</el-tag>
            <span class="count">{{ group.items.length }} 个变体</span>
          </template>
          <el-table :data="group.items" size="small">
            <el-table-column prop="variant" label="变体" width="140">
              <template #default="{ row }">
                <el-tag :type="variantTag(row.variant)" size="small">{{ row.variant }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="版本" width="90">
              <template #default="{ row }">v{{ row.version }}</template>
            </el-table-column>
            <el-table-column label="启用" width="90">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                  {{ row.is_active ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="updated_at" label="更新时间" width="180">
              <template #default="{ row }">{{ fmtTime(row.updated_at) }}</template>
            </el-table-column>
            <el-table-column prop="content" label="内容预览" min-width="220" show-overflow-tooltip />
            <el-table-column label="操作" width="160">
              <template #default="{ row }">
                <el-button size="small" type="primary" plain @click="openDrawer(row)">编辑</el-button>
                <el-button size="small" @click="showVersion(row)">版本信息</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-collapse-item>
        <el-empty v-if="!grouped.length && !loading" description="暂无模板数据" />
      </el-collapse>
    </el-card>

    <!-- 编辑抽屉 -->
    <el-drawer v-model="drawerVisible" size="55%"
      :title="`编辑模板：${editing ? agentLabel(editing.agent_name) : ''} / ${editing?.variant}`">
      <template v-if="editing">
        <div class="drawer-meta">
          <el-tag size="small">当前版本 v{{ editing.version }}</el-tag>
          <el-switch v-model="editActive" active-text="启用" inactive-text="停用" />
        </div>
        <el-input v-model="editContent" type="textarea" :rows="18"
          placeholder="System Prompt 内容……" />
        <div class="drawer-footer">
          <span class="hint">保存后版本号自动 +1；历史快照不保留。</span>
          <el-button type="primary" :loading="saving" @click="saveTemplate">保存</el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api/client'

interface TemplateRow {
  id: number; agent_name: string; variant: string; content: string
  version: number; is_active: boolean; updated_at: string | null
}

// 13 个 Agent 的中文展示名与展示顺序（与后端 default_templates 对齐）
const AGENT_ORDER: Array<[string, string]> = [
  ['fundamentals', '基本面分析师'],
  ['market', '市场分析师'],
  ['news', '新闻分析师'],
  ['social_media', '社媒分析师'],
  ['bull', '多头研究员'],
  ['bear', '空头研究员'],
  ['research_manager', '研究经理'],
  ['trader', '交易员'],
  ['conservative_debator', '保守辩手'],
  ['neutral_debator', '中性辩手'],
  ['aggressive_debator', '激进辩手'],
  ['risk_manager', '风控经理'],
  ['final_summary', '最终总结'],
]

const templates = ref<TemplateRow[]>([])
const loading = ref(false)
const saving = ref(false)
const drawerVisible = ref(false)
const editing = ref<TemplateRow | null>(null)
const editContent = ref('')
const editActive = ref(true)
const activeGroups = ref<string[]>([])

const agentLabel = (name: string) =>
  AGENT_ORDER.find(([k]) => k === name)?.[1] || name
const fmtTime = (t?: string | null) => (t ? t.replace('T', ' ').slice(0, 19) : '')
const variantTag = (v: string) =>
  v === 'default' ? 'primary' : v === 'conservative' ? 'warning' : 'info'

// 按固定 13 个 Agent 顺序分组
const grouped = computed(() => {
  const map = new Map<string, TemplateRow[]>()
  for (const t of templates.value) {
    if (!map.has(t.agent_name)) map.set(t.agent_name, [])
    map.get(t.agent_name)!.push(t)
  }
  const known = AGENT_ORDER
    .filter(([k]) => map.has(k))
    .map(([k]) => ({ agent: k, items: map.get(k)! }))
  const others = [...map.keys()]
    .filter((k) => !AGENT_ORDER.some(([kk]) => kk === k))
    .map((k) => ({ agent: k, items: map.get(k)! }))
  return [...known, ...others]
})

async function loadAll() {
  loading.value = true
  try {
    const res = await api.get('/templates')
    templates.value = res.data.data || []
  } finally {
    loading.value = false
  }
}

function openDrawer(row: TemplateRow) {
  editing.value = row
  editContent.value = row.content
  editActive.value = !!row.is_active
  drawerVisible.value = true
}

async function saveTemplate() {
  if (!editing.value) return
  if (!editContent.value.trim()) {
    ElMessage.warning('模板内容不能为空')
    return
  }
  saving.value = true
  try {
    const res = await api.put(`/templates/${editing.value.id}`, {
      content: editContent.value,
      is_active: editActive.value,
    })
    const updated = res.data.data as TemplateRow
    editing.value = updated
    ElMessage.success(`已保存，当前版本 v${updated.version}`)
    await loadAll()
    drawerVisible.value = false
  } finally {
    saving.value = false
  }
}

async function showVersion(row: TemplateRow) {
  const res = await api.get(`/templates/${row.id}/versions`)
  const v = res.data.data
  ElMessageBox.alert(
    `Agent：${v.agent_name} (${agentLabel(v.agent_name)})\n` +
    `变体：${v.variant}\n` +
    `当前版本：v${v.current_version}\n` +
    `状态：${v.is_active ? '启用' : '停用'}\n` +
    `更新时间：${fmtTime(v.updated_at)}\n` +
    `历史快照：${(v.history || []).length} 条（v3.0 不保留历史快照）`,
    '版本信息',
    { confirmButtonText: '知道了' },
  )
}

onMounted(loadAll)
</script>

<style scoped>
.disclaimer { margin-bottom: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.agent-name { font-weight: 600; margin-right: 10px; }
.count { color: #c0c4cc; font-size: 12px; margin-left: 10px; }
.drawer-meta { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.drawer-footer { display: flex; justify-content: space-between; align-items: center; margin-top: 14px; }
.hint { color: #909399; font-size: 12px; }
</style>
