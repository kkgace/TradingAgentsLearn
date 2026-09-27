// TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
import { createRouter, createWebHistory } from 'vue-router'
import Layout from '../components/Layout.vue'

// 登录页独立；其余页面统一嵌套在 Layout（侧边栏 Admin 布局）下
const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue'), meta: { public: true } },
  {
    path: '/',
    component: Layout,
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'Dashboard', component: () => import('../views/Dashboard.vue') },
      { path: 'screening', name: 'Screening', component: () => import('../views/Screening.vue') },
      { path: 'favorites', name: 'Favorites', component: () => import('../views/Favorites.vue') },
      { path: 'analysis', name: 'Analysis', component: () => import('../views/Analysis.vue') },
      { path: 'analysis/:id', name: 'AnalysisDetail', component: () => import('../views/AnalysisDetail.vue') },
      { path: 'plans', name: 'Plans', component: () => import('../views/Plans.vue') },
      { path: 'triggers', name: 'Triggers', component: () => import('../views/Triggers.vue') },
      { path: 'paper', name: 'Paper', component: () => import('../views/Paper.vue') },
      { path: 'journal', name: 'Journal', component: () => import('../views/Journal.vue') },
      { path: 'templates', name: 'Templates', component: () => import('../views/Templates.vue') },
      { path: 'settings', name: 'Settings', component: () => import('../views/Settings.vue') }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 未登录一律跳 /login（白名单仅 login）
router.beforeEach((to) => {
  const token = localStorage.getItem('calv_token')
  if (!token && !to.meta.public) return { path: '/login' }
  if (token && to.path === '/login') return { path: '/dashboard' }
  return true
})

export default router
