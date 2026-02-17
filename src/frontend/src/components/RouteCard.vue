<template>
  <div class="route-card">
    <div class="route-header">
      <div>
        <p class="route-title">{{ domains }}</p>
        <p class="route-upstream">{{ upstreamLabel }}</p>
      </div>
      <span class="badge" :class="route.enabled ? 'enabled' : 'disabled'">
        {{ route.enabled ? 'Enabled' : 'Disabled' }}
      </span>
    </div>
    <div class="route-meta">
      <template v-if="meta.length">
        <span v-for="item in meta" :key="item" class="tag">{{ item }}</span>
      </template>
      <span v-else class="tag">Default</span>
    </div>
    <div v-if="route.path_routes && route.path_routes.length" class="path-list">
      <div v-for="path in route.path_routes" :key="path.id" class="path-item">
        <span>{{ path.path }}</span>
        <span>{{ path.upstream.scheme }}://{{ path.upstream.host }}:{{ path.upstream.port }}</span>
      </div>
    </div>
    <div class="route-actions">
      <button class="ghost" @click="$emit('toggle', route)">
        {{ route.enabled ? 'Отключить' : 'Включить' }}
      </button>
      <button class="ghost" @click="$emit('edit', route)">Редактировать</button>
      <button class="danger" @click="$emit('delete', route)">Удалить</button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  route: {
    type: Object,
    required: true,
  },
})

defineEmits(['toggle', 'edit', 'delete'])

const domains = computed(() => (props.route.domains || []).join(', '))

const upstreamLabel = computed(() => {
  const upstream = props.route.upstream || {}
  return `${upstream.scheme || 'http'}://${upstream.host || ''}:${upstream.port || ''}`
})

const meta = computed(() => {
  const items = []
  if (props.route.request_body_max_mb !== null && props.route.request_body_max_mb !== undefined) {
    items.push(`Body: ${props.route.request_body_max_mb}MB`)
  }
  if (props.route.timeouts && Object.keys(props.route.timeouts).length) {
    const parts = []
    if (props.route.timeouts.connect) parts.push(`c${props.route.timeouts.connect}s`)
    if (props.route.timeouts.read) parts.push(`r${props.route.timeouts.read}s`)
    if (props.route.timeouts.write) parts.push(`w${props.route.timeouts.write}s`)
    items.push(`Timeouts: ${parts.join(' ')}`)
  }
  return items
})
</script>
