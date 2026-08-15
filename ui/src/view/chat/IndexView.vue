<script setup lang="ts">
// @ts-ignore
import { DynamicScroller, DynamicScrollerItem } from 'vue-virtual-scroller'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { cloneDeep } from 'lodash'
import { Message } from '@arco-design/web-vue'
import { useAccountStore } from '@/stores/account'
import {
  useGetAppConversations,
  useGetWebApp,
  useStopWebAppChat,
  useWebAppChat,
} from '@/hooks/use-web-app'
import {
  useDeleteConversation,
  useGetConversationMessagesWithPage,
  useUpdateConversationIsPinned,
} from '@/hooks/use-conversation'
import { useAudioPlayer, useAudioToText } from '@/hooks/use-audio'
import UpdateNameModal from './components/UpdateNameModal.vue'
import ConversationListItem from './components/ConversationListItem.vue'
import HumanMessage from '@/components/HumanMessage.vue'
import AiMessage from '@/components/AiMessage.vue'
import { useGenerateSuggestedQuestions } from '@/hooks/use-ai'
import { QueueEvent } from '@/config'
import { uploadImage } from '@/services/upload-file'
import AudioRecorder from 'js-audio-recorder'

// 1.定义页面所需数据
const route = useRoute()
const updateConversationNameModalVisible = ref(false)
const updateConversationNameId = ref('')
const newConversation = ref<any>(null)
const selectedConversation = ref('')
const query = ref('')
const image_urls = ref<string[]>([])
const fileInput = ref<any>(null)
const uploadFileLoading = ref(false)
const isRecording = ref(false) // 是否正在录音
const audioBlob = ref<any>(null) // 录音后音频的blob
let recorder: any = null // RecordRTC实例
const message_id = ref('')
const task_id = ref('')
const scroller = ref<any>(null)
const scrollHeight = ref(0)
const accountStore = useAccountStore()
const { loading: getWebAppLoading, web_app, loadWebApp } = useGetWebApp()
const {
  loading: getWebAppConversationsLoading,
  pinned_conversations,
  unpinned_conversations,
  loadWebAppConversations,
} = useGetAppConversations()
const { handleDeleteConversation } = useDeleteConversation()
const { messages, loadConversationMessagesWithPage } = useGetConversationMessagesWithPage()
const { handleUpdateConversationIsPinned } = useUpdateConversationIsPinned()
const { loading: webAppChatLoading, handleWebAppChat } = useWebAppChat()
const { loading: stopWebAppChatLoading, handleStopWebAppChat } = useStopWebAppChat()
const { suggested_questions, handleGenerateSuggestedQuestions } = useGenerateSuggestedQuestions()
const can_image_input = computed(() => {
  if (web_app.value) {
    return web_app.value?.app_config?.features?.includes('image_input')
  }
  return false
})
const opening_questions = computed(() => {
  return (
    web_app.value?.app_config?.opening_questions?.filter((item: any) => item.trim() !== '') ?? []
  )
})
const can_speech_to_text = computed(() => {
  if (web_app.value) {
    return web_app.value?.app_config?.speech_to_text?.enable
  }
  return false
})
const { loading: audioToTextLoading, text, handleAudioToText } = useAudioToText()
const { startAudioStream, stopAudioStream } = useAudioPlayer()

// 2.定义会话计算属性，动态展示当前选中会话
const conversation = computed(() => {
  // 2.1 判断是否选中新会话，如果是则直接返回新会话数据
  if (selectedConversation.value === 'new_conversation') {
    return newConversation.value
  } else if (selectedConversation.value !== '') {
    // 2.2 查询置顶会话数据，如果不为空则直接返回
    let item = pinned_conversations.value.find((item) => item.id === selectedConversation.value)
    if (item) return item

    // 2.3 置顶会话查询不到数据，则查询非置顶数据
    return unpinned_conversations.value.find((item) => item.id === selectedConversation.value)
  }
  return null
})

// 3.定义保存滚动高度函数
const saveScrollHeight = () => {
  scrollHeight.value = scroller.value.$el.scrollHeight
}

