<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import {
  Search,
  SlidersHorizontal,
  Download,
  CalendarClock,
  CalendarX,
  CalendarOff,
  Files,
  Paperclip,
  Info,
} from 'lucide-vue-next';
import AssuranceContactEditor from './AssuranceContactEditor.vue';
import SidePanel from './SidePanel.vue';
const props = defineProps<{
  request: (path: string, body?: any, method?: string) => Promise<any>;
  portal: (path: string, body?: any) => Promise<any>;
  initialDeadline?: string;
}>();
const emit = defineEmits<{ changed: [] }>();
const rows = ref<any[]>([]),
  page = ref(1),
  count = ref(0),
  busy = ref(false),
  error = ref(''),
  selected = ref<any>(null),
  panelBusy = ref(false),
  editor = ref<InstanceType<typeof AssuranceContactEditor> | null>(null);
const deadlines = ref<any>(null),
  statistics = ref<any>(null),
  exporting = ref(false);
const blankFilters = () => ({
  deadline: '',
  horizon_days: '30',
  search: '',
  kind: '',
  status: '',
  starts_from: '',
  starts_to: '',
  ends_from: '',
  ends_to: '',
});
const filters = ref({ ...blankFilters(), deadline: props.initialDeadline || '' });
// Advanced filters stay folded unless one of them is in use.
const advancedOpen = ref(false);
const advancedCount = computed(
  () =>
    ['status', 'starts_from', 'starts_to', 'ends_from', 'ends_to'].filter(
      (key) => (filters.value as any)[key],
    ).length + (filters.value.horizon_days !== '30' ? 1 : 0),
);
const kinds = [
  { value: '', label: 'Tous' },
  { value: 'mandate', label: 'Mandats' },
  { value: 'contract', label: 'Contrats' },
];
const deadlineLabels: Record<string, string> = {
  overdue: 'Date de fin dépassée',
  upcoming: 'Échéance proche',
  undated: 'Date de fin manquante',
  later: 'Échéance ultérieure',
  not_tracked: 'Hors suivi',
};
const states: Record<string, string> = {
  draft: 'Brouillon',
  tracking: 'En suivi',
  archived: 'Archivé',
};
const day = (value: string) =>
  value
    ? new Intl.DateTimeFormat('fr-FR', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        timeZone: 'UTC',
      }).format(new Date(value + 'T12:00:00Z'))
    : '—';
