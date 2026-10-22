<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount, markRaw } from 'vue';
import {
  Rocket,
  Clock3,
  CheckCircle2,
  CalendarDays,
  Search,
  RefreshCw,
  ArrowUpRight,
} from 'lucide-vue-next';
import SidePanel from './SidePanel.vue';
import IsolationFollowUps from './IsolationFollowUps.vue';
const props = defineProps<{ role: string; request: (path: string, body?: any) => Promise<any> }>();
const emit = defineEmits<{ saved: []; navigate: [value: string] }>();
type Column = {
  key: string;
  label: string;
  hint: string;
  tone: string;
  icon: any;
  rows: any[];
  count: number;
  page: number;
  next: boolean;
  busy: boolean;
  error: string;
};
const columns = ref<Column[]>([
  {
    key: 'upcoming',
    label: 'À traiter',
    hint: 'Les prochains rappels à préparer.',
    tone: 'coral',
    icon: markRaw(Rocket),
    rows: [],
    count: 0,
    page: 0,
    next: false,
    busy: false,
    error: '',
  },
  {
    key: 'overdue',
    label: 'En retard',
    hint: 'Les suivis qui demandent votre attention.',
    tone: 'violet',
    icon: markRaw(Clock3),
    rows: [],
    count: 0,
    page: 0,
    next: false,
    busy: false,
    error: '',
  },
  {
    key: 'closed',
    label: 'Terminées',
    hint: 'Les rappels résolus et leur historique.',
    tone: 'mint',
    icon: markRaw(CheckCircle2),
    rows: [],
    count: 0,
    page: 0,
    next: false,
    busy: false,
    error: '',
  },
]);
const search = ref(''),
  applied = ref(''),
  selected = ref<any>(null),
  closing = ref(false),
  opening = ref(false),
  detailBusy = ref(false),
  error = ref(''),
  editor = ref<any>(null);
const busy = computed(() => columns.value.some((c) => c.busy)),
  complete = computed(() => columns.value.every((c) => !c.busy && !c.error));
const total = computed(() => columns.value.reduce((n, c) => n + c.count, 0)),
  closed = computed(() => columns.value[2]!.count);
const percent = computed(() =>
  total.value ? Math.round((100 * closed.value) / total.value) : null,
);
let generation = 0,
  disposed = false;
