<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue';
const props = defineProps<{ request: (path: string, body?: any) => Promise<any> }>();
const emit = defineEmits<{ open: [id: number] }>();
const rows = ref<any[]>([]),
  error = ref(''),
  busy = ref(false);
let timer: ReturnType<typeof setInterval> | undefined;
async function load() {
  if (busy.value) return;
  busy.value = true;
  try {
    rows.value = (await props.request('appointment-notifications/?unread=true')).results;
    error.value = '';
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function open(row: any) {
  emit('open', row.appointment_id);
  try {
    await props.request(`appointment-notifications/${row.id}/read/`, {});
    row.read_at = new Date().toISOString();
  } catch (e: any) {
    error.value = e.message;
  }
}
onMounted(() => {
  load();
  timer = setInterval(() => {
    if (!document.hidden) load();
  }, 60000);
});
onBeforeUnmount(() => {
  if (timer) clearInterval(timer);
});
</script>
<template>
  <section
    v-if="rows.some((row) => !row.read_at) || error"
    class="appointment-alerts"
    aria-label="Notifications de rendez-vous"
  >
    <h3>Notifications de rendez-vous</h3>
    <p v-if="error" role="alert">{{ error }}</p>
    <button
      v-for="row in rows.filter((row) => !row.read_at)"
      :key="row.id"
      class="secondary"
      @click="open(row)"
    >
      {{ row.label }} · {{ row.contact_name }} ·
      {{ new Date(row.starts_at).toLocaleString('fr-CA', { timeZone: 'America/Toronto' }) }} —
      Consulter
    </button>
  </section>
</template>
<style scoped>
.appointment-alerts {
  padding: 16px;
  margin: 16px 0;
  border: 1px solid #dce4f2;
  border-radius: 16px;
  background: #f4f6ff;
}
.appointment-alerts button {
  display: block;
  margin: 8px 0;
}
</style>
