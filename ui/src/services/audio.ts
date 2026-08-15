import http from '@/utils/request'
import type { BaseResponse } from '@/models/base'

// 语音转文本服务接口
export const audioToText = (file: Blob) => {
  // 1.构建表单并添加音频数据
  const formData = new FormData()
  formData.append('file', new Blob([file], { type: file.type || 'audio/wav' }), 'recording.wav')

  // 2.调用audio服务实现语音转文本
  return http.upload<BaseResponse<{ text: string }>>(`/audio/audio-to-text`, {
    data: formData,
  })
}

// 消息转语音流式接口
export const messageToAudio = (
  message_id: string,
  onData: (event_response: Record<string, any>) => void,
) => {
  return http.ssePost(`/audio/message-to-audio`, { body: { message_id } }, onData)
}
