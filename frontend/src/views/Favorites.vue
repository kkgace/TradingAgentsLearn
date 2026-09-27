<!-- TradingAgents-Calv v3.0 | 教育用途，不构成投资建议 -->
<template>
  <div class="favorites-page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>我的自选股</span>
          <el-tag type="warning" size="small">本系统仅用于学习研究，不构成投资建议</el-tag>
        </div>
      </template>

      <div class="toolbar">
        <el-radio-group v-model="activeGroup" @change="load">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button v-for="g in groups" :key="g" :value="g">{{ g }}</el-radio-button>
        </el-radio-group>
        <div>
          <el-button type="primary" @click="addVisible = true">添加自选</el-button>
          <el-button @click="groupVisible = true">新建分组</el-button>
        </div>
      </div>

      <el-table :data="filtered" v-loading="loading" stripe>
        <el-table-column prop="code" label="代码" width="110" />
        <el-table-column label="名称" width="150"><template #default="{ row }">{{ row.stock?.name || row.name || '-' }}</template></el-table-column>
        <el-table-column prop="group_name" label="分组" width="130" />
        <el-table-column label="市场" width="80"><template #default="{ row }">{{ row.stock?.market || row.market || '-' }}</template></el-table-column>
        <el-table-column label="现价" width="100"><template #default="{ row }">{{ fmt(row.stock?.price ?? row.price) }}</template></el-table-column>
        <el-table-column prop="created_at" label="添加时间" min-width="170" />
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="startAna(row)">发起分析</el-button>
            <el-button size="small" type="danger" @click="removeFav(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>暂无自选股，可先在「条件选股」中加入</template>
      </el-table>
    </el-card>

    <el-dialog v-model="addVisible" title="添加自选" width="380px">
      <el-form label-width="80px">
        <el-form-item label="代码">
          <el-input v-model="addForm.code" placeholder="如 600519 / 00700 / AAPL" />
        </el-form-item>
        <el-form-item label="分组">
          <el-select v-model="addForm.group" allow-create filterable style="width: 100%">
            <el-option v-for="g in groups" :key="g" :label="g" :value="g" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveAdd">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="groupVisible" title="新建分组" width="360px">
      <el-input v-model="newGroup" placeholder="分组名称" />
      <template #footer>
        <el-button @click="groupVisible = false">取消</el-button>
        <el-button type="primary" @click="createGroup">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
// TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getFavorites,
  addFavorite,
  deleteFavorite,
  getFavoriteGroups,
  startAnalysis,
} from '../api/index'

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

const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const list = ref<any[]>([])
const groups = ref<string[]>([])
const activeGroup = ref('')

const addVisible = ref(false)
const groupVisible = ref(false)
const newGroup = ref('')
const addForm = reactive({ code: '', group: '默认分组' })

const fmt = (v: any) => (v === null || v === undefined ? '-' : Number(v).toFixed(2))
const filtered = computed(() =>
  activeGroup.value ? list.value.filter((i) => i.group_name === activeGroup.value) : list.value,
)

async function load() {
  loading.value = true
  try {
    const data = un(await getFavorites())
    list.value = Array.isArray(data) ? data : data?.items || []
    const g = un(await getFavoriteGroups())
    groups.value = Array.isArray(g) ? g : []
  } catch (e: any) {
    ElMessage.error(e?.message || '加载自选失败')
  } finally {
    loading.value = false
  }
}

async function saveAdd() {
  if (!addForm.code.trim()) return ElMessage.warning('请输入股票代码')
  saving.value = true
  try {
    await addFavorite(addForm.code.trim(), addForm.group || '默认分组')
    ElMessage.success('已加入自选')
    addVisible.value = false
    addForm.code = ''
    load()
  } catch (e: any) {
    ElMessage.error(e?.message || '添加失败')
  } finally {
    saving.value = false
  }
}

function createGroup() {
  const name = newGroup.value.trim()
  if (!name) return
  if (!groups.value.includes(name)) groups.value.push(name)
  addForm.group = name
  groupVisible.value = false
  newGroup.value = ''
  addVisible.value = true
}

async function removeFav(row: any) {
  try {
    await ElMessageBox.confirm(`确定从自选删除 ${row.code}？`, '提示', { type: 'warning' })
    await deleteFavorite(row.id)
    ElMessage.success('已删除')
    load()
  } catch { /* 用户取消或失败 */ }
}

async function startAna(row: any) {
  try {
    const data = un(await startAnalysis(row.code))
    ElMessage.success('分析任务已创建')
    const id = data?.analysis_id ?? data?.id
    if (id) router.push(`/analysis/${id}`)
  } catch (e: any) {
    ElMessage.error(e?.message || '发起分析失败')
  }
}

onMounted(load)
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.toolbar { display: flex; justify-content: space-between; margin-bottom: 12px; flex-wrap: wrap; gap: 8px; }
</style>
