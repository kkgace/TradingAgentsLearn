<!-- TradingAgents-Calv v3.0 | 教育用途，不构成投资建议 -->
<template>
  <div class="triggers-page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>触发器</span>
          <div>
            <el-tag type="warning" size="small" style="margin-right: 8px">本系统仅用于学习研究，不构成投资建议</el-tag>
            <el-button type="primary" @click="openCreate">新建触发器</el-button>
          </div>
        </div>
      </template>

      <el-table :data="rows" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="计划" min-width="160">
          <template #default="{ row }">
            <span v-if="planMap[row.plan_id]">#{{ row.plan_id }} {{ planMap[row.plan_id].code }}（{{ planMap[row.plan_id].direction }}）</span>
            <span v-else>#{{ row.plan_id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="120">
          <template #default="{ row }">
            <el-tag :type="row.type === 'price_above' ? 'danger' : 'success'">{{ row.type === 'price_above' ? '价格高于' : row.type === 'price_below' ? '价格低于' : row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="触发价" width="100">
          <template #default="{ row }">{{ fmt(parsePrice(row)) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="fired_at" label="触发时间" min-width="170"><template #default="{ row }">{{ row.fired_at || '-' }}</template></el-table-column>
        <el-table-column label="开关" width="90">
          <template #default="{ row }">
            <el-switch
              :model-value="row.status === 'on'"
              :disabled="row.status === 'fired'"
              @change="(v: boolean) => toggle(row, v)"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>暂无触发器</template>
      </el-table>
    </el-card>

    <el-dialog v-model="createVisible" title="新建触发器" width="440px">
      <el-form label-width="90px">
        <el-form-item label="关联计划">
          <el-select v-model="form.plan_id" placeholder="选择 draft/active 状态的计划" style="width: 100%">
            <el-option
              v-for="p in candidatePlans"
              :key="p.id"
              :value="p.id"
              :label="`#${p.id} ${p.code} ${p.direction} 目标 ${fmt(p.target_price)}`"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.type">
            <el-radio value="price_above">价格高于</el-radio>
            <el-radio value="price_below">价格低于</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="触发价">
          <el-input-number v-model="form.price" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
// TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getTriggers, createTrigger, updateTrigger, deleteTrigger, getPlans } from '../api/index'

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
const plans = ref<any[]>([])
const createVisible = ref(false)

const form = reactive({ plan_id: undefined as number | undefined, type: 'price_above', price: undefined as number | undefined })

const fmt = (v: any) => (v === null || v === undefined ? '-' : Number(v).toFixed(2))
const statusText = (s: string) => ({ on: '开启', off: '关闭', fired: '已触发' } as any)[s] || s
const statusTag = (s: string) => ({ on: 'success', off: 'info', fired: 'danger' } as any)[s] || 'info'

const planMap = computed(() => {
  const m: Record<number, any> = {}
  for (const p of plans.value) m[p.id] = p
  return m
})
const candidatePlans = computed(() => plans.value.filter((p) => ['draft', 'active'].includes(p.status)))

// params 可能是 JSON 字符串或对象
function parsePrice(row: any): number | undefined {
  let p = row.params
  if (typeof p === 'string') {
    try { p = JSON.parse(p) } catch { return undefined }
  }
  return p?.price
}

async function load() {
  loading.value = true
  try {
    const [t, p] = await Promise.all([getTriggers(), getPlans()])
    const td = un(t)
    rows.value = Array.isArray(td) ? td : td?.items || []
    const pd = un(p)
    plans.value = Array.isArray(pd) ? pd : pd?.items || []
  } catch (e: any) {
    ElMessage.error(e?.message || '加载触发器失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  if (!candidatePlans.value.length) return ElMessage.warning('暂无可用计划，请先创建 draft/active 计划')
  form.plan_id = candidatePlans.value[0]?.id
  form.type = 'price_above'
  form.price = form.plan_id !== undefined ? planMap.value[form.plan_id]?.target_price : undefined
  createVisible.value = true
}

async function save() {
  if (!form.plan_id || form.price === undefined) return ElMessage.warning('请完整填写')
  saving.value = true
  try {
    await createTrigger({ plan_id: form.plan_id, type: form.type, params: { price: form.price } })
    ElMessage.success('已创建')
    createVisible.value = false
    load()
  } catch (e: any) {
    ElMessage.error(e?.message || '创建失败')
  } finally {
    saving.value = false
  }
}

async function toggle(row: any, v: boolean) {
  try {
    await updateTrigger(row.id, { status: v ? 'on' : 'off' })
    row.status = v ? 'on' : 'off'
    ElMessage.success(v ? '已开启' : '已关闭')
  } catch (e: any) {
    ElMessage.error(e?.message || '操作失败')
    load()
  }
}

async function remove(row: any) {
  try {
    await ElMessageBox.confirm(`确定删除触发器 #${row.id}？`, '提示', { type: 'warning' })
    await deleteTrigger(row.id)
    ElMessage.success('已删除')
    load()
  } catch { /* 用户取消 */ }
}

onMounted(load)
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
