<!-- TradingAgents-Calv v3.0 | 教育用途，不构成投资建议 -->
<template>
  <div class="dashboard">
    <h2 class="welcome">欢迎，{{ auth.user?.username || '同学' }} 👋</h2>
    <p class="tip-text">从下面任一入口开始你的学习闭环：筛选 → 分析 → 计划 → 触发 → 模拟 → 复盘</p>

    <el-row :gutter="16" class="cards">
      <el-col v-for="c in entries" :key="c.path" :xs="24" :sm="12" :md="6">
        <el-card class="entry-card" shadow="hover" @click="$router.push(c.path)">
          <div class="entry-icon" :style="{ background: c.color }">
            <el-icon :size="26"><component :is="c.icon" /></el-icon>
          </div>
          <div class="entry-body">
            <div class="entry-title">{{ c.title }}</div>
            <div class="entry-desc">{{ c.desc }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="notice-card">
      <template #header>
        <div class="notice-header">
          <el-icon color="#e6a23c"><Warning /></el-icon>
          <span>使用前必读</span>
        </div>
      </template>
      <ul class="notice-list">
        <li>本系统仅用于学习研究，不构成投资建议；所有行情与模拟盘数据均可能来自 Mock 数据源。</li>
        <li>未配置 LLM 密钥时，13 个 Agent 辩论输出为确定性 Mock 内容，流程可完整体验但不具备真实投研价值。</li>
        <li>模拟盘成交、佣金与收益仅为教学演示，不与任何真实账户关联。</li>
        <li>建议路径：先在「股票筛选」发现标的 →「AI 分析」看多智能体辩论 → 生成「交易计划」→ 开「触发器」→「模拟盘」观察成交 →「复盘日记」总结。</li>
      </ul>
    </el-card>
  </div>
</template>

<script setup lang="ts">
// TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
import {
  Bell, DataAnalysis, Document, Files, Monitor, Setting, Star, TrendCharts, Warning,
} from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

// 快捷入口卡片（完整功能见左侧导航菜单）
const entries = [
  { path: '/analysis', title: '发起分析', desc: '13 Agent 多智能体辩论', icon: TrendCharts, color: '#409eff' },
  { path: '/screening', title: '股票筛选', desc: 'PE/PB 估值选股', icon: DataAnalysis, color: '#409eff' },
  { path: '/paper', title: '模拟盘', desc: '虚拟资金下单练习', icon: Monitor, color: '#67c23a' },
  { path: '/plans', title: '我的计划', desc: '管理交易计划与风控', icon: Files, color: '#e6a23c' },
  { path: '/triggers', title: '触发器', desc: '价格条件自动下单', icon: Bell, color: '#e6a23c' },
  { path: '/favorites', title: '自选股', desc: '分组跟踪关注标的', icon: Star, color: '#f56c6c' },
  { path: '/journal', title: '复盘日记', desc: '记录与统计交易总结', icon: Document, color: '#909399' },
  { path: '/settings', title: '系统设置', desc: '数据源/中转站配置', icon: Setting, color: '#909399' },
]
</script>

<style scoped>
.welcome {
  margin: 0 0 6px;
  font-size: 22px;
  color: #303133;
}
.tip-text {
  margin: 0 0 20px;
  color: #909399;
  font-size: 13px;
}
.cards {
  margin-bottom: 16px;
}
.entry-card {
  cursor: pointer;
  margin-bottom: 16px;
  transition: transform 0.15s;
}
.entry-card:hover {
  transform: translateY(-3px);
}
.entry-icon {
  width: 52px;
  height: 52px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  margin-bottom: 12px;
}
.entry-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}
.entry-desc {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
}
.notice-card :deep(.el-card__header) {
  padding: 12px 16px;
}
.notice-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
}
.notice-list {
  margin: 0;
  padding-left: 18px;
  color: #606266;
  font-size: 13px;
  line-height: 1.9;
}
</style>
