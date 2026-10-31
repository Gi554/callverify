<script setup lang="ts">
import { onMounted, ref } from 'vue';
import SidePanel from './SidePanel.vue';
import IsolationC2Snapshot from './IsolationC2Snapshot.vue';
const props = defineProps<{ request: (path: string, body?: any) => Promise<any> }>();
const rows = ref<any[]>([]),
  count = ref(0),
  page = ref(1),
  busy = ref(false),
  error = ref('');
const city = ref(''),
  postal = ref(''),
  reason = ref(''),
  sort = ref('-date');
const selected = ref<any>(null),
  history = ref<any[]>([]),
  historyCount = ref(0),
  historyPage = ref(1);
const callbacks = ref<any[]>([]),
  callbackCount = ref(0),
  callbackPage = ref(1);
const reasons: Record<string, string> = {
  out_of_area: 'Hors zone d’intervention',
  city_not_served: 'Ville non desservie actuellement',
  distance: 'Distance trop importante',
  other: 'Autre',
};
const labels: Record<string, string> = {
  note: 'Note',
  qualification: 'Qualification',
  call_result: 'Résultat d’appel',
  callback_created: 'Rappel créé',
  callback_updated: 'Rappel modifié',
  callback_closed: 'Rappel terminé',
  unqualified: 'Rendez-vous non qualifié',
};
const results: Record<string, string> = {
  appointment_booked: 'Rendez-vous pris',
  voicemail: 'Répondeur',
  invalid_number: 'Numéro non attribué',
  disconnected: 'Appel coupé',
  not_interested: 'Pas intéressé',
  callback: 'Rappel demandé',
  other: 'Autre résultat',
  unreachable: 'Injoignable',
};
const when = (value: string) =>
  new Date(value).toLocaleString('fr-CA', { timeZone: 'America/Toronto' });
