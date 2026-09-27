<!-- TradingAgents-Calv v3.0 | 教育用途，不构成投资建议 -->
<template>
  <div class="login-page">
    <div class="login-box">
      <h1 class="title">TradingAgents-Calv</h1>
      <p class="subtitle">多智能体股票分析学习平台</p>

      <el-tabs v-model="mode" stretch>
        <el-tab-pane label="登录" name="login" />
        <el-tab-pane label="注册" name="register" />
      </el-tabs>

      <el-form ref="formRef" :model="form" :rules="rules" size="large" @keyup.enter="onSubmit">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" :prefix-icon="User" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码（至少 6 位）"
            show-password
            :prefix-icon="Lock"
          />
        </el-form-item>
        <el-form-item v-if="mode === 'register'" prop="confirm">
          <el-input
            v-model="form.confirm"
            type="password"
            placeholder="确认密码"
            show-password
            :prefix-icon="Lock"
          />
        </el-form-item>
        <el-button
          class="submit-btn"
          type="primary"
          size="large"
          :loading="loading"
          @click="onSubmit"
        >
          {{ mode === 'login' ? '登 录' : '注 册' }}
        </el-button>
      </el-form>

      <p class="compliance">本系统仅用于学习研究，不构成投资建议</p>
    </div>
  </div>
</template>

<script setup lang="ts">
// TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Lock, User } from '@element-plus/icons-vue'
import client from '../api/client'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

const mode = ref<'login' | 'register'>('login')
const loading = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({ username: '', password: '', confirm: '' })

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_r, v, cb) =>
        v === form.password ? cb() : cb(new Error('两次输入的密码不一致')),
      trigger: 'blur',
    },
  ],
}

// 登录/注册二合一提交：注册成功后自动登录
async function onSubmit() {
  if (!(await formRef.value?.validate().catch(() => false))) return
  loading.value = true
  try {
    if (mode.value === 'register') {
      const reg = await client.post('/auth/register', {
        username: form.username,
        password: form.password,
      })
      if (reg.code !== 0) {
        ElMessage.error(reg.msg || '注册失败')
        return
      }
      ElMessage.success('注册成功，正在自动登录…')
    }
    const res = await client.post('/auth/login', {
      username: form.username,
      password: form.password,
    })
    if (res.code !== 0) {
      ElMessage.error(res.msg || '登录失败')
      return
    }
    setAuth(res.data.token, res.data.user)
    ElMessage.success('登录成功')
    router.push('/dashboard')
  } catch (e: any) {
    // client 拦截器已 toast，此处兜底
    if (!e?.shown) ElMessage.error('网络异常，请稍后重试')
  } finally {
    loading.value = false
  }
}

// 写入 auth store（兼容 T11 store 的多种可能实现）
function setAuth(token: string, user: { id: number; username: string; role: string }) {
  if (typeof auth.setAuth === 'function') {
    auth.setAuth(token, user)
  } else {
    auth.token = token
    auth.user = user
  }
  localStorage.setItem('token', token)
}
</script>

<style scoped>
.login-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1f2d3d 0%, #409eff 140%);
}
.login-box {
  width: 380px;
  padding: 36px 40px 24px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.15);
}
.title {
  margin: 0;
  text-align: center;
  font-size: 24px;
  color: #303133;
}
.subtitle {
  text-align: center;
  color: #909399;
  font-size: 13px;
  margin: 6px 0 18px;
}
.submit-btn {
  width: 100%;
  margin-top: 4px;
}
.compliance {
  margin: 20px 0 0;
  text-align: center;
  font-size: 12px;
  color: #c0c4cc;
}
</style>
