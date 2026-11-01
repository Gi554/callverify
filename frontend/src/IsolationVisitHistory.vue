<script setup lang="ts">
import { ref, onMounted } from 'vue';
const props = defineProps<{ visitId: number; request: (path: string) => Promise<any> }>();
const rows = ref<any[]>([]),
  count = ref(0),
  page = ref(1),
  busy = ref(false),
  error = ref('');
const labels: Record<string, string> = {
  'isolation.visit.booked': 'Rendez-vous enregistré',
  'isolation.visit.rescheduled': 'Rendez-vous reprogrammé',
  'isolation.visit.cancelled': 'Rendez-vous annulé',
  'isolation.visit.result_recorded': 'Résultat renseigné par le client',
  'isolation.visit.closer_reported': 'Résultat renseigné par le représentant',
  'isolation.visit.closer_assigned': 'Représentant désigné',
};
function date(value: string) {
  return new Date(value).toLocaleString('fr-CA', { timeZone: 'America/Toronto' });
}
function result(value: any) {
  if (value?.outcome === 'unqualified') return 'Non qualifié — non validé';
  if (value?.performed === false) return 'Non présenté';
  if (value?.performed === true)
    return value.closed === true
      ? 'Présenté — closé'
      : value.closed === false
        ? 'Présenté — non closé'
        : 'Présenté — vente à préciser';
  return '';
}
async function load() {
  if (busy.value) return;
  busy.value = true;
  error.value = '';
  try {
    const data = await props.request(`visits/${props.visitId}/result-history/?page=${page.value}`);
    rows.value = data.results;
    count.value = data.count;
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
onMounted(load);
</script>
<template>
  <section aria-label="Historique du rendez-vous">
    <h4>Historique du rendez-vous</h4>
    <p v-if="error" role="alert">{{ error }}</p>
    <button class="secondary" :disabled="busy" @click="load">Actualiser l’historique</button>
    <article v-for="row in rows" :key="row.id">
      <strong>{{ labels[row.action] || 'Mise à jour du rendez-vous' }}</strong>
      <small>{{ date(row.created_at) }} · Québec</small>
      <p v-if="result(row.before)">Avant : {{ result(row.before) }}</p>
      <p v-if="result(row.after)">Après : {{ result(row.after) }}</p>
      <p v-if="row.after?.starts_at">Créneau conservé : {{ date(row.after.starts_at) }} · Québec</p>
      <p v-if="row.after?.name">Représentant : {{ row.after.name }}</p>
      <p v-if="row.reason" class="history-note">Motif de mise à jour : {{ row.reason }}</p>
      <p v-if="row.before?.note" class="history-note">Note précédente : {{ row.before.note }}</p>
      <p v-if="row.after?.absence_reason" class="history-note">
        Motif : {{ row.after.absence_reason }}
      </p>
      <p v-if="row.after?.note" class="history-note">Note : {{ row.after.note }}</p>
    </article>
    <p v-if="!rows.length">{{ busy ? 'Chargement…' : 'Aucune modification enregistrée.' }}</p>
    <p>{{ count }} événement(s) · page {{ page }}</p>
    <button
      class="secondary"
      :disabled="busy || page === 1"
      @click="
        page--;
        load();
      "
    >
      Précédent
    </button>
    <button
      class="secondary"
      :disabled="busy || page * 25 >= count"
      @click="
        page++;
        load();
      "
    >
      Suivant
    </button>
  </section>
</template>
<style scoped>
.history-note {
  white-space: pre-wrap;
}
</style>