async function run(action: () => Promise<void>) {
  if (busy.value) return;
  busy.value = true;
  error.value = '';
  try {
    await action();
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function load() {
  const query = new URLSearchParams({
    page: String(page.value),
    city: city.value,
    postal_code: postal.value,
    reason: reason.value,
    sort: sort.value,
  });
  const data = await props.request(`isolation-unqualified/?${query}`);
  rows.value = data.results;
  count.value = data.count;
}
async function loadHistory() {
  const data = await props.request(
    `isolation-unqualified/${selected.value.id}/history/?page=${historyPage.value}`,
  );
  history.value = data.results;
  historyCount.value = data.count;
}
async function loadCallbacks() {
  const data = await props.request(
    `isolation-unqualified/${selected.value.id}/callbacks/?page=${callbackPage.value}`,
  );
  callbacks.value = data.results;
  callbackCount.value = data.count;
}
async function open(row: any) {
  await run(async () => {
    selected.value = await props.request(`isolation-unqualified/${row.id}/`);
    historyPage.value = 1;
    callbackPage.value = 1;
    history.value = [];
    callbacks.value = [];
    await loadHistory();
    await loadCallbacks();
  });
}
onMounted(() => run(load));
</script>
<template>
  <section class="unqualified">
    <p>
      Les prospects intéressés dont la visite ne peut pas encore être programmée restent regroupés
      ici.
    </p>
    <p v-if="error" role="alert">{{ error }}</p>
    <form
      class="filters"
      @submit.prevent="
        run(async () => {
          page = 1;
          await load();
        })
      "
    >
      <label>Ville<input v-model="city" maxlength="150" /></label>
      <label>Code postal<input v-model="postal" maxlength="10" /></label>
      <label
        >Motif<select v-model="reason">
          <option value="">Tous les motifs</option>
          <option v-for="(label, key) in reasons" :key="key" :value="key">{{ label }}</option>
        </select></label
      >
      <label
        >Trier par<select v-model="sort">
          <option value="-date">Plus récents</option>
          <option value="date">Plus anciens</option>
          <option value="setter">Setter responsable</option>
        </select></label
      >
      <button class="primary" :disabled="busy">Rechercher</button>
    </form>
    <p>{{ count }} fiche(s)</p>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Prospect</th>
            <th>Ville / code postal</th>
            <th>Motif</th>
            <th>Setter</th>
            <th>Enregistré le · Québec</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
            <td>{{ row.name }}<br />{{ row.phone }}</td>
            <td>{{ row.city || 'Non renseignée' }}<br />{{ row.postal_code }}</td>
            <td>{{ row.reason_label }}</td>
            <td>{{ row.setter.name }}</td>
            <td>{{ when(row.created_at) }}</td>
            <td>
              <button class="secondary" :disabled="busy" @click="open(row)">Ouvrir la fiche</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-if="!rows.length && !busy">Aucune fiche ne correspond à ces filtres.</p>
    <div class="actions">
      <button
        class="secondary"
        :disabled="busy || page === 1"
        @click="
          run(async () => {
            page--;
            await load();
          })
        "
      >
        Précédent</button
      ><span>Page {{ page }}</span
      ><button
        class="secondary"
        :disabled="busy || page * 25 >= count"
        @click="
          run(async () => {
            page++;
            await load();
          })
        "
      >
        Suivant
      </button>
    </div>
    <SidePanel
      :open="!!selected"
      title="Rendez-vous non qualifié"
      :close-disabled="busy"
      @request-close="selected = null"
    >
      <section v-if="selected" class="detail">
        <p v-if="error" role="alert">{{ error }}</p>
        <h3>{{ selected.name }}</h3>
        <p>{{ selected.phone }}</p>
        <p>
          {{ selected.reason_label }} · {{ selected.setter.name }} ·
          {{ when(selected.created_at) }} (Québec)
        </p>
        <p v-if="selected.note" class="note">{{ selected.note }}</p>
        <IsolationC2Snapshot :snapshot="selected.qualification" unqualified />
        <h4>Historique des appels et observations</h4>
        <article v-for="entry in history" :key="entry.id">
          <small>{{ when(entry.created_at) }} · {{ labels[entry.kind] || entry.kind }}</small>
          <p v-if="entry.changes?.result">
            {{ results[entry.changes.result] || entry.changes.result }}
          </p>
          <p class="note">{{ entry.body }}</p>
        </article>
        <p v-if="!history.length">Aucune interaction enregistrée.</p>
        <div class="actions">
          <button
            class="secondary"
            :disabled="busy || historyPage === 1"
            @click="
              run(async () => {
                historyPage--;
                await loadHistory();
              })
            "
          >
            Précédent</button
          ><span>Page {{ historyPage }}</span
          ><button
            class="secondary"
            :disabled="busy || historyPage * 25 >= historyCount"
            @click="
              run(async () => {
                historyPage++;
                await loadHistory();
              })
            "
          >
            Suivant
          </button>
        </div>
        <h4>Tâches et suivis</h4>
        <article v-for="task in callbacks" :key="task.id">
          <p>{{ when(task.due_at) }} · {{ task.closed_at ? 'Terminé' : 'À effectuer' }}</p>
          <p class="note">{{ task.note }}</p>
          <p v-if="task.closed_at" class="note">{{ task.resolution }}</p>
        </article>
        <p v-if="!callbacks.length">Aucun suivi enregistré.</p>
        <div class="actions">
          <button
            class="secondary"
            :disabled="busy || callbackPage === 1"
            @click="
              run(async () => {
                callbackPage--;
                await loadCallbacks();
              })
            "
          >
            Précédent</button
          ><span>Page {{ callbackPage }}</span
          ><button
            class="secondary"
            :disabled="busy || callbackPage * 25 >= callbackCount"
            @click="
              run(async () => {
                callbackPage++;
                await loadCallbacks();
              })
            "
          >
            Suivant
          </button>
        </div>
      </section>
    </SidePanel>
  </section>
</template>
<style scoped>
.unqualified,
.detail {
  display: grid;
  gap: 16px;
}
.filters,
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: end;
}
label {
  display: grid;
  gap: 6px;
}
.table-wrap {
  overflow-x: auto;
}
.note {
  white-space: pre-wrap;
}
[role='alert'] {
  color: #b42318;
}
</style>
