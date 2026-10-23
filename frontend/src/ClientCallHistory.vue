<script setup lang="ts">
import { onMounted, ref } from 'vue';
const props = defineProps<{
  workspace: string;
  contactId: number;
  portal: (path: string) => Promise<any>;
}>();
const rows = ref<any[]>([]),
  count = ref(0),
  page = ref(1),
  busy = ref(false),
  error = ref('');
const states: Record<string, string> = {
  dispatching: 'Envoi en cours',
  accepted: 'Poste joint · composition lancée',
  rejected: 'Refusé',
  blocked: 'Bloqué',
  unknown: 'État inconnu',
};
async function load() {
  busy.value = true;
  error.value = '';
  rows.value = [];
  try {
    const data = await props.portal(
      `${props.workspace}/call-history/?contact_id=${props.contactId}&page=${page.value}`,
    );
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
  <section>
    <p>
      Commandes lancées depuis le CRM pour cette fiche, tous agents confondus. « Poste joint » ne
      confirme pas une conversation avec le prospect. Les appels passés en dehors du CRM ne sont pas
      inclus.
    </p>
    <p v-if="error" role="alert">
      {{ error }} <button :disabled="busy" @click="load">Réessayer</button>
    </p>
    <p v-if="busy" role="status">Chargement…</p>
    <p v-if="!busy && !error">{{ count }} commande(s) enregistrée(s)</p>
    <div v-for="row in rows" :key="row.request_id" class="call-record">
      <strong>{{ row.caller?.username }} · poste {{ row.extension }}</strong>
      <p>
        {{ new Date(row.created_at).toLocaleString('fr-CA', { timeZone: 'America/Toronto' }) }} ·
        Montréal
      </p>
      <p>{{ states[row.state] || row.state }}</p>
      <small>{{
        row.journal_duration == null
          ? 'Durée indisponible'
          : `${row.journal_duration} seconde(s) · journal NEWT`
      }}</small>
    </div>
    <p v-if="!busy && !error && !rows.length">
      Aucune commande d’appel enregistrée pour cette fiche.
    </p>
    <footer>
      <button
        :disabled="busy || page === 1"
        @click="
          page--;
          load();
        "
      >
        Précédent</button
      ><span>Page {{ page }}</span
      ><button
        :disabled="busy || page * 25 >= count"
        @click="
          page++;
          load();
        "
      >
        Suivant
      </button>
    </footer>
  </section>
</template>
<style scoped>
section {
  padding: 20px;
  color: #34425c;
  font-size: 13px;
  line-height: 1.7;
}
.call-record {
  padding: 18px;
  margin: 12px 0;
  border: 1px solid #e2e4f4;
  border-radius: 12px;
  background: #f6f5fc;
}
.call-record p {
  margin: 5px 0;
}
footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 20px;
}
button {
  padding: 9px 12px;
  background: white;
  border: 1px solid #dce1ee;
  border-radius: 8px;
  color: #6353bb;
}
</style>
