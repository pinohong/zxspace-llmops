import { apiPrefix, httpCode } from "@/config"
import { Message } from '@arco-design/web-vue'
import { useCredentialStore } from '@/stores/credential'
import router from '@/router'
const TIME_OUT = 100000

// ==================== 接口错误统一处理 ====================

// 1.定义接口响应错误对象，handled标识该错误是否已由全局拦截器处理（已完成页面跳转）
export class ResponseError extends Error {
  code: string
  status: number
  handled: boolean

  constructor(
    message: string,
    options: { code?: string; status?: number; handled?: boolean } = {},
  ) {
    super(message)
    this.name = 'ResponseError'
    this.code = options.code ?? ''
    this.status = options.status ?? 0
    this.handled = options.handled ?? false
  }
}

// 2.定义业务状态码对应的全局跳转处理器
const codeRedirections: Record<string, () => Promise<void>> = {
  // 2.1 未登录：清除本地授权凭证并跳转登录页
  [httpCode.unauthorized]: async () => {
    const { clear: clearCredential } = useCredentialStore()
    clearCredential()
    await router.replace({ name: 'auth-login' })
  },
  // 2.2 无权限：跳转403页面
  [httpCode.forbidden]: async () => {
    await router.replace({ name: 'errors-forbidden' })
  },
  // 2.3 资源不存在：跳转404页面
  [httpCode.notFound]: async () => {
    await router.replace({ name: 'errors-not-found' })
  },
}

// 3.定义HTTP状态码与业务状态码的映射，兼容后端只返回HTTP状态码的场景
const httpStatusToCode: Record<number, string> = {
  401: httpCode.unauthorized,
  403: httpCode.forbidden,
  404: httpCode.notFound,
}

// 4.统一处理接口错误：优先匹配业务状态码，其次回退到HTTP状态码映射，命中跳转规则时完成页面跳转
const handleResponseError = async (status: number, body: any): Promise<ResponseError> => {
  // 4.1 提取业务状态码
  const code = body?.code ?? httpStatusToCode[status]
  const redirect = codeRedirections[code]

  // 4.2 命中跳转规则，执行跳转并返回已处理错误
  if (redirect) {
    await redirect()
    return new ResponseError(body?.message ?? `请求失败：${status}`, {
      code,
      status,
      handled: true,
    })
  }

  // 4.3 未命中跳转规则，返回普通业务错误
  return new ResponseError(body?.message ?? (body ? '请求失败' : `请求失败：${status}`), {
    code,
    status,
  })
}

interface FetchOptionType {
  params?: Record<string, any>
  body?: BodyInit | Record<string, any> | null
}
interface Options extends FetchOptionType {
  method?:string
  mode?:string
  credentials?:string
  headers:{
    [key:string]:any
  }
  redirect?:string
  [key:string]:any
}

const baseFetchOptions:Options = {
  method: "GET",
  mode: "cors",
  credentials: "include",
  headers: {
    "Content-Type": "application/json"
  },
  redirect: "follow"
}

type FetchOpitonType = Omit<RequestInit, "body"> & {
  params?: Record<string, any>
  body?: BodyInit | Record<string, any> | null
  headers?: Record<string, string>
}

const baseFetch = <T>(url: string, fetchOptions: FetchOpitonType): Promise<T> => {
  // 合并参数
  const options:Options = {
    ...baseFetchOptions,
    ...fetchOptions,
    headers: {
      ...baseFetchOptions.headers,
      ...fetchOptions.headers
    }
  }

  const { credential } = useCredentialStore()
  const access_token = credential.access_token
  if (access_token) {
    options.headers["Authorization"] = `Bearer ${access_token}`
  }
  // 判断url有没有/开头，如果没有则拼接一个
  let urlWithPreFix = `${apiPrefix}${url.startsWith('/') ? url : `/${url}`}`

  const { method, body, params } = options
  if (method === 'GET' && params) {
    const paramsArr: string[] = Object.entries(params).map(item => {
      return `${item[0]}=${encodeURIComponent(item[1])}`
    })

    if (paramsArr.length) {
      urlWithPreFix += `?${paramsArr.join("&")}`
    }

    // delete options.params
    delete options.body
  }

  if (body) options.body = JSON.stringify(body)

  return Promise.race([
    new Promise((resolve, reject) => {
      setTimeout(() => {
        reject(new ResponseError('请求超时', { code: 'timeout' }))
      }, TIME_OUT)
    }),
    new Promise((resolve, reject) => {
      window.fetch(urlWithPreFix, options as RequestInit)
        .then(async res => {
          // 1.尝试解析JSON响应，兼容后端返回非JSON格式的错误响应
          const json = await res.json().catch(() => null)

          // 2.HTTP状态码与业务状态码均正常，直接返回数据
          if (res.ok && json?.code === httpCode.success) {
            resolve(json)
            return
          }

          // 3.统一处理接口错误（含未登录/无权限/资源不存在的页面跳转）
          const error = await handleResponseError(res.status, json)

          // 4.未被全局处理的错误，统一进行消息提示后抛出
          if (!error.handled) {
            Message.error(error.message)
          }
          reject(error)
        })
        .catch(err => {
          Message.error(err?.message || '请求失败')
          reject(err)
        })
    })
  ]) as Promise<T>
}


