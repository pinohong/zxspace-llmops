import http from '@/utils/request'
import type { BaseResponse } from '@/models/base'
import type { PasswordLoginResponse } from '@/models/auth'

// 账号密码登录请求
export const passwordLogin = (email: string, password: string) => {
  return http.post<PasswordLoginResponse>(`/auth/password-login`, {
    body: { email, password },
  })
}

// 退出登录请求
export const logout = () => {
  return http.post<BaseResponse<any>>(`/auth/logout`)
}
