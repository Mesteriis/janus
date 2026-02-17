<template>
  <form @submit.prevent="submit" novalidate>
    <div class="field">
      <label for="cf-hostname">Hostname-исключение</label>
      <input id="cf-hostname" v-model="form.hostname" type="text" placeholder="ssh.sh-inc.ru" required />
      <small>Для SSH используйте отдельный hostname (например ssh.domain).</small>
    </div>
    <div class="field">
      <label for="cf-service">Service</label>
      <input id="cf-service" v-model="form.service" type="text" placeholder="ssh://host:22" />
      <small>Пример для SSH: ssh://host:22</small>
      <small>DNS запись должна указывать на tunnel в Cloudflare.</small>
    </div>
    <div class="field inline">
      <label class="toggle">
        <input type="checkbox" v-model="form.enabled" />
        <span>Включен</span>
      </label>
    </div>
    <button class="primary" type="submit">Сохранить</button>
    <p class="error">{{ displayError }}</p>
  </form>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'

const props = defineProps({
  defaultService: {
    type: String,
    default: '',
  },
  error: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['submit'])

const localError = ref('')

const form = reactive({
  hostname: '',
  service: '',
  enabled: true,
})

const displayError = computed(() => props.error || localError.value)

function reset() {
  form.hostname = ''
  form.service = ''
  form.enabled = true
  localError.value = ''
}

function prefill(entry) {
  form.hostname = entry.hostname
  form.service = entry.service
  form.enabled = Boolean(entry.enabled)
  localError.value = ''
}

function submit() {
  localError.value = ''
  if (!form.hostname.trim()) {
    localError.value = 'Укажите hostname'
    return
  }
  emit(
    'submit',
    {
      hostname: form.hostname.trim(),
      service: form.service.trim(),
      enabled: form.enabled,
    },
    reset
  )
}

defineExpose({ reset, prefill })
</script>
