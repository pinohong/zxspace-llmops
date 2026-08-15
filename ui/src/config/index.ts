export const apiPrefix = import.meta.env.VITE_API_PREFIX
export const httpCode = {
  success: 'success',
  fail: 'fail',
  notFound: 'not_found',
  unauthorized: 'unauthorized',
  forbidden: 'forbidden',
  validateError: 'validate_rrror'
}

// 类型字符串与中文映射
export const typeMap: { [key: string]: string } = {
  str: '字符串',
  int: '整型',
  float: '浮点型',
  bool: '布尔值',
}


// 智能体事件类型
export const QueueEvent = {
  longTermMemoryRecall: 'long_term_memory_recall',
  agentThought: 'agent_thought',
  agentMessage: 'agent_message',
  agentAction: 'agent_action',
  datasetRetrieval: 'dataset_retrieval',
  agentEnd: 'agent_ent',
  stop: 'stop',
  error: 'error',
  timeout: 'timeout',
  ping: 'ping',
}
