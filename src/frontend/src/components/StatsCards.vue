<template>
  <div class="stats">
    <div class="stat">
      <span class="stat-label">Активные</span>
      <span class="stat-value">{{ active }}</span>
    </div>
    <div class="stat">
      <span class="stat-label">Отключены</span>
      <span class="stat-value">{{ disabled }}</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  active: {
    type: Number,
    required: true,
  },
  disabled: {
    type: Number,
    required: true,
  },
})
</script>