// 4.定义修改指定状态处理器
const changeIsPinned = async (idx: number, origin_is_pinned: boolean) => {
  // 3.1 根据idx提取数据
  const conversation: any = origin_is_pinned
    ? pinned_conversations.value[idx]
    : unpinned_conversations.value[idx]

  // 3.2 调用hooks发起api请求
  await handleUpdateConversationIsPinned(conversation.id, !origin_is_pinned, () => {
    // 3.3 执行成功调用回调，更新会话位置
    if (origin_is_pinned) {
      pinned_conversations.value.splice(idx, 1)
      unpinned_conversations.value.push(conversation)
    } else {
      unpinned_conversations.value.splice(idx, 1)
      pinned_conversations.value.push(conversation)
    }
  })
}

// 5.定义修改会话名字处理器
const updateName = (idx: number, origin_is_pinned: boolean) => {
  // 4.1 根据idx提取数据
  const conversation: any = origin_is_pinned
    ? pinned_conversations.value[idx]
    : unpinned_conversations.value[idx]

  // 4.2 更新响应数据状态
  updateConversationNameId.value = conversation.id
  updateConversationNameModalVisible.value = true
}

// 6.定义更新会话名字成功处理器
const successUpdateNameCallback = (conversation_id: string, conversation_name: string) => {
  // 5.1 先查询置顶会话对应的记录索引
  let idx = pinned_conversations.value.findIndex((item) => item.id === conversation_id)

  // 5.2 判断索引值是否为-1
  if (idx !== -1) {
    // 5.2 置顶会话
    pinned_conversations.value[idx]!['name'] = conversation_name
  } else {
    idx = unpinned_conversations.value.findIndex((item) => item.id === conversation_id)
    if (idx !== -1) unpinned_conversations.value[idx]!['name'] = conversation_name
  }
}

// 7.定义删除回话处理器
const deleteConversation = async (idx: number, origin_is_pinned: boolean) => {
  // 6.1 根据idx提取数据
  const conversation = origin_is_pinned
    ? pinned_conversations.value[idx]
    : unpinned_conversations.value[idx]

  // 6.2 调用hooks发起请求
  handleDeleteConversation(conversation!.id, () => {
    // 6.3 执行成功调用回调，删除回话
    if (origin_is_pinned) {
      pinned_conversations.value.splice(idx, 1)
    } else {
      unpinned_conversations.value.splice(idx, 1)
    }
  })
}

// 8.定义新增会话处理器
const addConversation = () => {
  // 7.1 将选择会话切换到new_conversation
  selectedConversation.value = 'new_conversation'

  // 7.2 如果没有新会话则创建一个
  if (!newConversation.value) {
    newConversation.value = {
      id: '',
      name: '新对话',
      summary: '',
      created_at: 0,
    }
  }
}

// 9.定义还原滚动高度函数
const restoreScrollPosition = () => {
  scroller.value.$el.scrollTop = scroller.value.$el.scrollHeight - scrollHeight.value
}

// 10.定义滚动函数
const handleScroll = async (event: UIEvent) => {
  const { scrollTop } = event.target as HTMLElement
  if (scrollTop <= 0 && !webAppChatLoading.value) {
    saveScrollHeight()
    await loadConversationMessagesWithPage(conversation.value.id, false)
    restoreScrollPosition()
  }
}

