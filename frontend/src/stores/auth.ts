// TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
import { defineStore } from 'pinia'

export interface UserInfo {
  id: number
  username: string
  role: string
}

const TOKEN_KEY = 'calv_token'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || '',
    user: null as UserInfo | null
  }),
  getters: {
    isLoggedIn: (s) => !!s.token
  },
  actions: {
    setAuth(token: string, user: UserInfo | null = null) {
      this.token = token
      this.user = user
      localStorage.setItem(TOKEN_KEY, token)
    },
    setToken(token: string, user: UserInfo | null = null) {
      this.token = token
      localStorage.setItem(TOKEN_KEY, token)
      if (user) this.user = user
    },
    setUser(user: UserInfo) {
      this.user = user
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem(TOKEN_KEY)
    }
  }
})
