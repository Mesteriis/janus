<template>
  <div v-if="open" class="modal-backdrop" @click.self="$emit('cancel')">
    <div class="modal">
      <h3>{{ title }}</h3>
      <p>{{ message }}</p>
      <div class="modal-actions">
        <button class="ghost" type="button" @click="$emit('cancel')">
          {{ cancelLabel }}
        </button>
        <button class="danger" type="button" @click="$emit('confirm')">
          {{ confirmLabel }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  open: {
    type: Boolean,
    required: true,
  },
  title: {
    type: String,
    required: true,
  },
  message: {
    type: String,
    required: true,
  },
  confirmLabel: {
    type: String,
    default: 'Удалить',
  },
  cancelLabel: {
    type: String,
    default: 'Отмена',
  },
})

defineEmits(['confirm', 'cancel'])
</script>
