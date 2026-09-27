// TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
import client from './client'

// —— 认证 ——
export const authApi = {
  register: (data: { username: string; password: string }) => client.post('/auth/register', data),
  login: (data: { username: string; password: string }) => client.post('/auth/login', data),
  me: () => client.get('/auth/me')
}

// —— 股票 ——
export const stockApi = {
  search: (q: string, market?: string) => client.get('/stocks/search', { params: { q, market } }),
  quote: (code: string) => client.get(`/stocks/${code}/quote`),
  list: (params?: Record<string, unknown>) => client.get('/stocks/list', { params })
}

// —— 筛选 ——
export const screeningApi = {
  run: (data: {
    min_pe?: number; max_pe?: number; min_pb?: number; max_pb?: number
    markets?: string[]; limit?: number
  }) => client.post('/screening/run', data)
}

// —— 自选股 ——
export const favoritesApi = {
  list: () => client.get('/favorites'),
  add: (data: { code: string; group_name?: string }) => client.post('/favorites', data),
  remove: (id: number) => client.delete(`/favorites/${id}`),
  groups: () => client.get('/favorites/groups')
}

// —— 分析 ——
export const analysisApi = {
  start: (code: string) => client.post('/analysis/start', { code }),
  detail: (id: number | string) => client.get(`/analysis/${id}`),
  list: () => client.get('/analysis')
}

// —— 交易计划 ——
export const plansApi = {
  list: () => client.get('/plans'),
  create: (data: Record<string, unknown>) => client.post('/plans', data),
  update: (id: number, data: Record<string, unknown>) => client.put(`/plans/${id}`, data),
  remove: (id: number) => client.delete(`/plans/${id}`),
  fromAnalysis: (analysisId: number | string) => client.post(`/plans/from-analysis/${analysisId}`)
}

// —— 触发器 ——
export const triggersApi = {
  list: () => client.get('/triggers'),
  create: (data: { plan_id: number; type: string; params: Record<string, unknown> }) =>
    client.post('/triggers', data),
  update: (id: number, data: Record<string, unknown>) => client.put(`/triggers/${id}`, data),
  remove: (id: number) => client.delete(`/triggers/${id}`)
}

// —— 模拟盘 ——
export const paperApi = {
  account: () => client.get('/paper/account'),
  positions: () => client.get('/paper/positions'),
  order: (data: { code: string; side: string; qty: number; price?: number }) =>
    client.post('/paper/order', data),
  orders: () => client.get('/paper/orders')
}

// —— 复盘日记 ——
export const journalApi = {
  list: () => client.get('/journal'),
  create: (data: Record<string, unknown>) => client.post('/journal', data),
  update: (id: number, data: Record<string, unknown>) => client.put(`/journal/${id}`, data),
  remove: (id: number) => client.delete(`/journal/${id}`),
  stats: () => client.get('/journal/stats')
}

// —— 提示词模板 ——
export const templatesApi = {
  list: (agent?: string) => client.get('/templates', { params: agent ? { agent } : {} }),
  update: (id: number, data: Record<string, unknown>) => client.put(`/templates/${id}`, data),
  versions: (id: number) => client.get(`/templates/${id}/versions`)
}

// —— 报告 ——
export const reportApi = {
  markdown: (analysisId: number | string) => client.get(`/reports/${analysisId}/markdown`)
}

// —— 系统设置（数据源配置） ——
export const settingsApi = {
  getDatasource: () => client.get('/settings/datasource'),
  updateDatasource: (data: {
    tushare_api?: string; tushare_token?: string; tushare_codes?: string[]
  }) => client.put('/settings/datasource', data),
  testDatasource: (data: { tushare_api?: string; tushare_token?: string }) =>
    client.post('/settings/datasource/test', data),
  resetDatasource: () => client.delete('/settings/datasource')
}

// —— camelCase 便捷导出（各视图直接使用） ——
export const getFavorites = () => favoritesApi.list()
export const addFavorite = (code: string, group_name?: string) =>
  favoritesApi.add({ code, group_name })
export const deleteFavorite = (id: number) => favoritesApi.remove(id)
export const getFavoriteGroups = () => favoritesApi.groups()

export const startAnalysis = (code: string) => analysisApi.start(code)

export const getPlans = () => plansApi.list()
export const createPlan = (data: Record<string, unknown>) => plansApi.create(data)
export const updatePlan = (id: number, data: Record<string, unknown>) => plansApi.update(id, data)
export const deletePlan = (id: number) => plansApi.remove(id)

export const getTriggers = () => triggersApi.list()
export const createTrigger = (data: { plan_id: number; type: string; params: Record<string, unknown> }) =>
  triggersApi.create(data)
export const updateTrigger = (id: number, data: Record<string, unknown>) => triggersApi.update(id, data)
export const deleteTrigger = (id: number) => triggersApi.remove(id)

export const runScreening = (data: {
  min_pe?: number; max_pe?: number; min_pb?: number; max_pb?: number
  markets?: string[]; limit?: number
}) => screeningApi.run(data)

// —— SSE 地址辅助（EventSource 无法带 header，token 走 query） ——
export function sseUrl(analysisId: number | string): string {
  const token = localStorage.getItem('calv_token') || ''
  return `${location.origin}/sse/analysis/${analysisId}?token=${encodeURIComponent(token)}`
}
