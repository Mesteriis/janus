<template>
  <div class="route-card">
    <div class="route-header">
      <div>
        <p class="route-title">{{ entry.hostname }}</p>
        <p class="route-upstream">{{ entry.service }}</p>
      </div>
      <span class="badge" :class="entry.enabled ? 'enabled' : 'disabled'">
        {{ entry.enabled ? 'Enabled' : 'Disabled' }}
      </span>
    </div>
    <div class="route-actions">
      <button class="ghost" @click="$emit('toggle', entry)">
        {{ entry.enabled ? 'Отключить' : 'Включить' }}
      </button>
      <button class="ghost" @click="$emit('edit', entry)">Редактировать</button>
      <button class="danger" @click="$emit('delete', entry)">Удалить</button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  entry: {
    type: Object,
    required: true,
  },
})

defineEmits(['toggle', 'edit', 'delete'])
</script>
