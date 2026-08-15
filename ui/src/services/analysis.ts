import http from '@/utils/request'
import type { GetAppAnalysisResponse } from '@/models/analysis'

// 获取应用统计分析服务
export const getAppAnalysis = (app_id: string) => {
  return http.get<GetAppAnalysisResponse>(`/analysis/${app_id}`)
}
