// TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
<template>
  <div class="paper-page">
    <el-alert type="warning" :closable="false" show-icon
      title="本系统仅用于学习研究，不构成投资建议" class="disclaimer" />

    <!-- 账户三币种卡片 -->
    <el-row :gutter="16" class="account-cards">
      <el-col :span="6">
        <el-card class="account-card">
          <div class="acc-label">人民币账户 (CNY)</div>
          <div class="acc-value">¥ {{ fmt(account.cash_cny) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="account-card">
          <div class="acc-label">港币账户 (HKD)</div>
          <div class="acc-value">HK$ {{ fmt(account.cash_hkd) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="account-card">
          <div class="acc-label">美元账户 (USD)</div>
          <div class="acc-value">$ {{ fmt(account.cash_usd) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="account-card">
          <div class="acc-label">已实现盈亏 (CNY)</div>
          <div class="acc-value" :class="pnlClass(account.realized_pnl_cny)">
            {{ fmt(account.realized_pnl_cny) }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="block">
      <template #header>
        <div class="card-header">
          <span>持仓</span>
          <div>
            <el-button type="primary" @click="openOrder()">下单</el-button>
            <el-button @click="loadAll" :loading="loading">刷新</el-button>
          </div>
        </div>
      </template>
      <el-table :data="positions" v-loading="loading" empty-text="暂无持仓">
        <el-table-column prop="code" label="代码" width="110" />
        <el-table-column prop="market" label="市场" width="80">
          <template #default="{ row }">
            <el-tag size="small">{{ row.market }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="qty" label="数量" width="110" />
        <el-table-column label="成本价" width="120">
          <template #default="{ row }">{{ fmt(row.avg_cost) }}</template>
        </el-table-column>
        <el-table-column prop="currency" label="币种" width="90" />
        <el-table-column label="操作">
          <template #default="{ row }">
            <el-button size="small" @click="openOrder(row, 'buy')">买入</el-button>
            <el-button size="small" type="danger" plain @click="openOrder(row, 'sell')">卖出</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="block">
      <template #header><span>订单历史</span></template>
      <el-table :data="orders" v-loading="loading" empty-text="暂无订单">
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="code" label="代码" width="100" />
        <el-table-column prop="side" label="方向" width="80">
          <template #default="{ row }">
            <el-tag :type="row.side === 'buy' ? 'danger' : 'success'" size="small">
              {{ row.side === 'buy' ? '买入' : '卖出' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="qty" label="数量" width="100" />
        <el-table-column label="价格" width="110">
          <template #default="{ row }">{{ fmt(row.price) }}</template>
        </el-table-column>
        <el-table-column label="佣金" width="100">
          <template #default="{ row }">{{ fmt(row.commission) }}</template>
        </el-table-column>
        <el-table-column prop="currency" label="币种" width="80" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'filled' ? 'success' : 'info'" size="small">
              {{ row.status === 'filled' ? '已成交' : '已拒绝' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="备注" show-overflow-tooltip />
      </el-table>
    </el-card>

    <!-- 下单对话框 -->
    <el-dialog v-model="orderDialog" title="模拟下单" width="440px">
      <el-form label-width="80px">
        <el-form-item label="代码">
          <el-input v-model="orderForm.code" placeholder="如 600519 / 00700 / AAPL" />
        </el-form-item>
        <el-form-item label="方向">
          <el-radio-group v-model="orderForm.side">
            <el-radio-button value="buy">买入</el-radio-button>
            <el-radio-button value="sell">卖出</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="数量">
          <el-input-number v-model="orderForm.qty" :min="1" :step="100" />
        </el-form-item>
        <el-form-item label="价格">
          <el-input-number v-model="orderForm.price" :min="0" :precision="2"
            placeholder="留空取数据源现价" style="width: 100%" />
        </el-form-item>
      </el-form>
      <el-alert type="warning" :closable="false"
        title="模拟盘撮合：默认按数据源现价成交，仅用于学习研究，不构成投资建议" />
      <template #footer>
        <el-button @click="orderDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitOrder">确认下单</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api/client'

interface Account { cash_cny: number; cash_hkd: number; cash_usd: number; realized_pnl_cny: number }
interface Position { id: number; code: string; market: string; qty: number; avg_cost: number; currency: string }
interface Order {
  id: number; code: string; market: string; side: string; qty: number; price: number
  currency: string; commission: number; status: string; reason: string | null; created_at: string | null
}

const account = reactive<Account>({ cash_cny: 0, cash_hkd: 0, cash_usd: 0, realized_pnl_cny: 0 })
const positions = ref<Position[]>([])
const orders = ref<Order[]>([])
const loading = ref(false)
const submitting = ref(false)
const orderDialog = ref(false)
const orderForm = reactive<{ code: string; side: 'buy' | 'sell'; qty: number; price?: number }>({
  code: '', side: 'buy', qty: 100, price: undefined,
})

const fmt = (v?: number) => (v ?? 0).toFixed(2)
const pnlClass = (v?: number) => ((v ?? 0) >= 0 ? 'pnl-up' : 'pnl-down')
const fmtTime = (t?: string | null) => (t ? t.replace('T', ' ').slice(0, 19) : '')

async function loadAll() {
  loading.value = true
  try {
    const [acc, pos, ord] = await Promise.all([
      api.get('/paper/account'),
      api.get('/paper/positions'),
      api.get('/paper/orders'),
    ])
    Object.assign(account, acc.data.data || {})
    positions.value = pos.data.data || []
    orders.value = ord.data.data || []
  } finally {
    loading.value = false
  }
}

function openOrder(row?: Position, side?: 'buy' | 'sell') {
  orderForm.code = row?.code || ''
  orderForm.side = side || 'buy'
  orderForm.qty = 100
  orderForm.price = undefined
  orderDialog.value = true
}

async function submitOrder() {
  if (!orderForm.code.trim()) {
    ElMessage.warning('请输入股票代码')
    return
  }
  submitting.value = true
  try {
    await api.post('/paper/order', {
      code: orderForm.code.trim(),
      side: orderForm.side,
      qty: orderForm.qty,
      price: orderForm.price ?? null,
    })
    ElMessage.success('下单成功')
    orderDialog.value = false
    loadAll()
  } finally {
    submitting.value = false
  }
}

onMounted(loadAll)
</script>

<style scoped>
.disclaimer { margin-bottom: 16px; }
.account-cards { margin-bottom: 16px; }
.acc-label { color: #909399; font-size: 13px; margin-bottom: 6px; }
.acc-value { font-size: 22px; font-weight: 600; }
.pnl-up { color: #f56c6c; }
.pnl-down { color: #67c23a; }
.block { margin-bottom: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