let lastRequest = 0;
async function load(reset = false) {
  if (reset) page.value = 1;
  const current = ++lastRequest;
  busy.value = true;
  error.value = '';
  rows.value = [];
  deadlines.value = null;
  statistics.value = null;
  try {
    const query = new URLSearchParams({ page: String(page.value) });
    for (const [key, value] of Object.entries(filters.value)) if (value) query.set(key, value);
    const result = await props.request(`agreement-registry/?${query}`);
    if (current !== lastRequest) return;
    rows.value = result.results;
    count.value = result.count;
    deadlines.value = result.deadlines;
    statistics.value = result.statistics;
  } catch (e: any) {
    if (current === lastRequest) {
      error.value = e.message;
      count.value = 0;
    }
  } finally {
    if (current === lastRequest) busy.value = false;
  }
}
function setKind(value: string) {
  filters.value.kind = value;
  void load(true);
}
// Alert cards toggle the deadline filter; their counts ignore it (server "deadlines" summary).
function setDeadline(value: string) {
  filters.value.deadline = filters.value.deadline === value ? '' : value;
  void load(true);
}
async function open(row: any) {
  busy.value = true;
  error.value = '';
  try {
    selected.value = await props.request(`contacts/${row.contact.id}/`);
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
function closed() {
  selected.value = null;
  panelBusy.value = false;
  void load();
}
function clear() {
  filters.value = blankFilters();
  void load(true);
}
async function download() {
  exporting.value = true;
  error.value = '';
  try {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(filters.value)) if (value) query.set(key, value);
    const blob = await props.request(`agreement-registry/export/?${query}`);
    const url = URL.createObjectURL(blob);
    try {
      const link = document.createElement('a');
      link.href = url;
      link.download = 'mandats-contrats.xlsx';
      link.click();
    } finally {
      URL.revokeObjectURL(url);
    }
  } catch (e: any) {
    error.value = e.message;
  } finally {
    exporting.value = false;
  }
}
onMounted(() => load());
</script>

<template>
  <section class="registry">
    <header class="registry-toolbar">
      <form class="registry-search" @submit.prevent="load(true)">
        <Search :size="16" />
        <input
          v-model="filters.search"
          maxlength="250"
          aria-label="Référence ou nom du prospect"
          placeholder="Référence ou nom du prospect"
        />
      </form>
      <div class="segmented" role="group" aria-label="Type">
        <button
          v-for="kind in kinds"
          :key="kind.value"
          type="button"
          :class="{ 'is-active': filters.kind === kind.value }"
          :aria-pressed="filters.kind === kind.value"
          :disabled="busy"
          @click="setKind(kind.value)"
        >
          {{ kind.label }}
        </button>
      </div>
      <button
        type="button"
        class="secondary registry-more"
        :aria-expanded="advancedOpen"
        @click="advancedOpen = !advancedOpen"
      >
        <SlidersHorizontal :size="15" />Plus de filtres<span v-if="advancedCount" class="count">{{
          advancedCount
        }}</span>
      </button>
      <button
        type="button"
        class="secondary registry-export"
        :disabled="busy || exporting"
        @click="download"
      >
        <Download :size="15" />{{ exporting ? 'Export en cours…' : 'Exporter Excel' }}
      </button>
    </header>
    <form v-if="advancedOpen" class="registry-advanced" @submit.prevent="load(true)">
      <fieldset :disabled="busy">
        <label
          >État<select v-model="filters.status">
            <option value="">Tous, y compris archivés</option>
            <option v-for="(label, key) in states" :key="key" :value="key">{{ label }}</option>
          </select></label
        ><label
          >Horizon des échéances<select v-model="filters.horizon_days">
            <option value="7">7 jours</option>
            <option value="30">30 jours</option>
            <option value="90">90 jours</option>
          </select></label
        ><label>Début à partir du<input v-model="filters.starts_from" type="date" /></label
        ><label>Début jusqu’au<input v-model="filters.starts_to" type="date" /></label
        ><label>Fin à partir du<input v-model="filters.ends_from" type="date" /></label
        ><label>Fin jusqu’au<input v-model="filters.ends_to" type="date" /></label>
      </fieldset>
      <div class="registry-advanced-actions">
        <small>Bornes incluses ; un filtre de date écarte les suivis sans cette date.</small>
        <button type="button" class="secondary" :disabled="busy" @click="clear">
          Réinitialiser
        </button>
        <button class="primary" :disabled="busy">Appliquer</button>
      </div>
    </form>
    <p v-if="error" role="alert" class="registry-error">{{ error }}</p>
    <div v-if="deadlines" class="registry-alerts">
      <button
        type="button"
        :class="['alert-card', 'overdue', { 'is-active': filters.deadline === 'overdue' }]"
        :aria-pressed="filters.deadline === 'overdue'"
        :disabled="busy"
        @click="setDeadline('overdue')"
      >
        <CalendarX :size="20" /><strong>{{ deadlines.overdue }}</strong
        ><span>Date de fin dépassée</span>
      </button>
      <button
        type="button"
        :class="['alert-card', 'upcoming', { 'is-active': filters.deadline === 'upcoming' }]"
        :aria-pressed="filters.deadline === 'upcoming'"
        :disabled="busy"
        @click="setDeadline('upcoming')"
      >
        <CalendarClock :size="20" /><strong>{{ deadlines.upcoming }}</strong
        ><span>Échéance dans les {{ deadlines.horizon_days }} jours</span>
      </button>
      <div class="alert-card undated">
        <CalendarOff :size="20" /><strong>{{ deadlines.undated }}</strong
        ><span>Sans date de fin</span>
      </div>
      <div v-if="statistics" class="alert-card total">
        <Files :size="20" /><strong>{{ statistics.total }}</strong
        ><span
          >{{ statistics.by_kind.mandate }} mandat(s) ·
          {{ statistics.by_kind.contract }} contrat(s)</span
        >
      </div>
    </div>
    <ul v-if="statistics" class="registry-states">
      <li v-for="(label, key) in states" :key="key">
        <strong>{{ statistics.by_status[key] }}</strong
        >{{ label }}
      </li>
    </ul>
    <div v-if="!busy && !error && !rows.length" class="registry-empty">
      <Files :size="28" />
      <strong>Aucun mandat ni contrat pour ces critères</strong>
      <p>
        Les mandats et contrats s’ajoutent depuis la fiche d’un prospect. Élargissez la recherche ou
        réinitialisez les filtres.
      </p>
      <button type="button" class="secondary" @click="clear">Réinitialiser les filtres</button>
    </div>
    <div v-else class="table-scroll">
      <table class="registry-table">
        <thead>
          <tr>
            <th>Suivi</th>
            <th>Type</th>
            <th>État</th>
            <th>Période</th>
            <th>Échéance</th>
            <th>Pièces</th>
            <th><span class="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
            <td>
              <strong>{{ row.reference }}</strong>
              <small>{{ row.contact.name || 'Prospect sans nom' }}</small>
            </td>
            <td data-label="Type">
              <span :class="['reg-pill', row.kind]">{{
                row.kind === 'mandate' ? 'Mandat' : 'Contrat'
              }}</span>
            </td>
            <td data-label="État">
              <span :class="['reg-pill', 'state', row.status]">{{ states[row.status] }}</span>
            </td>
            <td data-label="Période">{{ day(row.starts_on) }} → {{ day(row.ends_on) }}</td>
            <td data-label="Échéance">
              <span :class="['deadline-badge', row.deadline_state]">{{
                deadlineLabels[row.deadline_state]
              }}</span
              ><small v-if="row.deadline_state === 'upcoming'">{{
                row.days_to_end === 0 ? 'Aujourd’hui' : 'Dans ' + row.days_to_end + ' jour(s)'
              }}</small
              ><small v-if="row.deadline_state === 'overdue'"
                >Depuis {{ -row.days_to_end }} jour(s)</small
              >
            </td>
            <td data-label="Pièces">
              <span class="attachments"><Paperclip :size="14" />{{ row.document_count }}</span>
            </td>
            <td class="row-action">
              <button class="secondary" :disabled="busy" @click="open(row)">Ouvrir la fiche</button>
            </td>
          </tr>
          <tr v-if="busy && !rows.length">
            <td colspan="7" class="registry-loading">Chargement…</td>
          </tr>
        </tbody>
      </table>
    </div>
    <footer v-if="count" class="registry-pages">
      <span
        >{{ count }} suivi(s) · page {{ page }} ·
        {{ filters.deadline ? 'triés par date de fin' : 'derniers modifiés d’abord' }}</span
      ><button
        class="secondary"
        :disabled="busy || page === 1"
        @click="
          page--;
          load();
        "
      >
        Précédent</button
      ><button
        class="secondary"
        :disabled="busy || page * 25 >= count"
        @click="
          page++;
          load();
        "
      >
        Suivant
      </button>
    </footer>
    <details class="registry-notes">
      <summary><Info :size="15" />À savoir</summary>
      <p>
        Registre administratif : les états de suivi ne constituent ni une signature ni une
        validation juridique, ni une conversion commerciale. Seuls les suivis « En suivi » sont
        signalés pour leur échéance, sans clôture automatique ; « Hors suivi » regroupe brouillons
        et archivés.
      </p>
      <p v-if="statistics">
        Synthèse au {{ statistics.as_of }} (UTC), sur toutes les pages des résultats filtrés. Les
        cartes d’alerte ignorent le filtre d’alerte en cours.
      </p>
      <p>
        L’export reprend les filtres et tous les résultats correspondants, au-delà de la page
        affichée (10 000 suivis au maximum).
      </p>
    </details>
    <SidePanel
      :scrollable="false"
      :open="!!selected"
      :title="selected?.name || 'Prospect sans nom'"
      :subtitle="selected?.status_label || selected?.status"
      eyebrow="FICHE PROSPECT"
      :close-disabled="panelBusy"
      @request-close="editor?.close()"
      ><AssuranceContactEditor
        v-if="selected"
        ref="editor"
        :key="selected.id"
        :contact="selected"
        role="administrator"
        :request="request"
        :portal="portal"
        @busy="panelBusy = $event"
        @close="closed"
        @changed="
          load();
          emit('changed');
        "
    /></SidePanel>
  </section>
</template>

<style scoped>
.registry {
  display: grid;
  gap: 16px;
}
.registry-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}
.registry-search {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1 1 240px;
  padding: 0 12px;
  border: 1px solid #dfe4ec;
  border-radius: 10px;
  background: white;
  color: #6b7686;
}
.registry-search input {
  flex: 1;
  border: 0;
  padding: 10px 0;
  background: none;
  outline: none;
}
.segmented {
  display: inline-flex;
  padding: 3px;
  border-radius: 10px;
  background: #eef1f6;
}
.segmented button {
  border: 0;
  border-radius: 8px;
  background: none;
  color: #5b6b82;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.segmented button.is-active {
  background: white;
  color: #1f2f45;
  box-shadow: 0 1px 4px #1f2f4518;
}
.registry-more,
.registry-export,
.registry-notes summary,
.attachments {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.registry-export {
  margin-left: auto;
}
.count {
  display: inline-grid;
  place-items: center;
  min-width: 18px;
  height: 18px;
  border-radius: 99px;
  background: #1f5fa8;
  color: white;
  font-size: 11px;
}
.registry-advanced {
  display: grid;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid #e3e7ee;
  border-radius: 12px;
  background: #fafbfd;
}
.registry-advanced fieldset {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 12px;
  margin: 0;
  padding: 0;
  border: 0;
}
.registry-advanced label {
  display: grid;
  gap: 4px;
  font-size: 12px;
  color: #5b6b82;
}
.registry-advanced-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}
.registry-advanced-actions small {
  margin-right: auto;
  color: #6b7686;
}
.registry-error {
  color: #b42318;
}
.registry-alerts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}
.alert-card {
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 2px 12px;
  padding: 14px 16px;
  border: 1px solid #e3e7ee;
  border-radius: 14px;
  background: white;
  text-align: left;
  color: #1f2f45;
}
button.alert-card {
  cursor: pointer;
}
.alert-card svg {
  grid-row: span 2;
}
.alert-card strong {
  font-size: 24px;
  line-height: 1.1;
}
.alert-card span {
  color: #5b6b82;
  font-size: 12px;
}
.alert-card.overdue svg {
  color: #b42318;
}
.alert-card.upcoming svg {
  color: #b4610c;
}
.alert-card.undated svg {
  color: #6b4fc5;
}
.alert-card.total svg {
  color: #1f5fa8;
}
.alert-card.overdue.is-active {
  border-color: #f0a199;
  background: #fff5f4;
}
.alert-card.upcoming.is-active {
  border-color: #f4c38b;
  background: #fffaf3;
}
.registry-states {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.registry-states li {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 99px;
  background: #f3f5f8;
  color: #5b6b82;
  font-size: 12px;
}
.registry-states strong {
  color: #1f2f45;
}
.registry-empty {
  display: grid;
  justify-items: center;
  gap: 8px;
  padding: 36px 20px;
  border: 1px dashed #d6dce5;
  border-radius: 14px;
  color: #5b6b82;
  text-align: center;
}
.registry-empty strong {
  color: #1f2f45;
}
.registry-empty p {
  margin: 0;
  max-width: 460px;
}
.registry-table td small {
  display: block;
  margin-top: 2px;
  color: #6b7686;
}
.reg-pill {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 99px;
  background: #f1f3f6;
  color: #3d4b60;
  font-size: 12px;
  font-weight: 600;
}
.reg-pill.mandate {
  background: #e7f0fd;
  color: #1f5fa8;
}
.reg-pill.contract {
  background: #efeafb;
  color: #6b4fc5;
}
.reg-pill.state.tracking {
  background: #e3f4ea;
  color: #23784a;
}
.reg-pill.state.archived {
  color: #6b7686;
}
.deadline-badge {
  display: inline-block;
  padding: 3px 8px;
  border-radius: 6px;
  background: #eef0e8;
  color: #4c5340;
  font-size: 12px;
}
.deadline-badge.overdue {
  background: #fde9e5;
  color: #8a281d;
}
.deadline-badge.upcoming {
  background: #fff0d1;
  color: #755019;
}
.deadline-badge.undated {
  background: #ece9fa;
  color: #57448a;
}
.row-action {
  text-align: right;
}
.registry-loading {
  color: #6b7686;
  text-align: center;
}
.registry-pages {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #5b6b82;
  font-size: 12px;
}
.registry-pages span {
  margin-right: auto;
}
.registry-notes {
  padding: 12px 16px;
  border-radius: 12px;
  background: #f6f8fb;
  color: #5b6b82;
  font-size: 13px;
}
.registry-notes summary {
  cursor: pointer;
  font-weight: 600;
  color: #1f2f45;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
</style>
