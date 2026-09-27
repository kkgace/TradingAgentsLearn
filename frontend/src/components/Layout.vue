<!-- TradingAgents-Calv v3.0 | 教育用途，不构成投资建议 -->
<template>
  <el-container class="layout-root">
    <el-aside :width="collapsed ? '64px' : '220px'" class="layout-aside">
      <div class="logo" @click="$router.push('/dashboard')">
        <span v-if="!collapsed">TradingAgents</span>
        <span v-else>TA</span>
      </div>
      <el-menu
        class="side-menu"
        :collapse="collapsed"
        :default-active="activePath"
        router
        background-color="#001529"
        text-color="#a6adb4"
        active-text-color="#ffffff"
      >
        <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">
          <el-icon><component :is="m.icon" /></el-icon>
          <template #title>{{ m.title }}</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="layout-header">
        <div class="header-left">
          <el-button text @click="collapsed = !collapsed">
            <el-icon><Expand v-if="collapsed" /><Fold v-else /></el-icon>
          </el-button>
          <span class="page-title">{{ routeTitle }}</span>
        </div>
        <el-dropdown @command="onUserCommand">
          <span class="user-name">
            {{ auth.user?.username || '用户' }}
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="settings">系统设置</el-dropdown-item>
              <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>

      <el-main class="layout-main">
        <router-view />
      </el-main>

      <el-footer class="layout-footer" height="36px">
        本系统仅用于学习研究，不构成投资建议 | TradingAgents-Calv v3.0
      </el-footer>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
// TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowDown,
  Bell,
  TrendCharts,
  DataAnalysis,
  Document,
  Expand,
  Files,
  Fold,
  Monitor,
  Odometer,
  Setting,
  Star,
} from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const collapsed = ref(false)

// 侧边栏菜单（与 router 注册路由保持一致）
const menus = [
  { path: '/dashboard', title: '仪表盘', icon: Odometer },
  { path: '/screening', title: '股票筛选', icon: DataAnalysis },
  { path: '/favorites', title: '自选股', icon: Star },
  { path: '/analysis', title: 'AI 分析', icon: TrendCharts },
  { path: '/plans', title: '交易计划', icon: Files },
  { path: '/triggers', title: '触发器', icon: Bell },
  { path: '/paper', title: '模拟盘', icon: Monitor },
  { path: '/journal', title: '复盘日记', icon: Document },
  { path: '/templates', title: '提示词模板', icon: Files },
  { path: '/settings', title: '系统设置', icon: Setting },
]

const activePath = computed(() =>
  route.path.startsWith('/analysis/') ? '/analysis' : route.path,
)

const routeTitle = computed(() => {
  const hit = menus.find((m) => m.path === activePath.value)
  return hit ? hit.title : ''
})

// 顶栏用户菜单：设置跳转 / 退出登录清空 token 回登录页
function onUserCommand(cmd: string) {
  if (cmd === 'logout') {
    auth.logout()
    router.push('/login')
  } else if (cmd === 'settings') {
    router.push('/settings')
  }
}
</script>

<style scoped>
.layout-root {
  height: 100vh;
}
.layout-aside {
  background: #001529;
  transition: width 0.2s;
  overflow: hidden;
}
.logo {
  height: 56px;
  line-height: 56px;
  text-align: center;
  color: #fff;
  font-weight: 600;
  font-size: 16px;
  cursor: pointer;
  white-space: nowrap;
}
.side-menu {
  border-right: none;
}
.layout-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e8e8e8;
  background: #fff;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.page-title {
  font-size: 15px;
  font-weight: 600;
}
.user-name {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  color: #303133;
}
.layout-main {
  background: #f5f7fa;
}
.layout-footer {
  text-align: center;
  font-size: 12px;
  color: #909399;
  line-height: 36px;
  background: #fff;
  border-top: 1px solid #e8e8e8;
}
</style>