function date(value: string) {
  return new Intl.DateTimeFormat('fr-FR', {
    timeZone: 'America/Toronto',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}
async function loadColumn(column: Column, version: number, append = false) {
  if (append && column.busy) return;
  column.busy = true;
  column.error = '';
  try {
    const q = new URLSearchParams({
      state: column.key,
      search: applied.value,
      page: String(append ? column.page + 1 : 1),
    });
    const data = await props.request(`follow-ups/?${q}`);
    if (version !== generation || disposed) return;
    column.rows = append ? [...column.rows, ...data.results] : data.results;
    column.count = data.count;
    column.next = !!data.next;
    column.page = append ? column.page + 1 : 1;
  } catch (e: any) {
    if (version === generation) column.error = e.message;
  } finally {
    if (version === generation) column.busy = false;
  }
}
async function load() {
  const version = ++generation;
  applied.value = search.value.trim();
  for (const column of columns.value) {
    column.rows = [];
    column.count = 0;
    column.page = 0;
    column.next = false;
  }
  await Promise.all(columns.value.map((c) => loadColumn(c, version)));
}
async function open(row: any, finish = false) {
  if (opening.value || selected.value) return;
  opening.value = true;
  error.value = '';
  try {
    const data = await props.request(`follow-ups/${row.id}/?state=all`);
    if (disposed) return;
    selected.value = data;
    closing.value = finish;
  } catch (e: any) {
    error.value = e.message;
  } finally {
    opening.value = false;
  }
}
function saved() {
  selected.value = null;
  emit('saved');
  void load();
}
onMounted(load);
onBeforeUnmount(() => {
  disposed = true;
  generation++;
});
</script>
<template>
  <section class="setter-tasks">
    <header class="tasks-heading">
      <div>
        <span>ESPACE ISOLATION · {{ role === 'administrator' ? 'ADMINISTRATION' : 'SETTER' }}</span>
        <h1>{{ role === 'administrator' ? 'Tâches de l’équipe' : 'Mes tâches' }}</h1>
        <p>Un suivi après l’autre, faites avancer vos prospects.</p>
      </div>
      <button class="tasks-agenda" @click="emit('navigate', 'appointments')">
        <CalendarDays :size="16" />Voir les visites<ArrowUpRight :size="16" />
      </button>
    </header>
    <form class="tasks-toolbar" @submit.prevent="load">
      <label class="tasks-search"
        ><Search :size="17" /><input
          v-model="search"
          aria-label="Rechercher un rappel Isolation"
          placeholder="Prospect, téléphone ou note…" /></label
      ><button class="tasks-filter" :disabled="busy">Rechercher</button
      ><button type="button" class="tasks-refresh" :disabled="busy" @click="load">
        <RefreshCw :size="15" />Actualiser</button
      ><span class="tasks-scope"
        >{{ applied ? 'Vue filtrée' : 'Tous les rappels' }} · Heures de Montréal</span
      >
    </form>
    <p v-if="error" class="tasks-error" role="alert">{{ error }}</p>
    <div class="tasks-layout">
      <div
        class="tasks-columns"
        role="region"
        tabindex="0"
        aria-label="Tableau des rappels par état"
      >
        <section
          v-for="column in columns"
          :key="column.key"
          class="task-column"
          :class="column.tone"
        >
          <header class="task-column-heading">
            <component :is="column.icon" :size="18" />
            <h2>{{ column.label }}</h2>
            <span>{{ column.busy && !column.page ? '…' : column.count }}</span>
          </header>
          <p class="task-column-hint">{{ column.hint }}</p>
          <div class="task-column-stack">
            <p v-if="column.error" role="alert" class="tasks-error">
              {{ column.error
              }}<button @click="loadColumn(column, generation, column.page > 0)">Réessayer</button>
            </p>
            <p v-if="!column.busy && !column.error && !column.count" class="task-empty">
              Aucun rappel ici.
            </p>
            <article v-for="row in column.rows" :key="row.id" class="task-card">
              <button class="task-title" @click="open(row)">
                {{ row.prospect_name || 'Prospect ' + row.prospect_id }}
              </button>
              <p class="task-deadline"><Clock3 :size="13" />{{ date(row.due_at) }}</p>
              <p class="task-description">{{ row.note || 'Aucune note complémentaire.' }}</p>
              <small v-if="role === 'administrator'">{{
                row.owner_name || 'Setter non affecté'
              }}</small
              ><span class="task-tag">{{
                row.closed_at ? 'Résolu' : row.overdue ? 'À prioriser' : 'Rappel prospect'
              }}</span>
              <p v-if="row.closed_at" class="task-description">{{ row.resolution }}</p>
              <footer>
                <button :disabled="opening" @click="open(row)">
                  {{ row.closed_at ? 'Consulter' : 'Modifier' }}</button
                ><button v-if="!row.closed_at" :disabled="opening" @click="open(row, true)">
                  Terminer<ArrowUpRight :size="14" />
                </button>
              </footer>
            </article>
            <button
              v-if="column.next"
              class="task-load-more"
              :disabled="column.busy"
              @click="loadColumn(column, generation, true)"
            >
              {{ column.busy ? 'Chargement…' : 'Afficher plus' }} · {{ column.rows.length }} /
              {{ column.count }}
            </button>
          </div>
        </section>
      </div>
      <aside class="tasks-sidebar">
        <div class="task-progress">
          <h2>Progression des suivis</h2>
          <p v-if="!complete">
            {{
              busy
                ? 'Chargement des totaux…'
                : 'Totaux indisponibles : actualisez les colonnes en erreur.'
            }}
          </p>
          <template v-else
            ><div class="progress-main">
              <div
                class="task-donut"
                :style="{ '--progress': `${percent ?? 0}%` }"
                role="img"
                :aria-label="percent === null ? 'Aucune tâche' : percent + ' % terminées'"
              >
                <strong>{{ percent === null ? '—' : percent + '%' }}</strong
                ><small>Terminées</small>
              </div>
              <div>
                <strong>{{ total - closed }}</strong
                ><span>rappels ouverts</span>
              </div>
            </div>
            <div class="progress-stat">
              <span>Terminées</span><strong>{{ closed }} / {{ total }}</strong>
            </div>
            <div class="progress-track"><span :style="{ width: `${percent ?? 0}%` }"></span></div
          ></template>
        </div>
        <div class="task-priorities">
          <header>
            <h2>Le bon réflexe</h2>
            <Clock3 :size="18" />
          </header>
          <p>
            Traitez les rappels en retard et renseignez leur résolution. Les tâches suivent toujours
            le responsable actuel du prospect.
          </p>
          <button class="secondary" @click="emit('navigate', 'contacts')">
            Retrouver un prospect
          </button>
        </div>
      </aside>
    </div>
    <SidePanel
      :open="!!selected"
      :title="selected?.prospect_name || 'Rappel du prospect'"
      eyebrow="ISOLATION · SUIVI"
      :close-disabled="detailBusy"
      @request-close="selected?.closed_at ? (selected = null) : editor?.close()"
      ><IsolationFollowUps
        v-if="selected && !selected.closed_at"
        ref="editor"
        :key="selected.id"
        :editor-only="true"
        :initial-task="selected"
        :initial-close="closing"
        :request="request"
        @busy="detailBusy = $event"
        @saved="saved"
        @close="selected = null"
      />
      <div v-else-if="selected" class="resolved-task">
        <h3>Rappel terminé</h3>
        <p>{{ selected.note }}</p>
        <p>{{ selected.resolution }}</p>
        <button class="secondary" @click="selected = null">Fermer</button>
      </div></SidePanel
    >
  </section>
</template>

<style scoped>
.setter-tasks {
  padding: 28px;
  background: #f7f8fb;
  min-height: calc(100dvh - 78px);
  color: #303747;
  font-family: Inter, 'Segoe UI', sans-serif;
}
.tasks-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 24px;
}
.tasks-heading > div > span {
  font-size: 9px;
  font-weight: 650;
  letter-spacing: 1.7px;
  color: #8e9aaf;
}
.tasks-heading h1 {
  font-size: 28px;
  letter-spacing: -0.7px;
  color: #293344;
  margin: 8px 0;
}
.tasks-heading p {
  font-size: 12px;
  color: #8592a7;
  margin: 0;
}
.tasks-agenda,
.tasks-filter,
.tasks-refresh,
.tasks-finish {
  font-family: inherit;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  border-radius: 9px;
  padding: 11px 14px;
  font-size: 12px;
  background: white;
  border: 1px solid #dfe6f0;
  color: #687b97;
}
.tasks-agenda {
  background: #fff;
  border-color: #b7cee9;
  color: #4c86c8;
}
.tasks-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin: 0 0 28px !important;
}
.tasks-search {
  display: flex !important;
  align-items: center;
  gap: 10px;
  background: white;
  border: 1px solid #e4e9f2;
  border-radius: 10px;
  padding: 0 13px;
  color: #98a7bc;
  flex: 1;
  max-width: 365px;
}
.setter-tasks
  .tasks-toolbar
  .tasks-search
  input:not([type='checkbox']):not([type='radio']):not([type='file']) {
  font-size: 12px;
  border: 0;
  background: none;
  box-shadow: none;
  outline: 0;
  width: 100%;
  padding: 11px 0;
  color: #657c9b;
}
.tasks-priority-select {
  display: flex !important;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: #8290a8;
}
.setter-tasks .tasks-toolbar .tasks-priority-select select {
  font-size: 12px;
  background: white;
  border: 1px solid #e4e9f2;
  border-radius: 9px;
  padding: 10px;
  color: #6d7f9b;
  width: auto;
}
.tasks-filter {
  font-size: 11px;
  padding: 10px 13px;
}
.tasks-refresh {
  background: none;
  border: 0;
  font-size: 11px;
  padding: 10px;
}
.tasks-scope {
  font-size: 10px;
  color: #95a0b3;
  margin-left: auto;
}
.tasks-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 250px;
  gap: 22px;
  align-items: start;
}
.tasks-columns {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  min-width: 0;
}
.task-column {
  min-width: 0;
  --column-tone: #ed9c91;
}
.task-column.violet {
  --column-tone: #b092d5;
}
.task-column.mint {
  --column-tone: #8ac8ac;
}
.task-column-heading {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 0 0 15px;
  border-bottom: 2px solid var(--column-tone);
  color: #7f8ba0;
}
.task-column-heading h2 {
  font-size: 12px !important;
  letter-spacing: 0.7px;
  font-weight: 600;
  text-transform: uppercase;
  color: #566279;
  margin: 0;
}
.task-column-heading > span {
  font-size: 11px;
  padding: 3px 8px;
  background: #fff0ed;
  color: #bf8175;
  border-radius: 20px;
  margin-left: auto;
}
.violet .task-column-heading > span {
  background: #f0eafa;
  color: #9679ba;
}
.mint .task-column-heading > span {
  background: #e9f5ee;
  color: #6ca78a;
}
.task-column-hint {
  font-size: 10px;
  color: #a0aabd;
  line-height: 1.6;
  margin: 11px 0 17px;
  min-height: 32px;
}
.task-column-stack {
  display: grid;
  align-content: start;
  gap: 14px;
  max-height: max(300px, calc(100dvh - 330px));
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-width: thin;
  padding: 2px;
}
.task-card {
  background: white;
  border: 1px solid #e4e9f1;
  border-radius: 14px;
  padding: 17px 15px;
  min-width: 0;
  box-shadow: 0 3px 7px #243f6b03;
}
.task-card-top {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  flex-wrap: wrap;
}
.task-card-top > button {
  flex: 1;
  min-width: 80px;
  text-align: left;
  overflow-wrap: anywhere;
  font-family: inherit;
  font-size: 13px;
  font-weight: 600;
  color: #52657d;
  border: 0;
  background: none;
  cursor: pointer;
  padding: 0;
  line-height: 1.5;
}
.task-priority {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: #eef3fc;
  color: #7c9bc9;
  border-radius: 20px;
  padding: 4px 6px;
  font-size: 9px;
  white-space: nowrap;
}
.task-priority.urgent {
  background: #fce9e8;
  color: #bd7675;
}
.task-priority.high {
  background: #fff0e4;
  color: #c3956c;
}
.task-priority.low {
  background: #ecf5f1;
  color: #7b9e8c;
}
.task-deadline {
  display: flex;
  align-items: flex-start;
  gap: 5px;
  font-size: 10px;
  color: #75859b;
  line-height: 1.7;
  margin-top: 12px;
}
.task-deadline > svg {
  flex-shrink: 0;
  margin-top: 2px;
}
.task-deadline.deadline-late {
  color: #bc8f9c;
}
.task-reason {
  font-size: 11px;
  color: #697b92;
  line-height: 1.8;
  margin: 14px 0;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  min-height: 40px;
}
.task-completed,
.task-incident,
.task-context {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 7px;
  border-radius: 6px;
  background: #f0f6f3;
  color: #8daf9c;
  font-size: 9px;
}
.task-incident {
  background: #fcf0ed;
  color: #bd9486;
}
.task-context {
  background: #f4f3f9;
  color: #a49ab6;
}
.task-card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-top: 18px;
  padding-top: 13px;
  border-top: 1px solid #eef1f7;
  font-size: 10px;
  color: #98a8bd;
}
.task-card-footer > span {
  display: flex;
  align-items: center;
  gap: 5px;
}
.task-card-footer button {
  min-height: 30px;
  min-width: 62px;
  justify-content: flex-end;
  display: flex;
  align-items: center;
  gap: 5px;
  border: 0;
  background: none;
  padding: 0;
  font-family: inherit;
  font-size: 10px;
  color: #82a0c6;
  cursor: pointer;
}
.task-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  border: 1px dashed #dce3ee;
  border-radius: 12px;
  padding: 24px 15px;
  color: #a8b5c7;
  min-height: 170px;
  background: #ffffff70;
}
.task-empty > svg {
  color: var(--column-tone);
  margin-bottom: 13px;
}
.task-empty strong {
  font-size: 12px;
  font-weight: 550;
  color: #8a9ab1;
}
.task-empty p {
  font-size: 11px;
  line-height: 1.8;
  margin: 8px 0 0;
  color: #8391a6;
}
.task-load-more {
  width: 100%;
  font-family: inherit;
  font-size: 11px;
  padding: 12px;
  border: 1px solid #e2e9f2;
  border-radius: 9px;
  background: #fff;
  color: #8399b7;
  cursor: pointer;
}
.tasks-sidebar {
  display: grid;
  gap: 18px;
}
.task-progress {
  position: relative;
  isolation: isolate;
  overflow: hidden;
  border-radius: 17px;
  background: linear-gradient(135deg, #438fd8, #628fd7);
  color: white;
  padding: 24px 20px;
}
.task-progress:before,
.task-progress:after {
  content: '';
  position: absolute;
  z-index: -1;
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: #ffffff09;
  right: -45px;
  top: -35px;
}
.task-progress:after {
  width: 200px;
  height: 200px;
  top: auto;
  bottom: -160px;
  left: -90px;
}
.progress-kicker {
  font-size: 8px;
  letter-spacing: 1.3px;
  color: #e2edff;
}
.task-progress h2 {
  font-size: 21px !important;
  font-weight: 550;
  line-height: 1.4;
  letter-spacing: -0.5px;
  color: white;
  margin: 10px 0;
}
.task-progress > p {
  font-size: 10px;
  line-height: 1.6;
  color: #dceaff;
  margin: 0;
}
.progress-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 15px;
  margin: 24px 0;
}
.task-donut {
  width: 88px;
  height: 88px;
  flex-shrink: 0;
  border-radius: 50%;
  background: conic-gradient(#fff var(--progress), #ffffff35 0);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
  isolation: isolate;
}
.task-donut:before {
  content: '';
  position: absolute;
  inset: 7px;
  border-radius: 50%;
  background: #538fd7;
  z-index: -1;
}
.task-donut strong {
  font-size: 18px;
  line-height: 1.3;
  font-weight: 550;
}
.setter-tasks .task-progress .task-donut small {
  font-size: 9px;
  color: #deebff;
}
.progress-main > div:last-child > strong {
  font-size: 35px;
  letter-spacing: -1px;
  display: block;
  line-height: 1.2;
}
.progress-main > div:last-child > span {
  font-size: 9px;
  color: #e0edff;
  display: block;
  margin-top: 4px;
}
.progress-stat {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 10px;
  margin: 16px 0 8px;
  color: #e6f0ff;
}
.progress-stat strong {
  font-weight: 550;
}
.progress-track {
  height: 5px;
  overflow: hidden;
  background: #ffffff25;
  border-radius: 20px;
}
.progress-track > span {
  display: block;
  height: 100%;
  border-radius: 20px;
  background: #d4e7ff;
}
.progress-track.warm > span {
  background: #f4d6c3;
}
.task-priorities {
  padding: 22px 18px;
  background: white;
  border: 1px solid #e3e9f1;
  border-radius: 15px;
}
.task-priorities header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #a4b3c7;
}
.task-priorities h2 {
  font-size: 16px !important;
  letter-spacing: -0.3px;
  color: #667890;
  font-weight: 550;
  margin: 0;
}
.task-priorities > p {
  font-size: 10px;
  color: #9eabc0;
  margin: 8px 0 18px;
}
.priority-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 11px;
  padding: 10px 0;
  border-top: 1px solid #f0f3f8;
  color: #94a1b5;
}
.priority-row > span {
  display: flex;
  align-items: center;
  gap: 7px;
}
.priority-row strong {
  font-weight: 550;
  color: #8195af;
}
.priority-row i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #abc2e6;
}
.priority-row i.urgent {
  background: #e9a39f;
}
.priority-row i.high {
  background: #edc6a4;
}
.priority-row i.low {
  background: #abd0bd;
}
.tasks-help {
  padding: 19px;
  color: #a3b4c7;
  border: 1px solid #e5ebf3;
  border-radius: 15px;
  background: #f1f5fa;
}
.tasks-help > strong {
  display: block;
  color: #8da1b9;
  font-size: 12px;
  margin-top: 10px;
  font-weight: 550;
}
.tasks-help p {
  font-size: 10px;
  line-height: 1.9;
  margin: 8px 0 0;
  color: #a5b2c5;
}
.tasks-error {
  font-size: 12px;
  color: #b27d83;
  background: #fff4f3;
  border: 1px solid #f0d8d9;
  border-radius: 10px;
  padding: 14px;
  line-height: 1.8;
}
.tasks-error p {
  margin: 0 0 8px;
}
.task-detail {
  font-family: Inter, 'Segoe UI', sans-serif;
  color: #7789a4;
}
.task-detail-status {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 0 24px;
}
.task-detail-status > span {
  font-size: 10px;
  border-radius: 15px;
  background: #edf2fc;
  padding: 6px 10px;
  color: #8aa4c8;
}
.task-detail-status strong {
  font-size: 13px;
  font-weight: 550;
  color: #7b8fa9;
}
.task-detail dl {
  margin: 0 0 24px;
}
.task-detail dl > div {
  display: grid;
  grid-template-columns: 130px 1fr;
  gap: 16px;
  padding: 14px 0;
  border-bottom: 1px solid #e8eef6;
  font-size: 12px;
}
.task-detail dt {
  color: #a0adc1;
}
.task-detail dd {
  margin: 0;
  color: #7c8fa9;
  line-height: 1.8;
}
.task-detail-block {
  padding: 18px;
  background: white;
  border: 1px solid #e4eaf3;
  border-radius: 13px;
  margin: 16px 0;
}
.task-detail h3 {
  font-size: 15px !important;
  font-weight: 550;
  color: #7187a2;
  margin: 0 0 12px;
}
.task-detail-block p {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 13px;
  line-height: 1.9;
  margin: 10px 0 0;
  color: #6c809b;
}
.task-detail-block.incident {
  background: #fdf5f0;
  border-color: #f2e5da;
}
.task-detail-block.resolved {
  background: #edf7f1;
  border-color: #dcebe2;
}
.task-resolution-form {
  margin: 28px 0 0 !important;
  display: grid;
  gap: 12px;
}
.task-resolution-form > p {
  font-size: 12px;
  line-height: 1.8;
  color: #91a0b6;
  margin: 0;
}
.task-resolution-form label {
  display: grid;
  gap: 9px;
  font-size: 12px;
  color: #8395ac;
}
.task-resolution-form textarea {
  width: 100%;
  min-height: 155px;
  padding: 13px;
  box-sizing: border-box;
  border: 1px solid #dfe6f1;
  background: white;
  border-radius: 10px;
  font-family: inherit;
  font-size: 13px;
  color: #748aa6;
  resize: vertical;
}
.task-resolution-form > span {
  text-align: right;
  color: #a6b4c5;
  font-size: 10px;
}
.task-detail-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.tasks-finish {
  background: #548bc7;
  border-color: #548bc7;
  color: #fff;
  font-size: 12px;
}
.task-success {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #eaf5ef;
  color: #80a690;
  padding: 14px;
  border-radius: 10px;
  font-size: 12px;
  line-height: 1.7;
}
.task-discard {
  background: #fff4e9;
  padding: 18px;
  border: 1px solid #f2dfca;
  border-radius: 12px;
  font-size: 12px;
  line-height: 1.7;
  margin-bottom: 22px;
  color: #b79c7c;
}
.task-discard button {
  margin: 5px;
}
.setter-tasks button:disabled,
.task-detail-footer button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.setter-tasks button:focus-visible,
.tasks-columns:focus-visible,
.task-column-stack:focus-visible,
.tasks-search:focus-within {
  outline: 3px solid #abc9ef;
  outline-offset: 3px;
}
@media (min-width: 1550px) {
  .tasks-layout {
    grid-template-columns: minmax(0, 1fr) 280px;
    gap: 26px;
  }
  .tasks-columns {
    gap: 22px;
  }
  .task-card {
    padding: 21px;
  }
}
@media (max-width: 1250px) {
  .tasks-layout {
    grid-template-columns: minmax(0, 1fr);
  }
  .tasks-sidebar {
    grid-template-columns: 1fr 1fr 1fr;
  }
  .task-progress {
    padding: 20px;
  }
  .tasks-help {
    align-self: start;
  }
  .task-column-hint {
    min-height: 0;
  }
}
@media (max-width: 850px) {
  .tasks-columns {
    grid-template-columns: repeat(3, minmax(240px, 1fr));
    overflow-x: auto;
    padding-bottom: 14px;
  }
  .tasks-sidebar {
    grid-template-columns: 1fr 1fr;
  }
  .tasks-help {
    grid-column: 1/-1;
  }
  .tasks-scope {
    width: 100%;
    margin: 0;
  }
  .tasks-search {
    max-width: none;
  }
  .tasks-heading {
    align-items: flex-start;
  }
  .task-column-hint {
    min-height: 32px;
  }
}
@media (max-width: 600px) {
  .setter-tasks {
    padding: 20px 14px;
  }
  .tasks-heading {
    flex-direction: column;
    gap: 18px;
  }
  .tasks-heading h1 {
    font-size: 25px;
  }
  .tasks-toolbar {
    gap: 10px;
  }
  .tasks-search {
    flex-basis: 100%;
  }
  .tasks-priority-select {
    flex-wrap: wrap;
  }
  .tasks-sidebar {
    grid-template-columns: 1fr;
  }
  .tasks-help {
    grid-column: auto;
  }
  .task-progress {
    padding: 24px;
  }
  .progress-main {
    justify-content: flex-start;
    gap: 30px;
  }
  .task-detail dl > div {
    grid-template-columns: 100px 1fr;
  }
  .task-detail-footer {
    gap: 8px;
  }
  .tasks-finish {
    font-size: 11px;
    padding: 11px;
  }
}
</style>

