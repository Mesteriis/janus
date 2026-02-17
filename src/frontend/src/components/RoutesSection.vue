<template>
  <section class="routes">
    <div class="section-header">
      <h2>Маршруты</h2>
      <button class="ghost" @click="$emit('refresh')">Обновить</button>
    </div>
    <div v-if="loading" class="empty">Загружаем маршруты...</div>
    <div v-else-if="routes.length === 0" class="empty">Маршрутов пока нет.</div>
    <div v-else class="routes-grid">
      <RouteCard
        v-for="route in routes"
        :key="route.id"
        :route="route"
        @toggle="$emit('toggle', $event)"
        @edit="$emit('edit', $event)"
        @delete="$emit('delete', $event)"
      />
    </div>
  </section>
</template>

<script setup>
import RouteCard from './RouteCard.vue'

defineProps({
  routes: {
    type: Array,
    required: true,
  },
  loading: {
    type: Boolean,
    required: true,
  },
})

defineEmits(['refresh', 'toggle', 'edit', 'delete'])
</script>