// 11.定义输入框提交函数
const handleSubmit = async () => {
  // 11.1 检测是否录入了query，如果没有则结束
  if (query.value.trim() === '') {
    Message.warning('用户提问不能为空')
    return
  }

  // 11.2 检测上次提问是否结束，如果没结束不能发起新提问
  if (webAppChatLoading.value) {
    Message.warning('上一次提问还未结束，请稍等')
    return
  }

  // 11.3 满足条件，处理正式提问的前置工作，涵盖：清空建议问题、删除消息id、任务id
  suggested_questions.value = []
  message_id.value = ''
  task_id.value = ''
  // stopAudioStream()
  const selectedConversationTmp = cloneDeep(selectedConversation.value)

  // 11.4 往消息列表中添加基础人类消息
  messages.value.unshift({
    id: '',
    conversation_id: '',
    query: query.value,
    image_urls: image_urls.value,
    answer: '',
    total_token_count: 0,
    latency: 0,
    agent_thoughts: [],
    created_at: 0,
  })

  // 11.5 初始化推理过程数据，并清空输入数据
  let position = 0
  const humanQuery = query.value
  const humanImageUrls = image_urls.value
  query.value = ''
  image_urls.value = []

  // 11.6 调用hooks发起请求
  const req = {
    conversation_id:
      selectedConversation.value === 'new_conversation' ? '' : selectedConversation.value,
    query: humanQuery,
    image_urls: humanImageUrls,
  }
  await handleWebAppChat(String(route.params?.token), req, (event_response) => {
    // 11.7 提取流式事件响应数据以及事件名称
    const event = event_response?.event
    const data = event_response?.data
    const event_id = data?.id
    let agent_thoughts = messages.value[0]!.agent_thoughts

    // 11.8 初始化数据检测与赋值
    if (message_id.value === '' && data?.message_id) {
      task_id.value = data?.task_id
      message_id.value = data?.message_id
      messages.value[0]!.id = data?.message_id
      messages.value[0]!.conversation_id = data?.conversation_id
    }

    // 11.9 循环处理得到的事件，记录除ping之外的事件
    if (event !== QueueEvent.ping) {
      // 11.10 除了agent_message数据为叠加，其他均为覆盖
      if (event === QueueEvent.agentMessage) {
        // 5.11 获取数据索引并检测是否存在
        const agent_thought_idx = agent_thoughts.findIndex((item) => item?.id === event_id)

        // 5.12 数据不存在则添加
        if (agent_thought_idx === -1) {
          position += 1
          agent_thoughts.push({
            id: event_id,
            position: position,
            event: data?.event,
            thought: data?.thought,
            observation: data?.observation,
            tool: data?.tool,
            tool_input: data?.tool_input,
            latency: data?.latency,
            created_at: 0,
          })
        } else {
          // 5.13 存在数据则叠加
          agent_thoughts[agent_thought_idx] = {
            ...agent_thoughts[agent_thought_idx]!,
            thought: agent_thoughts[agent_thought_idx]!.thought + data?.thought,
            latency: data?.latency,
          }
        }

        // 5.14 更新/添加answer答案
        messages.value[0]!.answer += data?.thought
        messages.value[0]!.latency = data?.latency
        messages.value[0]!.total_token_count = data?.total_token_count
      } else if (event === QueueEvent.error) {
        // 5.15 事件为error，将错误信息(observation)填充到消息答案中进行展示
        messages.value[0]!.answer = data?.observation
      } else if (event === QueueEvent.timeout) {
        // 5.16 事件为timeout，则人工提示超时信息
        messages.value[0]!.answer = '当前Agent执行已超时，无法得到答案，请重试'
      } else {
        // 11.11 处理其他类型的事件，直接填充覆盖数据
        position += 1
        agent_thoughts.push({
          id: event_id,
          position: position,
          event: data?.event,
          thought: data?.thought,
          observation: data?.observation,
          tool: data?.tool,
          tool_input: data?.tool_input,
          latency: data?.latency,
          created_at: 0,
        })
      }

      // 11.12 更新agent_thoughts
      messages.value[0]!.agent_thoughts = agent_thoughts

      scroller.value.scrollToBottom()
    }
  })

  // 11.13 消息正常判断结束的情况下，判断是否是新会话
  if (messages.value.length > 0) {
    if (selectedConversationTmp === 'new_conversation') {
      // 11.14 将newConversation填充到会话列表中
      unpinned_conversations.value.unshift({
        id: messages.value[0]!.conversation_id,
        name: 'New Conversation',
        summary: '',
        created_at: messages.value[0]!.created_at,
      })
      // 11.15 清空newConversation并修改选中
      newConversation.value = null
      if (selectedConversation.value === 'new_conversation') {
        selectedConversation.value = messages.value[0]!.conversation_id
      }
    }
    // 11.16 判断是否开启建议问题生成，如果开启了则发起api请求获取数据
    if (web_app.value?.app_config?.suggested_after_answer.enable && message_id.value) {
      handleGenerateSuggestedQuestions(message_id.value)
      setTimeout(() => scroller.value && scroller.value.scrollToBottom(), 100)
    }

    // 11.17 判断是否自动播放
    if (
      web_app.value?.app_config?.text_to_speech.enable &&
      web_app.value?.app_config?.text_to_speech.auto_play &&
      message_id.value
    ) {
      startAudioStream(message_id.value)
    }
  }
}

