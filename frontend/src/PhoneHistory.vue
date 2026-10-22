<script setup lang="ts">
import { ref } from 'vue';
const props = defineProps<{
  workspace: 'assurance' | 'isolation';
  resourceId: number;
  request: (path: string, body?: any) => Promise<any>;
  portal: (path: string, body?: any) => Promise<any>;
  blocked?: boolean;
}>();
const emit = defineEmits<{ busy: [value: boolean] }>();
const today = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'America/Toronto',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
}).format(new Date());
const start = ref(today),
  end = ref(today),
  busy = ref(false),
  error = ref(''),
  result = ref<any>(null),
  applied = ref({ start: '', end: '' });
async function load(page = 1) {
  if (busy.value) return;
  busy.value = true;
  emit('busy', true);
  error.value = '';
  result.value = null;
  try {
    const dates = page === 1 ? { start: start.value, end: end.value } : applied.value;
    const source = props.workspace === 'assurance' ? 'contacts' : 'work-queue';
    const signed = await props.request(`${source}/${props.resourceId}/phone-history-proof/`, {});
    result.value = await props.portal(`${props.workspace}/phone-history/`, {
      proof: signed.proof,
      starts_on: dates.start,
      ends_on: dates.end,
      page,
    });
    applied.value = { ...dates };
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
    emit('busy', false);
  }
}
</script>
<template>
  <section class="phone-history">
    <h3>Historique Phonetico</h3>
    <p>
      Consultation manuelle du journal sortant de votre poste pour le numéro actuel de cette fiche.
      Aucun appel n’est lancé.
    </p>
    <form @submit.prevent="load()">
      <fieldset :disabled="busy || blocked">
        <div class="history-dates">
          <label>Du · Montréal<input v-model="start" type="date" :max="today" required /></label
          ><label
            >Au inclus · Montréal<input
              v-model="end"
              type="date"
              :min="start"
              :max="today"
              required
          /></label>
        </div>
        <small>Sept dates maximum. Les données restent distinctes des résultats déclarés.</small
        ><button type="submit" class="secondary">
          {{ busy ? 'Consultation…' : 'Consulter le journal Phonetico' }}
        </button>
      </fieldset>
    </form>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="result"
      ><p>
        Poste {{ result.extension }} · {{ result.count }} ligne(s) · {{ result.starts_on }} →
        {{ result.ends_on }} · {{ result.timezone }}
      </p>
      <p>
        Association du poste depuis le
        {{
          new Date(result.assignment_since).toLocaleString('fr-FR', { timeZone: 'America/Toronto' })
        }}
        · Montréal.
      </p>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Date · Montréal</th>
              <th>Heure</th>
              <th>Durée brute</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in result.results" :key="index">
              <td>{{ row.local_date }}</td>
              <td>{{ row.local_time }}</td>
              <td>{{ row.duration_raw || 'Non renseignée' }}</td>
            </tr>
            <tr v-if="!result.results.length">
              <td colspan="3">
                Aucune ligne rapprochée dans ce périmètre. Cela ne prouve pas l’absence d’appels.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p>{{ result.definition }}</p>
      <small
        >Source {{ result.source }} · consultée le
        {{ new Date(result.checked_at).toLocaleString('fr-FR') }}. L’unité de durée reste à
        confirmer.</small
      ><button
        type="button"
        class="secondary"
        :disabled="busy || blocked || result.page === 1"
        @click="load(result.page - 1)"
      >
        Précédent</button
      ><span>Page {{ result.page }}</span
      ><button
        type="button"
        class="secondary"
        :disabled="busy || blocked || !result.has_next"
        @click="load(result.page + 1)"
      >
        Suivant
      </button></template
    >
  </section>
</template>
<style scoped>
.phone-history {
  border: 1px solid #e3e8f2;
  border-radius: 12px;
  padding: 18px;
  margin: 20px 0;
  background: #f7f9fe;
}
.phone-history p,
.phone-history small {
  font-size: 12px;
  line-height: 1.7;
  color: #77859c;
}
.phone-history fieldset {
  border: 0;
  margin: 0;
  padding: 0;
}
.history-dates {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin: 14px 0;
}
.phone-history button {
  margin: 12px 6px 0 0;
}
.phone-history input {
  box-sizing: border-box;
  max-width: 100%;
}
@media (max-width: 480px) {
  .history-dates {
    grid-template-columns: 1fr;
  }
}
</style>
