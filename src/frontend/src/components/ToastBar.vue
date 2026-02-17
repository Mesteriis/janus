<template>
  <div v-if="visible" class="toast">{{ message }}</div>
</template>

<script setup>
defineProps({
  visible: {
    type: Boolean,
    required: true,
  },
  message: {
    type: String,
    required: true,
  },
})
</script>
