<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';
import { History, Search } from 'lucide-vue-next';
import IsolationPageHeader from './IsolationPageHeader.vue';
import SidePanel from './SidePanel.vue';
const props = defineProps<{ workspace: string; request: (path: string) => Promise<any> }>();
const day = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'America/Toronto',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
}).format(new Date());
const from = ref(day.slice(0, 8) + '01'),
  to = ref(day),
  actor = ref(''),
  objectId = ref(''),
  action = ref(''),
  page = ref(1),
  data = ref<any>(null),
  busy = ref(false),
  error = ref(''),
  selected = ref<any>(null);
let version = 0;
const date = (s: string) =>
  new Intl.DateTimeFormat('fr-CA', {
    dateStyle: 'medium',
    timeStyle: 'medium',
    timeZone: 'America/Toronto',
  }).format(new Date(s));
function parameters() {
  const q = new URLSearchParams({ from: from.value, to: to.value, page: String(page.value) });
  if (actor.value) q.set('actor_id', actor.value);
  if (objectId.value) q.set('object_id', objectId.value);
  if (action.value) q.set('action', action.value);
  return q;
}
async function load(reset = false) {
  if (reset) page.value = 1;
  const current = ++version;
  busy.value = true;
  error.value = '';
  selected.value = null;
  try {
    const result = await props.request('admin-journal/?' + parameters());
    if (current === version) data.value = result;
  } catch (e: any) {
    if (current === version) {
      data.value = null;
      error.value = e.message || 'Journal indisponible.';
    }
  } finally {
    if (current === version) busy.value = false;
  }
}
function turn(delta: number) {
  page.value += delta;
  load();
}
onMounted(() => load());
onBeforeUnmount(() => version++);
</script>
<template>
  <div class="iso-page admin-journal">
    <IsolationPageHeader
      title="Journal d’activité"
      subtitle="Qui a fait quoi, quand et sur quel dossier. Heure du Québec."
      :eyebrow="'ADMINISTRATION · ' + workspace.toUpperCase()"
      :busy="busy"
      @refresh="load()"
    />
    <form class="iso-panel journal-filters" @submit.prevent="load(true)">
      <label>Du<input v-model="from" type="date" required :disabled="busy" /></label
      ><label>Au<input v-model="to" type="date" required :disabled="busy" /></label>
      <label
        >Compte auteur<input
          v-model="actor"
          type="number"
          min="1"
          placeholder="Identifiant du compte"
          :disabled="busy"
      /></label>
      <label
        >Référence du dossier<input
          v-model="objectId"
          maxlength="100"
          placeholder="Identifiant de l’objet"
          :disabled="busy"
      /></label>
      <label
        >Type d’action<input
          v-model="action"
          list="journal-actions"
          placeholder="Toutes les actions"
          maxlength="100"
          :disabled="busy" /><datalist id="journal-actions">
          <option v-for="item in data?.actions || []" :key="item" :value="item" /></datalist
      ></label>
      <button class="primary" :disabled="busy"><Search :size="16" />Rechercher</button>
    </form>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <section v-if="data" class="iso-panel">
      <header class="iso-panel-heading">
        <div>
          <h2><History :size="19" />Historique de cet espace</h2>
          <p>{{ data.count }} événement(s) · consultation seule</p>
        </div>
      </header>
      <div class="journal-table">
        <table>
          <thead>
            <tr>
              <th>Date au Québec</th>
              <th>Auteur</th>
              <th>Action</th>
              <th>Référence</th>
              <th>Détails</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in data.results" :key="row.id">
              <td>{{ date(row.created_at) }}</td>
              <td>{{ row.actor_label }}</td>
              <td>{{ row.action }}</td>
              <td>{{ row.object_id || '—' }}</td>
              <td><button class="secondary" @click="selected = row">Consulter</button></td>
            </tr>
            <tr v-if="!data.results.length">
              <td colspan="5">Aucun événement sur ces critères.</td>
            </tr>
          </tbody>
        </table>
      </div>
      <footer class="iso-pagination">
        <span>Page {{ page }}</span
        ><button class="secondary" :disabled="busy || page === 1" @click="turn(-1)">
          Précédent</button
        ><button class="secondary" :disabled="busy || page * 25 >= data.count" @click="turn(1)">
          Suivant
        </button>
      </footer>
    </section>
    <SidePanel
      :open="!!selected"
      title="Détail de l’événement"
      :eyebrow="'JOURNAL · ' + workspace.toUpperCase()"
      @request-close="selected = null"
    >
      <template v-if="selected"
        ><section class="iso-panel">
          <h3>{{ selected.action }}</h3>
          <p>{{ selected.actor_label }} · {{ date(selected.created_at) }}</p>
          <p>Référence : {{ selected.object_id || '—' }}</p>
        </section>
        <section
          v-if="selected.metadata.before !== undefined || selected.metadata.after !== undefined"
          class="journal-comparison"
        >
          <article>
            <h3>Avant</h3>
            <pre>{{ JSON.stringify(selected.metadata.before ?? null, null, 2) }}</pre>
          </article>
          <article>
            <h3>Après</h3>
            <pre>{{ JSON.stringify(selected.metadata.after ?? null, null, 2) }}</pre>
          </article>
        </section>
        <h3>Informations enregistrées</h3>
        <pre>{{ JSON.stringify(selected.metadata, null, 2) }}</pre>
        <p class="muted">
          Les secrets sont masqués. Certains événements historiques n’ont pas enregistré d’auteur ou
          d’état avant/après ; aucune information n’est reconstituée.
        </p></template
      >
    </SidePanel>
  </div>
</template>
<style scoped>
.journal-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: end;
}
.journal-filters label {
  display: grid;
  gap: 7px;
  flex: 1 1 160px;
  font-size: 12px;
}
.journal-table {
  overflow: auto;
}
.journal-table table {
  width: 100%;
  border-collapse: collapse;
}
.journal-table th,
.journal-table td {
  padding: 13px;
  text-align: left;
  border-bottom: 1px solid var(--border, #e4e9f2);
  font-size: 12px;
}
.journal-table th {
  background: #f5f7fc;
  color: #60758f;
}
.journal-comparison {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  background: #f5f7fc;
  border-radius: 12px;
  padding: 16px;
  font-size: 12px;
  max-width: 100%;
}
@media (max-width: 760px) {
  .journal-comparison {
    grid-template-columns: 1fr;
  }
  .journal-filters button {
    width: 100%;
  }
  .journal-table th,
  .journal-table td {
    padding: 9px;
  }
}
</style>