// 12.定义切换会话处理器
const changeConversation = async (conversation_id: string) => {
  // 12.1 先暂停并清空会话
  await handleStop()

  // 12.2 修改激活选项
  selectedConversation.value = conversation_id
}

// 13.定义停止会话函数
const handleStop = async () => {
  // 13.1 如果没有任务id或者未在加载中，则直接停止
  if (task_id.value === '' || !webAppChatLoading.value) return

  // 13.2 调用api接口中断请求
  await handleStopWebAppChat(String(route.params?.token), task_id.value)
}

// 14.定义问题提交函数
const handleSubmitQuestion = async (question: string) => {
  // 14.1 将问题同步到query中
  query.value = question

  // 14.2 触发handleSubmit函数
  await handleSubmit()
}

// 8.定义文件上传触发器
const triggerFileInput = () => {
  // 1.检测上传的图片数量是否超过5
  if (image_urls.value.length >= 5) {
    Message.error('对话上传图片数量不能超过5张')
    return
  }

  // 2.满足条件触发上传
  fileInput.value.click()
}

// 15.定义文件变化监听器
const handleFileChange = async (event: Event) => {
  // 1.判断是否在上传中
  if (uploadFileLoading.value) return

  // 2.获取当前选中的图片
  const input = event.target as HTMLInputElement
  const selectedFile = input.files?.[0]
  if (selectedFile) {
    try {
      // 3.调用API接口上传图片
      uploadFileLoading.value = true
      const resp = await uploadImage(selectedFile)
      image_urls.value.push(resp.data.image_url)
      Message.success('上传图片成功')
    } finally {
      uploadFileLoading.value = false
    }
  }
}

// 16.开始录音处理器
const handleStartRecord = async () => {
  // 10.1 创建AudioRecorder
  recorder = new AudioRecorder()

  // 10.2 开始录音并记录录音状态
  try {
    isRecording.value = true
    await recorder.start()
    Message.success('开始录音')
  } catch (error: any) {
    Message.error(`录音失败: ${error}`)
    isRecording.value = false
  }
}

// 17.停止录音处理器
const handleStopRecord = async () => {
  if (recorder) {
    try {
      // 11.1 等待录音停止并获取录音数据
      await recorder.stop()
      audioBlob.value = recorder.getWAVBlob()

      // 11.2 调用语音转文本处理器并将文本填充到query中
      await handleAudioToText(audioBlob.value)
      Message.success('语音转文本成功')
      query.value = text.value
    } catch (error: any) {
      Message.error(`录音失败: ${error}`)
    } finally {
      isRecording.value = false // 标记为停止录音
    }
  }
}

// 18.监听选择会话变化
watch(
  () => selectedConversation.value,
  async (newValue) => {
    // 15.1 判断数据的类型
    if (newValue === 'new_conversation') {
      // 15.2 点击了新会话，将消息清空
      messages.value = []
    } else if (newValue !== '') {
      // 15.3 选择了已有会话，获取对应会话的消息列表
      await loadConversationMessagesWithPage(newValue, true)
      await nextTick(() => {
        // 15.4 确保在视图更新完成后执行滚动操作
        if (scroller.value) {
          scroller.value.scrollToBottom()
        }
      })
    }

    // 15.5 切换会话时停止播放音频
    // stopAudioStream()
  },
  { immediate: true },
)

