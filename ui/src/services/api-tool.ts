import http from '@/utils/request'
import type { BaseResponse } from '@/models/base'
import type {
  CreateApiToolProviderRequest,
  GetApiToolProviderResponse,
  GetApiToolProvidersWithPageResponse,
  GetApiToolResponse,
  UpdateApiToolProviderRequest,
} from '@/models/api-tool'
// 获取自定义API列表分页数据
export const getApiToolProvidersWithPage = (
  current_page: number = 1,
  page_size: number = 20,
  search_word: string = '',
) => {
  return http.get<GetApiToolProvidersWithPageResponse>('/api-tools', {
    params: { current_page, page_size, search_word },
  })
}

// 创建API工具提供者
export const createApiToolProvider = (req: CreateApiToolProviderRequest) => {
  return http.post<BaseResponse<any>>('/api-tools', {
    body: req,
  })
}

// 删除API工具提供者详情
export const deleteApiToolProvider = (provider_id: string) => {
  return http.post<BaseResponse<any>>(`/api-tools/${provider_id}/delete`)
}

// 获取API工具详情信息
export const getApiTool = (provider_id: string, tool_name: string) => {
  return http.get<GetApiToolResponse>(`/api-tools/${provider_id}/tools/${tool_name}`)
}

// 获取API工具提供者详情
export const getApiToolProvider = (provider_id: string) => {
  return http.get<GetApiToolProviderResponse>(`/api-tools/${provider_id}`)
}

// 更新API工具提供者详情
export const updateApiToolProvider = (provider_id: string, req: UpdateApiToolProviderRequest) => {
  return http.post<BaseResponse<any>>(`/api-tools/${provider_id}`, {
    body: req,
  })
}

// 校验OpenAPI Schema数据
export const validateOpenAPISchema = (openapi_schema: string) => {
  return http.post<BaseResponse<any>>('/api-tools/validate-openapi-schema', {
    body: { openapi_schema },
  })
}
