// TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
import { defineStore } from 'pinia'

// 全局应用状态：合规声明、侧边栏折叠等
export const useAppStore = defineStore('app', {
  state: () => ({
    disclaimer: '本系统仅用于学习研究，不构成投资建议',
    sidebarCollapsed: false,
    llmMode: 'mock' as 'mock' | 'live'
  }),
  actions: {
    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed
    }
  }
})