const ssePost = async (
  url: string,
  fetchOptions: FetchOptionType,
  onData: (data: { [key: string]: any }) => Promise<void> | void
) => {
  // 1.组装基础的fetch请求配置
  const options = Object.assign({}, baseFetchOptions, { method: "POST" }, fetchOptions)
  const { credential } = useCredentialStore()
  const access_token = credential.access_token
  if (access_token) {
    options.headers['Authorization'] = `Bearer ${access_token}`
  }

  // 2.组装请求URL
  const urlWithPreFix = `${apiPrefix}${url.startsWith('/') ? url : `/${url}`}`

  // 3.结构body参数，并处理body对应的数据
  const { body } = fetchOptions
  if (body) options.body = JSON.stringify(body)

  // 4.发起fetch请求并处理流式事件响应
  const response = await globalThis.fetch(urlWithPreFix, options as RequestInit)

  // 5 获取响应内容类型并判断类型
  const contentType = response.headers.get('Content-Type')
  if (contentType?.includes('application/json')) {
    // 5.6 接口为json输出，意味着出错，统一处理错误（含页面跳转）后返回错误数据
    const json = await response.json()
    await handleResponseError(response.status, json)
    return json
  }

  return await handleStream(response, onData)
}

const handleStream = (
  response: Response,
  onData: (data: Record<string, any>) => Promise<void> | void,
): Promise<void> => {
  return new Promise((resolve, reject) => {
    // 1.检测网络请求是否正常
    if (!response.ok) {
      reject(new Error('网络请求失败'))
      return
    }

    // 2.构建reader以及decoder
    const reader = response.body?.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    let event = ''
    let data = ''

    // 3.构建read函数用于去读取数据
    const read = async () => {
      reader?.read().then(async (result: any) => {
        if (result.done) {
          resolve()
          return
        }

        buffer += decoder.decode(result.value, { stream: true })
        const lines = buffer.split('\n')

        try {
          for (const line of lines) {
            const trimmedLine = line.trim()
            if (trimmedLine.startsWith('event:')) {
              event = trimmedLine.slice(6).trim()
            } else if (trimmedLine.startsWith('data:')) {
              data = trimmedLine.slice(5).trim()
            }
            // 每个事件以空行结束，只有event和data同时存在，才表示一次流式事件的数据完整获取到了
            if (trimmedLine === '') {
              if (event !== '' && data !== '') {
                await onData({
                  event: event,
                  data: JSON.parse(data),
                })
                event = ''
                data = ''
              }
            }
          }
          buffer = lines.pop() || ''
        } catch (e) {
          reject(e)
        }

        read()
      })
    }

    // 4.调用read函数去执行获取对应的数据
    read()
  })
}

export const upload = <T>(url: string, options: any = {}): Promise<T> => {
  // 1 组装请求URL
  const urlWithPrefix = `${apiPrefix}${url.startsWith('/') ? url : `/${url}`}`

  // 2.组装xhr请求配置信息
  const defaultOptions = {
    method: 'POST',
    url: urlWithPrefix,
    headers: {},
    data: {},
  }
  options = {
    ...defaultOptions,
    ...options,
    headers: { ...defaultOptions.headers, ...options.headers },
  }
  const { credential } = useCredentialStore()
  const access_token = credential.access_token
  if (access_token) options.headers['Authorization'] = `Bearer ${access_token}`

  // 3.构建promise并使用xhr完成文件上传
  return new Promise((resolve, reject) => {
    // 4.创建xhr服务
    const xhr = new XMLHttpRequest()

    // 5.初始化xhr请求并配置headers
    xhr.open(options.method, options.url)
    for (const key in options.headers) {
      xhr.setRequestHeader(key, options.headers[key])
    }

    // 6.设置xhr响应格式并携带授权凭证（例如cookie）
    xhr.withCredentials = true
    xhr.responseType = 'json'

    // 7.监听xhr状态变化并导出数据
    xhr.onreadystatechange = async () => {
      // 8.判断xhr的状态是不是为4，如果为4则代表已经传输完成（涵盖成功与失败）
      if (xhr.readyState === 4) {
        // 9.检查HTTP与业务状态码是否均正常，正常则直接返回数据
        const response = xhr.response
        if (xhr.status >= 200 && xhr.status < 300 && response?.code === httpCode.success) {
          resolve(response)
          return
        }

        // 10.统一处理接口错误（含未登录/无权限/资源不存在的页面跳转）
        const error = await handleResponseError(xhr.status, response)
        if (!error.handled) {
          Message.error(error.message)
        }
        reject(error)
      }
    }

    // 10.添加xhr进度监听
    xhr.upload.onprogress = options.onprogress

    // 11.发送请求
    xhr.send(options.data)
  })
}

// 5.封装给予post的sse(流式事件响应)请求
const request = <T>(url: string, options: FetchOpitonType = {}): Promise<T> => {
  return baseFetch<T>(url, options)
}
const get = <T>(url: string, options: FetchOpitonType = {}) => {
  options.method = "GET"
  return request<T>(url, options)
}
const post = <T>(url: string, options: FetchOpitonType = {}) => {
  options.method = "POST"
  return request<T>(url, options)
}

const http = {
  request,
  post,
  get,
  ssePost,
  upload
}
export default http
