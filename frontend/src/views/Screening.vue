<!-- TradingAgents-Calv v3.0 | 教育用途，不构成投资建议 -->
<template>
  <div class="screening-page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>条件选股</span>
          <el-tag type="warning" size="small">本系统仅用于学习研究，不构成投资建议</el-tag>
        </div>
      </template>
      <el-form :inline="true" :model="form">
        <el-form-item label="PE 范围">
          <el-input-number v-model="form.min_pe" :min="0" :max="1000" placeholder="最小" style="width: 120px" />
          <span class="range-sep">~</span>
          <el-input-number v-model="form.max_pe" :min="0" :max="1000" placeholder="最大" style="width: 120px" />
        </el-form-item>
        <el-form-item label="PB 范围">
          <el-input-number v-model="form.min_pb" :min="0" :max="1000" placeholder="最小" style="width: 120px" />
          <span class="range-sep">~</span>
          <el-input-number v-model="form.max_pb" :min="0" :max="1000" placeholder="最大" style="width: 120px" />
        </el-form-item>
        <el-form-item label="市场">
          <el-select v-model="form.markets" multiple placeholder="全部市场" style="width: 220px">
            <el-option label="A股" value="CN" />
            <el-option label="港股" value="HK" />
            <el-option label="美股" value="US" />
          </el-select>
        </el-form-item>
        <el-form-item label="上限">
          <el-input-number v-model="form.limit" :min="1" :max="200" style="width: 100px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="run">筛选</el-button>
          <el-button @click="reset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" style="margin-top: 12px">
      <el-table :data="rows" v-loading="loading" stripe>
        <el-table-column prop="code" label="代码" width="110" />
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="market" label="市场" width="80" />
        <el-table-column prop="industry" label="行业" min-width="120" show-overflow-tooltip />
        <el-table-column label="PE" width="90"><template #default="{ row }">{{ fmt(row.pe) }}</template></el-table-column>
        <el-table-column label="PB" width="90"><template #default="{ row }">{{ fmt(row.pb) }}</template></el-table-column>
        <el-table-column label="现价" width="100"><template #default="{ row }">{{ fmt(row.price) }}</template></el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openFav(row)">加入自选</el-button>
            <el-button size="small" type="primary" @click="startAna(row)">发起分析</el-button>
          </template>
        </el-table-column>
        <template #empty>暂无数据，请先运行筛选</template>
      </el-table>
    </el-card>

    <el-dialog v-model="favVisible" title="加入自选" width="380px">
      <el-form label-width="80px">
        <el-form-item label="股票">
          <span>{{ favTarget?.code }} {{ favTarget?.name }}</span>
        </el-form-item>
        <el-form-item label="分组">
          <el-select v-model="favGroup" allow-create filterable placeholder="选择或输入分组" style="width: 100%">
            <el-option v-for="g in groups" :key="g" :label="g" :value="g" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="favVisible = false">取消</el-button>
        <el-button type="primary" :loading="favSaving" @click="saveFav">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
// TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  runScreening,
  addFavorite,
  getFavoriteGroups,
  startAnalysis,
} from '../api/index'

// 防御性解包：兼容已解包的 data 与原始 {code,data,msg} 两种形态
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
const rows = ref<any[]>([])
const groups = ref<string[]>([])

const form = reactive({
  min_pe: undefined as number | undefined,
  max_pe: undefined as number | undefined,
  min_pb: undefined as number | undefined,
  max_pb: undefined as number | undefined,
  markets: [] as string[],
  limit: 50,
})

const fmt = (v: any) => (v === null || v === undefined ? '-' : Number(v).toFixed(2))

async function run() {
  loading.value = true
  try {
    const data = un(await runScreening({ ...form }))
    rows.value = Array.isArray(data) ? data : data?.items || []
  } catch (e: any) {
    ElMessage.error(e?.message || '筛选失败')
  } finally {
    loading.value = false
  }
}

function reset() {
  form.min_pe = form.max_pe = form.min_pb = form.max_pb = undefined
  form.markets = []
  form.limit = 50
  run()
}

const favVisible = ref(false)
const favSaving = ref(false)
const favTarget = ref<any>(null)
const favGroup = ref('默认分组')

function openFav(row: any) {
  favTarget.value = row
  favVisible.value = true
}

async function saveFav() {
  if (!favTarget.value) return
  favSaving.value = true
  try {
    await addFavorite(favTarget.value.code, favGroup.value || '默认分组')
    ElMessage.success('已加入自选')
    favVisible.value = false
  } catch (e: any) {
    ElMessage.error(e?.message || '加入自选失败')
  } finally {
    favSaving.value = false
  }
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

onMounted(async () => {
  try {
    const g = un(await getFavoriteGroups())
    groups.value = Array.isArray(g) ? g : []
  } catch { /* 忽略，分组仅为辅助 */ }
  run()
})
</script>

<style scoped>
.range-sep { margin: 0 4px; color: #909399; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
