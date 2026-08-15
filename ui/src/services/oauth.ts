import http from '@/utils/request'
import { type AuthorizeResponse, type ProviderResponse } from '@/models/oauth'

// 获取指定第三方授权服务的重定向地址
export const provider = (provider_name: string) => {
  return http.get<ProviderResponse>(`/oauth/${provider_name}`)
}

// 指定第三方授权服务认证地址
export const authorize = (provider_name: string, code: string) => {
  return http.post<AuthorizeResponse>(`/oauth/authorize/${provider_name}`, {
    body: { code },
  })
}
