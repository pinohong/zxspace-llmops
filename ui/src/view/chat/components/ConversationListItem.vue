<script setup lang="ts">
// 1.定义自定义组件所需数据
const props = defineProps({
  conversation: {
    type: Object,
    required: true,
  },
  selected: { type: Boolean, default: false },
  pinned: { type: Boolean, default: false },
  showActions: { type: Boolean, default: true },
})
const emits = defineEmits(['select', 'toggle-pin', 'rename', 'delete'])
</script>

<template>
  <div
    class="group flex h-9 cursor-pointer select-none items-center gap-2 rounded-lg pl-3 pr-1.5 transition-all duration-150"
    :class="
      props.selected
        ? 'bg-blue-50 font-medium text-blue-600'
        : 'text-gray-700 hover:bg-gray-100 hover:text-gray-900'
    "
    @click="emits('select')"
  >
    <icon-message
      class="shrink-0"
      :class="props.selected ? 'text-blue-500' : 'text-gray-400'"
    />
    <div class="min-w-0 flex-1 truncate text-sm">{{ props.conversation?.name }}</div>
    <a-dropdown
      v-if="props.showActions"
      position="br"
      @click.stop
    >
      <a-button
        size="mini"
        type="text"
        class="shrink-0 !bg-transparent !text-inherit opacity-0 transition-opacity duration-150 group-hover:opacity-100"
      >
        <template #icon>
          <icon-more />
        </template>
      </a-button>
      <template #content>
        <a-doption @click="emits('toggle-pin')">
          {{ props.pinned ? '取消置顶' : '置顶会话' }}
        </a-doption>
        <a-doption @click="emits('rename')">重命名</a-doption>
        <a-doption
          class="text-red-600"
          @click="emits('delete')"
        >
          删除
        </a-doption>
      </template>
    </a-dropdown>
  </div>
</template>

<style scoped></style>