// 17.页面挂在完毕请求数据
onMounted(async () => {
  // 16.1 提取WebApp凭证标识
  const token = String(route.params?.token)

  // 16.2 异步加载数据
  await Promise.all([loadWebApp(token), loadWebAppConversations(token)])

  // 16.3 默认新增空白会话
  addConversation()
})

// 18.页面卸载后停止播放
onUnmounted(() => {
  stopAudioStream()
})
</script>

<template>
  <div class="flex h-screen w-full overflow-hidden bg-white">
    <!-- 左侧会话记录 -->
    <aside class="flex w-64 shrink-0 flex-col border-r border-gray-200 bg-gray-50">
      <!-- 顶部应用信息 -->
      <div class="flex shrink-0 items-center gap-3 px-4 pb-3 pt-4">
        <a-avatar
          :size="36"
          shape="square"
          :image-url="web_app?.icon"
          class="shrink-0 rounded-lg"
        />
        <div class="min-w-0 flex-1">
          <a-skeleton
            v-if="getWebAppLoading"
            animation
          >
            <a-skeleton-line
              :rows="1"
              :line-height="20"
              :line-spacing="4"
            />
          </a-skeleton>
          <div
            v-else
            class="truncate text-sm font-semibold text-gray-800"
          >
            {{ web_app?.name }}
          </div>
        </div>
      </div>
      <!-- 新增会话 -->
      <div class="shrink-0 px-4 pb-3">
        <a-button
          type="primary"
          long
          class="rounded-xl !border-0 !bg-gradient-to-r !from-blue-500 !to-indigo-500 shadow-sm transition-all duration-200 hover:!from-blue-600 hover:!to-indigo-600 hover:shadow-md"
          @click="addConversation"
        >
          <template #icon>
            <icon-edit />
          </template>
          新增会话
        </a-button>
      </div>
      <!-- 会话列表 -->
      <div class="scrollbar-w-none flex-1 overflow-y-auto px-2 pb-4">
        <!-- 空白骨架屏 -->
        <a-skeleton
          v-if="getWebAppConversationsLoading"
          animation
        >
          <a-skeleton-line
            :rows="6"
            :line-height="40"
            :line-spacing="8"
          />
        </a-skeleton>
        <template v-else>
          <!-- 置顶会话 -->
          <section v-if="pinned_conversations.length > 0">
            <div class="px-2 pb-1.5 pt-2 text-xs font-medium text-gray-400">置顶会话</div>
            <div class="flex flex-col gap-0.5">
              <conversation-list-item
                v-for="(conversation, idx) in pinned_conversations"
                :key="conversation.id"
                :conversation="conversation"
                :selected="selectedConversation === conversation.id"
                :pinned="true"
                @select="() => changeConversation(conversation.id)"
                @toggle-pin="() => changeIsPinned(idx, true)"
                @rename="() => updateName(idx, true)"
                @delete="() => deleteConversation(idx, true)"
              />
            </div>
          </section>
          <!-- 对话列表 -->
          <section>
            <div class="px-2 pb-1.5 pt-2 text-xs font-medium text-gray-400">对话列表</div>
            <div class="flex flex-col gap-0.5">
              <conversation-list-item
                v-if="newConversation"
                :conversation="newConversation"
                :selected="selectedConversation === 'new_conversation'"
                :show-actions="false"
                @select="() => changeConversation('new_conversation')"
              />
              <conversation-list-item
                v-for="(conversation, idx) in unpinned_conversations"
                :key="conversation.id"
                :conversation="conversation"
                :selected="selectedConversation === conversation.id"
                :pinned="false"
                @select="() => changeConversation(conversation.id)"
                @toggle-pin="() => changeIsPinned(idx, false)"
                @rename="() => updateName(idx, false)"
                @delete="() => deleteConversation(idx, false)"
              />
            </div>
          </section>
          <!-- 空会话列表 -->
          <div
            v-if="
              !newConversation &&
              pinned_conversations.length === 0 &&
              unpinned_conversations.length === 0
            "
            class="flex flex-col items-center gap-2 py-12 text-gray-400"
          >
            <icon-empty :size="40" />
            <div class="text-xs">暂无会话</div>
          </div>
        </template>
      </div>
    </aside>
    <!-- 右侧对话窗口 -->
    <main class="flex min-w-0 flex-1 flex-col bg-white">
      <!-- 顶部会话名称 -->
      <header class="flex h-14 shrink-0 items-center justify-center border-b border-gray-100 px-6">
        <div class="flex min-w-0 items-center gap-2">
          <span class="h-2 w-2 shrink-0 rounded-full bg-blue-500"></span>
          <div class="truncate text-sm font-medium text-gray-700">
            {{ conversation?.name || '新对话' }}
          </div>
        </div>
      </header>
      <!-- 对话消息列表 -->
      <div
        v-if="messages.length > 0"
        class="flex min-h-0 flex-1 flex-col"
      >
        <div class="min-h-0 flex-1">
          <dynamic-scroller
            ref="scroller"
            :items="messages.slice().reverse()"
            :min-item-size="1"
            @scroll="handleScroll"
            class="scrollbar-w-none h-full"
          >
            <template v-slot="{ item, active }">
              <dynamic-scroller-item
                :item="item"
                :active="active"
                :data-index="item.id"
              >
                <div class="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-6">
                  <human-message
                    :query="item.query"
                    :image_urls="item.image_urls"
                    :account="accountStore.account"
                  />
                  <!-- :enable_text_to_speech="web_app?.app_config?.text_to_speech?.enable" -->
                  <ai-message
                    :message_id="item.id"
                    :agent_thoughts="item.agent_thoughts"
                    :answer="item.answer"
                    :app="{ name: web_app.name, icon: web_app.icon }"
                    :suggested_questions="item.id === message_id ? suggested_questions : []"
                    :loading="item.id === message_id && webAppChatLoading"
                    :latency="item.latency"
                    :total_token_count="item.total_token_count"
                    @select-suggested-question="handleSubmitQuestion"
                    message_class="max-w-[640px] !bg-gray-50"
                  />
                </div>
              </dynamic-scroller-item>
            </template>
          </dynamic-scroller>
        </div>
        <!-- 停止调试会话 -->
        <div
          v-if="task_id && webAppChatLoading"
          class="flex shrink-0 items-center justify-center py-3"
        >
          <a-button
            :loading="stopWebAppChatLoading"
            class="rounded-full px-4"
            @click="handleStop"
          >
            <template #icon>
              <icon-poweroff />
            </template>
            停止响应
          </a-button>
        </div>
      </div>
      <!-- 对话列表为空时展示的对话开场白 -->
      <div
        v-else
        class="scrollbar-w-none min-h-0 flex-1 overflow-y-auto"
      >
        <div
          class="mx-auto flex min-h-full w-full max-w-2xl flex-col items-center justify-center gap-4 px-6 py-16"
        >
          <!-- 应用图标与名称 -->
          <a-avatar
            :size="56"
            shape="square"
            :image-url="web_app?.icon"
            class="rounded-2xl shadow-sm"
          />
          <div class="text-xl font-semibold text-gray-800">{{ web_app?.name }}</div>
          <!-- 对话开场白 -->
          <div
            v-if="web_app?.app_config?.opening_statement"
            class="w-full rounded-2xl border border-gray-100 bg-gray-50 px-6 py-5 text-center text-sm leading-6 text-gray-600"
          >
            {{ web_app?.app_config?.opening_statement }}
          </div>
          <!-- 开场白建议问题 -->
          <div
            v-if="opening_questions.length > 0"
            class="flex w-full flex-wrap items-center justify-center gap-2"
          >
            <div
              v-for="(opening_question, idx) in opening_questions"
              :key="idx"
              class="cursor-pointer rounded-full border border-gray-200 px-4 py-1.5 text-sm text-gray-600 transition-all duration-150 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-600"
              @click="async () => await handleSubmitQuestion(opening_question)"
            >
              {{ opening_question }}
            </div>
          </div>
        </div>
      </div>
      <!-- 对话输入框 -->
      <div class="shrink-0 pb-3">
        <div class="mx-auto w-full max-w-3xl px-4">
          <div
            class="flex flex-col justify-end gap-2 rounded-3xl border border-gray-200 bg-white px-4 py-2.5 shadow-sm transition-all duration-300 focus-within:border-blue-400 focus-within:shadow-[0_0_0_3px_rgba(59,130,246,0.12)]"
          >
            <!-- 图片列表 -->
            <div
              v-if="image_urls.length > 0 && can_image_input"
              class="flex flex-wrap items-center gap-2"
            >
              <div
                v-for="(image_url, idx) in image_urls"
                :key="image_url"
                class="group relative h-12 w-12 cursor-pointer overflow-hidden rounded-xl"
              >
                <a-avatar
                  shape="square"
                  :size="48"
                  :image-url="image_url"
                  class="h-full w-full"
                />
                <div
                  class="absolute inset-0 hidden items-center justify-center bg-black/40 group-hover:flex"
                  @click="() => image_urls.splice(idx, 1)"
                >
                  <icon-close class="text-white" />
                </div>
              </div>
            </div>
            <div class="flex items-center gap-1.5">
              <input
                v-model="query"
                type="text"
                class="min-w-0 flex-1 bg-transparent text-sm text-gray-800 outline-none placeholder:text-gray-400"
                :placeholder="`给 &quot;${web_app?.name ?? '&quot;聊天机器人&quot;'}&quot; 发送消息`"
                @keyup.enter="handleSubmit"
              />
              <!-- 上传图片输入框 -->
              <input
                type="file"
                ref="fileInput"
                accept="image/*"
                @change="handleFileChange"
                class="hidden"
              />
              <a-button
                v-if="can_image_input"
                :loading="uploadFileLoading"
                size="mini"
                type="text"
                shape="circle"
                class="shrink-0 !text-gray-500 transition-colors duration-150 hover:!bg-blue-50 hover:!text-blue-600"
                @click="triggerFileInput"
              >
                <template #icon>
                  <icon-plus />
                </template>
              </a-button>
              <!-- 语音转文本加载按钮 -->
              <template v-if="!can_speech_to_text"></template>
              <template v-else-if="audioToTextLoading">
                <a-button
                  size="mini"
                  type="text"
                  shape="circle"
                >
                  <template #icon>
                    <icon-loading />
                  </template>
                </a-button>
              </template>
              <template v-else>
                <!-- 开始音频录制按钮 -->
                <a-button
                  v-if="!isRecording"
                  size="mini"
                  type="text"
                  shape="circle"
                  class="!text-gray-700"
                  @click="handleStartRecord"
                >
                  <template #icon>
                    <icon-voice />
                  </template>
                </a-button>
                <!-- 结束音频录制按钮 -->
                <a-button
                  v-else
                  size="mini"
                  type="text"
                  shape="circle"
                  @click="handleStopRecord"
                >
                  <template #icon>
                    <icon-pause />
                  </template>
                </a-button>
              </template>
              <a-button
                :loading="webAppChatLoading"
                type="primary"
                shape="circle"
                class="shrink-0 !h-8 !w-8 !border-0 !bg-gradient-to-r !from-blue-500 !to-indigo-500 !shadow-md !shadow-blue-200 transition-all duration-300 hover:!from-blue-600 hover:!to-indigo-600 hover:!shadow-lg hover:!shadow-blue-300"
                @click="handleSubmit"
              >
                <template #icon>
                  <icon-send :size="16" />
                </template>
              </a-button>
            </div>
          </div>
          <!-- 底部提示信息 -->
          <div class="pb-1 pt-2.5 text-center text-xs text-gray-400">
            内容由AI生成，无法确保真实准确，仅供参考。
          </div>
        </div>
      </div>
    </main>
    <!-- 修改会话名字模态窗 -->
    <update-name-modal
      v-model:visible="updateConversationNameModalVisible"
      v-model:conversation_id="updateConversationNameId"
      :success_callback="successUpdateNameCallback"
    />
  </div>
</template>

<style scoped></style>