<style scoped>
.task-stack {
  overflow-y: auto;
  min-height: 0;
  padding: 2px 2px 14px;
}
.task-card {
  margin-bottom: 14px;
}
.task-card footer {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  border-top: 1px solid #f0edf5;
  padding-top: 12px;
  margin-top: 14px;
}
.task-card footer button {
  display: flex;
  align-items: center;
  gap: 5px;
  border: 0;
  background: none;
  color: #7d8db9;
  font-size: 11px;
  cursor: pointer;
}
.task-column > header {
  display: flex;
  align-items: center;
  gap: 9px;
}
.task-column > header h2 {
  flex: 1;
}
.task-column > header > span {
  border-radius: 20px;
  background: #f4f0f8;
  padding: 4px 8px;
  font-size: 11px;
}
.task-description {
  font-size: 12px;
  color: #8190a5;
  line-height: 1.65;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.task-deadline {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 11px;
  color: #9c94a7;
}
.task-tag {
  display: inline-flex;
  margin-top: 10px;
  border-radius: 20px;
  padding: 5px 9px;
  background: #f3effa;
  font-size: 10px;
  color: #8d7aa5;
}
.task-title {
  text-align: left;
  border: 0;
  background: none;
  padding: 0;
  color: #43506c;
  font-weight: 650;
  cursor: pointer;
}
.resolved-task {
  line-height: 1.7;
  color: #73829b;
}
</style>
