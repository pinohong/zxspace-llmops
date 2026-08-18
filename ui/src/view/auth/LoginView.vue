<template>
  <div class="flex min-h-screen bg-white">
    <!-- 左侧品牌区域 -->
    <aside class="hidden lg:flex relative w-1/2 flex-col justify-between overflow-hidden bg-gradient-to-br from-slate-900 via-blue-950 to-blue-800 p-12 text-white">
      <!-- 装饰圆 -->
      <div class="absolute -top-32 -right-32 h-96 w-96 rounded-full bg-blue-500/20 blur-3xl"></div>
      <div class="absolute bottom-0 -left-24 h-72 w-72 rounded-full bg-cyan-400/10 blur-3xl"></div>

      <!-- Logo -->
      <div class="relative inline-flex items-center gap-3">
        <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-white/10 text-xl font-black tracking-tight backdrop-blur">
          L
        </div>
        <span class="text-lg font-semibold tracking-wide">LLMOps AppBuilder</span>
      </div>

      <!-- 文案 -->
      <div class="relative">
        <h1 class="text-4xl font-bold leading-snug tracking-tight">
          高效开发你的<br />AI 原生应用
        </h1>
        <p class="mt-4 max-w-md text-base leading-7 text-blue-200/80">
          开箱即用的高质量编排模板，零代码快速搭建，覆盖大多数典型业务场景。
        </p>
        <ul class="mt-10 space-y-4 text-sm text-blue-100/90">
          <li class="flex items-center gap-3">
            <span class="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-400/20 text-emerald-300">✓</span>
            丰富的应用组件与编排模板
          </li>
          <li class="flex items-center gap-3">
            <span class="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-400/20 text-emerald-300">✓</span>
            零代码快速编排 AI 应用
          </li>
          <li class="flex items-center gap-3">
            <span class="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-400/20 text-emerald-300">✓</span>
            安全可控的工程化管理能力
          </li>
        </ul>
      </div>

      <!-- 底部 -->
      <p class="relative text-xs text-blue-200/50">© {{ new Date().getFullYear() }} LLMOps AppBuilder</p>
    </aside>

    <!-- 右侧表单区域 -->
    <main class="flex flex-1 items-center justify-center bg-slate-50 p-6">
      <div class="w-full max-w-md">
        <!-- 移动端 Logo -->
        <div class="mb-8 flex items-center justify-center gap-2 lg:hidden">
          <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600 text-base font-black text-white">L</div>
          <span class="text-base font-semibold text-slate-800">LLMOps AppBuilder</span>
        </div>

        <div class="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
          <h2 class="text-2xl font-bold text-slate-900">欢迎回来</h2>
          <p class="mt-1 mb-6 text-sm text-slate-500">登录你的账号，继续构建 AI 应用</p>

          <div class="mb-4 h-6 text-sm leading-6 text-red-600">{{ errorMessage }}</div>

          <a-form
            :model="loginForm"
            @submit="handleSubmit"
            layout="vertical"
            size="large"
          >
            <a-form-item
              field="email"
              :rules="[{ type: 'email', required: true, message: '登录账号必须是合法的邮箱' }]"
              :validate-trigger="['change', 'blur']"
              hide-label
            >
              <a-input v-model="loginForm.email" placeholder="登录账号">
                <template #prefix>
                  <icon-user />
                </template>
              </a-input>
            </a-form-item>
            <a-form-item
              field="password"
              :rules="[{ required: true, message: '账号密码不能为空' }]"
              :validate-trigger="['change', 'blur']"
              hide-label
            >
              <a-input-password v-model="loginForm.password" placeholder="账号密码">
                <template #prefix>
                  <icon-lock />
                </template>
              </a-input-password>
            </a-form-item>

            <div class="flex items-center justify-between">
              <a-checkbox>记住密码</a-checkbox>
              <a-link @click="forgetPassword">忘记密码?</a-link>
            </div>

            <a-button
              :loading="passwordLoginLoading"
              size="large"
              type="primary"
              html-type="submit"
              long
              class="mt-6"
            >
              登录
            </a-button>

            <a-divider class="my-6">第三方授权</a-divider>

            <a-button :loading="providerLoading" size="large" type="dashed" long @click="githubLogin">
              <template #icon>
                <icon-github />
              </template>
              Github 登录
            </a-button>
          </a-form>
        </div>
      </div>
    </main>

    <!-- 底部备案 -->
    <footer class="fixed bottom-0 left-0 w-full border-t border-slate-200/60 bg-white/70 py-2 text-center text-xs text-slate-400 backdrop-blur lg:w-1/2 lg:left-auto lg:right-0">
      <a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer" class="hover:text-slate-600 transition-colors">
        鄂ICP备2026044076号-1
      </a>
    </footer>
  </div>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useCredentialStore } from '@/stores/credential'
import { Message, type ValidatedError } from '@arco-design/web-vue'
import { usePasswordLogin } from '@/hooks/use-auth'
import { useProvider } from '@/hooks/use-oauth'

const errorMessage = ref('')
const loginForm = ref({ email: '', password: '' })
const credentialStore = useCredentialStore()
const router = useRouter()
const { loading: passwordLoginLoading, authorization, handlePasswordLogin } = usePasswordLogin()
const { loading: providerLoading, redirect_url, handleProvider } = useProvider()

const forgetPassword = () => Message.error('忘记密码请联系管理员')

const githubLogin = async () => {
  await handleProvider('github')
  window.location.href = redirect_url.value
}

const handleSubmit = async ({ errors }: { errors: Record<string, ValidatedError> | undefined }) => {
  if (errors) return
  try {
    await handlePasswordLogin(loginForm.value.email, loginForm.value.password)
    Message.success('登录成功，正在跳转')
    credentialStore.update(authorization.value)
    await router.replace({ path: '/home' })
  } catch (error: any) {
    errorMessage.value = error.message
    loginForm.value.password = ''
  }
}
</script>
