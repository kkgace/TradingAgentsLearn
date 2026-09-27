<!-- TradingAgents-Calv v3.0 | 教育用途，不构成投资建议 -->
<template>
  <div class="plans-page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>交易计划</span>
          <div>
            <el-tag type="warning" size="small" style="margin-right: 8px">本系统仅用于学习研究，不构成投资建议</el-tag>
            <el-button type="primary" @click="openEdit()">新建计划</el-button>
          </div>
        </div>
      </template>

      <el-table :data="rows" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="code" label="代码" width="100" />
        <el-table-column label="方向" width="90">
          <template #default="{ row }">
            <el-tag :type="dirTag(row.direction)" effect="dark">{{ dirText(row.direction) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="入场价" width="100"><template #default="{ row }">{{ fmt(row.entry_price) }}</template></el-table-column>
        <el-table-column label="目标价" width="100"><template #default="{ row }">{{ fmt(row.target_price) }}</template></el-table-column>
        <el-table-column label="止损价" width="100"><template #default="{ row }">{{ fmt(row.stop_price) }}</template></el-table-column>
        <el-table-column label="风险%" width="90"><template #default="{ row }">{{ fmt((row.risk_pct ?? 0) * 100) }}</template></el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="note" label="备注" min-width="140" show-overflow-tooltip />
        <el-table-column prop="created_at" label="创建时间" min-width="170" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>暂无计划，可由分析详情页「生成交易计划」自动创建</template>
      </el-table>
    </el-card>

    <el-dialog v-model="editVisible" :title="editing ? '编辑计划' : '新建计划'" width="520px">
      <el-form label-width="90px">
        <el-form-item label="代码">
          <el-input v-model="form.code" :disabled="!!editing" placeholder="如 600519" />
        </el-form-item>
        <el-form-item label="方向">
          <el-select v-model="form.direction" style="width: 100%">
            <el-option label="买入" value="buy" />
            <el-option label="持有" value="hold" />
            <el-option label="减仓" value="reduce" />
            <el-option label="卖出" value="sell" />
          </el-select>
        </el-form-item>
        <el-form-item label="入场价"><el-input-number v-model="form.entry_price" :min="0" :precision="2" style="width: 100%" /></el-form-item>
        <el-form-item label="目标价"><el-input-number v-model="form.target_price" :min="0" :precision="2" style="width: 100%" /></el-form-item>
        <el-form-item label="止损价"><el-input-number v-model="form.stop_price" :min="0" :precision="2" style="width: 100%" /></el-form-item>
        <el-form-item label="风险比例"><el-input-number v-model="form.risk_pct_view" :min="0" :max="100" :precision="2" style="width: 100%" /><span style="margin-left:6px">%</span></el-form-item>
        <el-form-item v-if="editing" label="状态">
          <el-select v-model="form.status" style="width: 100%">
            <el-option label="草稿" value="draft" />
            <el-option label="生效" value="active" />
            <el-option label="完成" value="done" />
            <el-option label="取消" value="cancelled" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="form.note" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
// TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getPlans, createPlan, updatePlan, deletePlan } from '../api/index'

function un(r: any): any {
  if (r && typeof r === 'object' && typeof r.code === 'number') {
    if (r.code !== 0) throw new Error(r.msg || '请求失败')
    return r.data
  }
  if (r && r.data && typeof r.data.code === 'number') {
    if (r.data.code !== 0) throw new Error(r.data.msg || '请求失败')
    return r.data.data
  }
  return r
}

const loading = ref(false)
const saving = ref(false)
const rows = ref<any[]>([])
const editVisible = ref(false)
const editing = ref<any>(null)

const form = reactive({
  code: '',
  direction: 'buy',
  entry_price: undefined as number | undefined,
  target_price: undefined as number | undefined,
  stop_price: undefined as number | undefined,
  risk_pct_view: 1,
  status: 'draft',
  note: '',
})

const fmt = (v: any) => (v === null || v === undefined ? '-' : Number(v).toFixed(2))
const dirText = (d: string) => ({ buy: '买入', hold: '持有', reduce: '减仓', sell: '卖出' } as any)[d] || d
const dirTag = (d: string) => ({ buy: 'success', hold: 'info', reduce: 'warning', sell: 'danger' } as any)[d] || 'info'
const statusText = (s: string) => ({ draft: '草稿', active: '生效', done: '完成', cancelled: '取消' } as any)[s] || s
const statusTag = (s: string) => ({ draft: 'info', active: 'success', done: 'primary', cancelled: 'danger' } as any)[s] || 'info'

async function load() {
  loading.value = true
  try {
    const data = un(await getPlans())
    rows.value = Array.isArray(data) ? data : data?.items || []
  } catch (e: any) {
    ElMessage.error(e?.message || '加载计划失败')
  } finally {
    loading.value = false
  }
}

function openEdit(row?: any) {
  editing.value = row || null
  if (row) {
    Object.assign(form, {
      code: row.code,
      direction: row.direction,
      entry_price: row.entry_price,
      target_price: row.target_price,
      stop_price: row.stop_price,
      risk_pct_view: Number(((row.risk_pct ?? 0.01) * 100).toFixed(2)),
      status: row.status,
      note: row.note || '',
    })
  } else {
    Object.assign(form, {
      code: '', direction: 'buy', entry_price: undefined, target_price: undefined,
      stop_price: undefined, risk_pct_view: 1, status: 'draft', note: '',
    })
  }
  editVisible.value = true
}

async function save() {
  if (!form.code) return ElMessage.warning('请填写股票代码')
  saving.value = true
  try {
    const payload = {
      code: form.code,
      direction: form.direction,
      entry_price: form.entry_price,
      target_price: form.target_price,
      stop_price: form.stop_price,
      risk_pct: (form.risk_pct_view ?? 1) / 100,
      note: form.note,
    }
    if (editing.value) {
      await updatePlan(editing.value.id, { ...payload, status: form.status })
      ElMessage.success('已更新')
    } else {
      await createPlan(payload)
      ElMessage.success('已创建')
    }
    editVisible.value = false
    load()
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function remove(row: any) {
  try {
    await ElMessageBox.confirm(`确定删除计划 #${row.id}？`, '提示', { type: 'warning' })
    await deletePlan(row.id)
    ElMessage.success('已删除')
    load()
  } catch { /* 用户取消 */ }
}

onMounted(load)
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
