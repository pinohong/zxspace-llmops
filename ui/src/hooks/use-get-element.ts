import { nextTick } from 'vue'

export const useGetRect = async (targetRef: any) => {
  await nextTick()
  if (!targetRef.value) return null
  let el: HTMLElement
  // 判断是否为组件实例（存在 $el）
  if ('$el' in targetRef.value) {
    el = targetRef.value.$el as HTMLElement
  } else {
    el = targetRef.value
  }
  const rect = el.getBoundingClientRect()
  return {
    rect: rect,
    listHeight: window.innerHeight - rect.top
  }
}
