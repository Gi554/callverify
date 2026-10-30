<script setup lang="ts">
import { onMounted, ref } from 'vue';
const props = defineProps<{
  request: (path: string, body?: any) => Promise<any>;
  assignmentId?: number;
}>();
const emit = defineEmits<{ changed: [] }>();
const url = ref(''),
  revision = ref(0),
  busy = ref(false),
  ready = ref(false),
  error = ref(''),
  message = ref('');
const endpoint = props.assignmentId
  ? `assignments/${props.assignmentId}/booking-link/`
  : 'advisor-booking-link/';
async function load() {
  busy.value = true;
  error.value = '';
  ready.value = false;
  try {
    const data = await props.request(endpoint);
    url.value = data.url;
    revision.value = data.revision;
    ready.value = true;
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function save() {
  if (!ready.value || busy.value) return;
  busy.value = true;
  error.value = '';
  message.value = '';
  try {
    const data = await props.request(endpoint, { url: url.value.trim(), revision: revision.value });
    url.value = data.url;
    revision.value = data.revision;
    message.value = 'Lien enregistré pour les setters associés à ce conseiller.';
    emit('changed');
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
onMounted(load);
</script>
<template>
  <form class="booking-link-settings" @submit.prevent="save">
    <h3>Lien de réservation du conseiller</h3>
    <p>
      Ajoutez votre page Microsoft Bookings, Calendly ou votre autre outil de réservation. Les
      setters l’ouvriront dans un nouvel onglet.
    </p>
    <label
      >Page de réservation
      <input
        v-model="url"
        type="url"
        maxlength="2048"
        placeholder="https://…"
        :disabled="busy || !ready"
      />
    </label>
    <small>Laissez vide pour retirer le lien.</small>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <button type="submit" :disabled="busy || !ready">Enregistrer le lien</button>
    <button type="button" class="secondary" :disabled="busy" @click="load">Recharger</button>
  </form>
</template>
<style scoped>
.booking-link-settings {
  padding: 20px;
  border: 1px solid #dce4f2;
  border-radius: 16px;
  margin: 16px 0;
  background: white;
}
.booking-link-settings label {
  display: grid;
  gap: 8px;
}
.booking-link-settings input {
  width: 100%;
  box-sizing: border-box;
}
.booking-link-settings small {
  display: block;
  margin: 8px 0 16px;
}
.booking-link-settings button {
  margin-right: 8px;
}
</style>
