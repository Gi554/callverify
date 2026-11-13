<script setup lang="ts">
import { isDialableNumber } from './phone-number';
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import {
  CalendarDays,
  UserRoundCog,
  History,
  Search,
  RefreshCw,
  Pencil,
  Phone,
  Users,
  PhoneForwarded,
} from 'lucide-vue-next';
import CallAction from './CallAction.vue';
import IsolationProspectActivity from './IsolationProspectActivity.vue';
import IsolationVisits from './IsolationVisits.vue';
import SidePanel from './SidePanel.vue';
import CallCountdownModal from './CallCountdownModal.vue';
import ProspectExport from './ProspectExport.vue';
import IsolationBulkAssignment from './IsolationBulkAssignment.vue';
import IsolationDistribution from './IsolationDistribution.vue';
import IsolationLots from './IsolationLots.vue';
import IsolationQualification from './IsolationQualification.vue';
const includeProcessed = ref(false);
const lotsOpen = ref(false),
  adminTools = ref(false),
  callPending = ref(false),
  workflow = ref<'edit' | 'call'>('edit'),
  listManagement = ref(false);
const statuses = [
  ['callback_queue', 'Rappels'],
  ['to_contact', 'À contacter'],
  ['in_progress', 'En cours'],
  ['callback', 'À rappeler'],
  ['interested', 'Intéressé'],
  ['not_interested', 'Non intéressé'],
  ['unreachable', 'Non joint'],
];
type Column = {
  key: string;
  label: string;
  rows: any[];
  count: number;
  page: number;
  next: boolean;
  busy: boolean;
  error: string;
};
const columns = ref<Column[]>([]),
  applied = ref({ search: '', owner: '', due: false });
const visible = computed(() =>
  columns.value.filter(
    (c) =>
      (!commercialStatus.value || c.key === commercialStatus.value) && (c.count > 0 || !!c.error),
  ),
);
const total = computed(() => visible.value.reduce((n, c) => n + c.count, 0));
let generation = 0,
  disposed = false;
const props = defineProps<{
  role: string;
  sessionOwner?: string;
  portal: (path: string, body?: any) => Promise<any>;
  request: (path: string, body?: any, method?: string) => Promise<any>;
  // Prospect to open on arrival, e.g. from the calls module.
  focus?: { id: number; mode: 'edit' | 'call' } | null;
}>();
const activityPanel = ref<any>(null),
  activityBusy = ref(false);
const visitsPanel = ref<any>(null),
  visitBusy = ref(false);
const visitsOpen = ref(false),
  visitProspect = ref<number | undefined>(undefined);
const activity = ref<any>(null),
  commercialStatus = ref(''),
  dueOnly = ref(false),
  callbacksDue = ref(0);
const rows = computed(() => columns.value.flatMap((c) => c.rows)),
  search = ref(''),
  owner = ref(''),
  busy = ref(false),
  error = ref(''),
  selected = ref<any>(null),
  reason = ref('');
const people = ref<any[]>([]),
  peoplePage = ref(1),
  peopleCount = ref(0),
  peopleSearch = ref(''),
  target = ref(''),
  history = ref<any>(null),
  historyPage = ref(1),
  historyCount = ref(0),
  historyRows = ref<any[]>([]);
async function run(action: () => Promise<void>) {
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
async function loadColumn(column: Column, version: number, append = false) {
  if (append && column.busy) return;
  column.busy = true;
  column.error = '';
  try {
    const callbackQueue = column.key === 'callback_queue';
    const q = new URLSearchParams({
      page: String(append ? column.page + 1 : 1),
      search: applied.value.search,
      owner: applied.value.owner,
      ...(callbackQueue ? {} : { commercial_status: column.key }),
      due: String(applied.value.due),
      queue: callbackQueue ? 'callbacks' : includeProcessed.value ? 'all' : 'active',
    });
    const data = await props.request(`work-queue/?${q}`);
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
  busy.value = true;
  error.value = '';
  const term = search.value.trim();
  if (term !== applied.value.search && isDialableNumber(term)) includeProcessed.value = true;
  applied.value = { search: term, owner: owner.value, due: dueOnly.value };
  columns.value = statuses.map(([key, label]) => ({
    key,
    label,
    rows: [],
    count: 0,
    page: 0,
    next: false,
    busy: true,
    error: '',
  }));
  const queue = [...columns.value];
  await Promise.allSettled([
    props
      .request('workspace-dashboard/')
      .then((data) => {
        if (version === generation) callbacksDue.value = data.callbacks_due;
      })
      .catch(() => {}),
    ...Array.from({ length: 3 }, async () => {
      while (queue.length && !disposed && version === generation)
        await loadColumn(queue.shift()!, version);
    }),
  ]);
  if (version === generation) busy.value = false;
}
// Call session (setters): prospects are called one after the other. Finishing a file starts a
// countdown that the setter can stop; at zero the next prospect is opened and called.
const COUNTDOWN = 10;
const session = ref(false),
  countdown = ref<number | null>(null),
  nextInSession = ref<any>(null),
  sessionNote = ref(''),
  resumeAvailable = ref(false),
  recovering = ref(false),
  currentSessionProspect = ref<number | null>(null);
const visited = new Set<number>();
async function sessionAction(action: string, prospectId?: number) {
  return props.request(
    'call-session/',
    { action, ...(prospectId ? { prospect_id: prospectId } : {}) },
    'POST',
  );
}
async function loadSessionState() {
  const saved = await props.request('call-session/');
  visited.clear();
  for (const id of saved.visited_ids || []) visited.add(Number(id));
  currentSessionProspect.value = saved.current_id == null ? null : Number(saved.current_id);
  resumeAvailable.value = !!saved.active;
  return saved;
}
let sessionId = 0;
let timer: ReturnType<typeof setInterval> | null = null;
function isCurrentSession(id: number) {
  return session.value && id === sessionId && !disposed;
}
async function nextProspect(id: number) {
  // The session reads the active lot independently of the board's filters and loaded pages.
  for (let page = 1; isCurrentSession(id); page++) {
    const data = await props.request(`work-queue/?owner=me&queue=active&page=${page}`);
    const candidate = data.results.find(
      (row: any) =>
        !visited.has(row.id) &&
        row.queue_reason !== 'appointment_booked' &&
        row.commercial_status !== 'not_interested' &&
        String(row.phone || row.raw_phone || '').trim(),
    );
    if (candidate) return candidate;
    if (!data.next) break;
  }
  return null;
}
function stopTimer() {
  if (timer) clearInterval(timer);
  timer = null;
  countdown.value = null;
}
async function advance() {
  stopTimer();
  const id = sessionId;
  const row = nextInSession.value;
  nextInSession.value = null;
  if (!row || !isCurrentSession(id)) return;
  try {
    await sessionAction('begin', Number(row.id));
    currentSessionProspect.value = Number(row.id);
    recovering.value = false;
  } catch (e: any) {
    session.value = false;
    sessionNote.value = e.message || 'Impossible de préparer cette fiche.';
    resumeAvailable.value = true;
    return;
  }
  await openActivity(row, 'call', id);
  if (isCurrentSession(id) && !activity.value) {
    session.value = false;
    sessionNote.value = error.value || 'Session interrompue.';
  }
}
async function startSession() {
  if (session.value || busy.value || activity.value) return;
  sessionNote.value = '';
  sessionId++;
  try {
    const saved = await loadSessionState();
    if (saved.active && saved.current_id) {
      session.value = true;
      recovering.value = true;
      resumeAvailable.value = false;
      sessionNote.value =
        'Fiche interrompue : vérifiez son historique avant toute nouvelle tentative d’appel.';
      await openActivity({ id: Number(saved.current_id) }, 'call', sessionId);
      return;
    }
    if (!saved.active) {
      visited.clear();
      await sessionAction('start');
    }
    resumeAvailable.value = false;
  } catch (e: any) {
    sessionNote.value = e.message || 'Impossible de charger la progression de la session.';
    resumeAvailable.value = true;
    return;
  }
  session.value = true;
  await prepareNext(true);
}
function stopSession() {
  stopTimer();
  nextInSession.value = null;
  session.value = false;
  sessionNote.value = 'Session mise en pause. Votre progression est enregistrée sur le serveur.';
  resumeAvailable.value = true;
}
async function prepareNext(first = false) {
  const id = sessionId;
  try {
    const row = await nextProspect(id);
    if (!isCurrentSession(id)) return;
    if (row) {
      nextInSession.value = row;
      if (first) await advance();
      else startCountdown();
      return;
    }
    session.value = false;
    sessionNote.value = first
      ? 'Aucun prospect dans votre lot actif.'
      : 'Session terminée : plus aucun prospect à appeler.';
    try {
      await sessionAction('finish');
      visited.clear();
      currentSessionProspect.value = null;
    } catch (e: any) {
      sessionNote.value = `Session terminée, mais progression non clôturée : ${e.message}`;
    }
    resumeAvailable.value = false;
  } catch (e: any) {
    if (!isCurrentSession(id)) return;
    session.value = false;
    sessionNote.value = e.message || 'Impossible de charger votre lot actif.';
    resumeAvailable.value = true;
  }
}
function startCountdown() {
  stopTimer();
  countdown.value = COUNTDOWN;
  timer = setInterval(() => {
    if (countdown.value === null) return;
    if (countdown.value <= 1) void advance();
    else countdown.value -= 1;
  }, 1000);
}
async function openActivity(row: any, mode: 'edit' | 'call' = 'edit', id?: number) {
  if (activity.value || (session.value && id === undefined)) return;
  await run(async () => {
    const prospect = await props.request(`work-queue/${row.id}/`);
    if (disposed || (id !== undefined && !isCurrentSession(id))) return;
    workflow.value = mode;
    activity.value = prospect;
  });
}
async function activityClosed() {
  if (callPending.value) return;
  const closedId = activity.value?.id;
  if (
    Number.isSafeInteger(Number(closedId)) &&
    Number(closedId) > 0 &&
    currentSessionProspect.value === Number(closedId)
  ) {
    activityBusy.value = true;
    try {
      await sessionAction('complete', Number(closedId));
      visited.add(Number(closedId));
      currentSessionProspect.value = null;
      recovering.value = false;
    } catch (e: any) {
      error.value = `Progression non enregistrée : ${e.message}. La fiche reste ouverte.`;
      activityBusy.value = false;
      return;
    }
  }
  activity.value = null;
  activityBusy.value = false;
  callPending.value = false;
  void load();
  if (session.value && !disposed) void prepareNext();
}
async function directory(step = 0) {
  peoplePage.value = step ? peoplePage.value + step : 1;
  target.value = '';
  const data = await props.portal(
    `isolation/setters/?page=${peoplePage.value}&search=${encodeURIComponent(peopleSearch.value)}`,
  );
  people.value = data.results;
  peopleCount.value = data.count;
}
async function open(row: any) {
  await run(async () => {
    selected.value = await props.request(`work-queue/${row.id}/`);
    reason.value = '';
    await directory();
  });
}
async function assign(release = false) {
  await run(async () => {
    const row = selected.value;
    const body: any = { revision: row.revision, reason: reason.value };
    if (!release)
      body.proof = (
        await props.portal('isolation/setters/', {
          prospect_id: row.id,
          setter_id: Number(target.value),
        })
      ).proof;
    await props.request(`work-queue/${row.id}/${release ? 'unassign' : 'assign'}/`, body);
    selected.value = null;
    await load();
  });
}
async function callIntent(row: any, id: string) {
  const current = await props.request(`work-queue/${row.id}/`);
  if (activity.value?.id === current.id) activity.value = current;
  return props.request(`work-queue/${row.id}/call-intent/`, {
    revision: current.revision,
    request_id: id,
  });
}
async function loadHistory() {
  const data = await props.request(
    `work-queue/${history.value.id}/history/?page=${historyPage.value}`,
  );
  historyRows.value = data.results;
  historyCount.value = data.count;
}
onMounted(async () => {
  await load();
  try {
    await loadSessionState();
  } catch {
    sessionNote.value = 'La progression de session ne peut pas être chargée pour le moment.';
  }
  if (props.focus) await openActivity({ id: props.focus.id }, props.focus.mode);
  if (props.role === 'administrator') void run(() => directory());
});
onBeforeUnmount(() => {
  stopTimer();
  disposed = true;
  generation++;
});
</script>
<template>
  <section class="prospects-board isolation-board">
    <header class="prospects-heading">
      <div>
        <span>ESPACE ISOLATION · {{ role === 'administrator' ? 'ADMINISTRATION' : 'SETTER' }}</span>
        <h1>Prospects</h1>
        <p>Vos fiches, vos rappels et vos prochaines visites, au même endroit.</p>
      </div>
      <div class="board-actions">
        <button
          v-if="role === 'administrator' && !listManagement"
          class="secondary"
          @click="listManagement = true"
        >
          Listes et imports
        </button>
        <button v-if="listManagement" class="secondary" @click="listManagement = false">
          ← Retour aux prospects
        </button>
        <button
          v-if="['setter', 'administrator'].includes(role) && !session"
          class="primary"
          :disabled="busy || !!activity"
          @click="startSession"
        >
          <PhoneForwarded :size="16" />{{
            resumeAvailable ? 'Reprendre la session' : 'Lancer une session d’appels'
          }}
        </button>
        <button
          v-if="role === 'administrator'"
          class="secondary"
          :aria-expanded="lotsOpen"
          @click="lotsOpen = !lotsOpen"
        >
          <Users :size="16" />Lot de la semaine</button
        ><button
          v-if="role === 'administrator'"
          class="secondary"
          @click="adminTools = !adminTools"
        >
          <Users :size="16" />Répartir les prospects</button
        ><ProspectExport
          v-if="role !== 'setter'"
          :request="request"
          path="work-queue/export/"
          :filters="{
            search: applied.search,
            owner: applied.owner,
            commercial_status: commercialStatus,
            due: applied.due ? 'true' : '',
            queue: includeProcessed ? 'all' : 'active',
          }"
        /><button class="secondary" :disabled="busy" @click="load">
          <RefreshCw :size="16" />Actualiser
        </button>
      </div>
    </header>
    <IsolationQualification v-if="listManagement && role === 'administrator'" :request="request" />
    <template v-else>
      <div class="prospects-toolbar">
        <label class="processed-toggle"
          ><input type="checkbox" v-model="includeProcessed" @change="load" />Afficher aussi les
          fiches traitées</label
        >
        <label class="stage-filter"
          ><select v-model="commercialStatus" aria-label="Filtrer les prospects par statut">
            <option value="">Tous les statuts</option>
            <option v-for="[key, label] in statuses" :key="key" :value="key">{{ label }}</option>
          </select></label
        ><span class="prospects-count" role="status"
          >{{ busy ? 'Chargement…' : total + ' prospect(s)'
          }}{{ columns.some((c) => c.error) ? ' · résultat partiel' : '' }}</span
        >
        <form @submit.prevent="load">
          <Search :size="17" /><input
            v-model="search"
            aria-label="Rechercher un prospect Isolation"
            placeholder="Nom, téléphone ou référence"
          /><button :disabled="busy">Rechercher</button>
        </form>
      </div>
      <div class="isolation-filters">
        <label
          ><input v-model="dueOnly" type="checkbox" @change="load" />Rappels à traiter
          <span v-if="callbacksDue">({{ callbacksDue }})</span></label
        ><label v-if="role === 'administrator'"
          >Responsable<select v-model="owner" @change="load">
            <option value="">Tous les setters</option>
            <option value="unassigned">Non affectés</option>
            <option v-for="person in people" :key="person.id" :value="String(person.id)">
              {{ person.name }}
            </option></select
          ><input
            v-model="peopleSearch"
            aria-label="Rechercher un responsable"
            placeholder="Rechercher un setter"
            @change="run(() => directory())" /></label
        ><button
          class="text-button"
          @click="
            visitProspect = undefined;
            visitsOpen = true;
          "
        >
          <CalendarDays :size="15" />Consulter les visites
        </button>
      </div>
      <p v-if="error" role="alert" class="error">{{ error }}</p>
      <CallCountdownModal
        v-if="session && countdown !== null"
        :seconds="countdown"
        :prospect="nextInSession?.name"
        @stop="stopSession"
      >
        <span class="session-countdown-status" role="status"
          >Prochain appel dans {{ countdown }} s</span
        >
        <button class="primary" @click="advance">Appeler maintenant</button>
        <button class="secondary" @click="stopSession">Mettre en pause</button>
      </CallCountdownModal>
      <p v-else-if="session && !activity" class="call-session" role="status">
        Chargement du prochain prospect…
      </p>
      <p v-else-if="sessionNote" class="call-session" role="status">{{ sessionNote }}</p>
      <IsolationLots
        v-if="lotsOpen && role === 'administrator'"
        :request="request"
        :portal="portal"
        @changed="load"
      />
      <section v-if="adminTools && role === 'administrator'" class="admin-tools">
        <h2>Répartition et affectation</h2>
        <p>
          Ces outils portent sur les {{ rows.length }} fiches actuellement chargées. Filtrez ou
          chargez davantage de cartes pour préciser la sélection.
        </p>
        <IsolationDistribution
          :rows="rows"
          :portal="portal"
          :request="request"
          @changed="load"
        /><IsolationBulkAssignment
          :rows="rows"
          :portal="portal"
          :request="request"
          @changed="load"
        />
      </section>
      <p v-if="!busy && !visible.length" class="board-empty">
        Aucun prospect ne correspond à ces filtres.
      </p>
      <div
        class="prospects-columns"
        :class="{ 'single-status': visible.length === 1 }"
        role="region"
        tabindex="0"
        aria-label="Prospects Isolation par statut"
      >
        <section
          v-for="column in visible"
          :key="column.key"
          class="prospect-column"
          :style="{
            '--stage-tone': ['#f1ad54', '#5b8def', '#a18be2', '#48b3be', '#c990b8', '#90a0b9'][
              columns.indexOf(column) % 6
            ],
          }"
        >
          <header>
            <span class="stage-dot"></span>
            <h2>{{ column.label }}</h2>
            <span class="column-count">{{ column.count }}</span>
          </header>
          <div class="prospect-stack">
            <p v-if="column.error" role="alert">
              {{ column.error
              }}<button class="secondary" @click="loadColumn(column, generation, column.page > 0)">
                Réessayer
              </button>
            </p>
            <article v-for="row in column.rows" :key="row.id" class="prospect-card">
              <button class="prospect-title" @click="openActivity(row)">
                {{ row.name || 'Prospect sans nom' }}</button
              ><small class="prospect-updated">{{
                row.campaign?.name || row.reference || 'Isolation'
              }}</small>
              <div class="prospect-phone">
                <Phone :size="14" /><span>{{ row.phone || row.raw_phone || 'Non renseigné' }}</span>
                <div class="number-actions">
                  <button
                    :aria-label="'Ouvrir la fiche de ' + (row.name || 'ce prospect')"
                    title="Fiche et suivi"
                    @click="openActivity(row)"
                  >
                    <Pencil :size="15" /></button
                  ><button
                    v-if="['setter', 'administrator'].includes(role)"
                    class="phone-button"
                    :disabled="!row.phone && !row.raw_phone"
                    :aria-label="'Préparer l’appel vers ' + (row.phone || row.raw_phone)"
                    title="Préparer l’appel"
                    @click="openActivity(row, 'call')"
                  >
                    <Phone :size="15" />
                  </button>
                </div>
              </div>
              <p class="prospect-email">
                <Users :size="14" /><span>{{ row.assigned_setter?.name || 'Non affecté' }}</span>
              </p>
              <p
                v-if="row.callback_at"
                class="prospect-reminder"
                :class="{ 'is-late': row.callback_due }"
              >
                {{ row.callback_due ? 'Rappel en retard' : 'Prochain rappel' }} ·
                {{
                  new Date(row.callback_at).toLocaleString('fr-CA', { timeZone: 'America/Toronto' })
                }}
              </p>
              <footer class="isolation-card-footer">
                <span class="prospect-stage">{{
                  row.queue_reason === 'appointment_booked'
                    ? 'RDV pris'
                    : row.queue_reason === 'client_followup'
                      ? 'Relance personnelle du client'
                      : row.queue_reason === 'unqualified'
                        ? 'Rendez-vous non qualifié'
                        : row.commercial_label || column.label
                }}</span>
                <div>
                  <button
                    title="Qualification et visites"
                    aria-label="Qualification et visites"
                    @click="
                      visitProspect = row.id;
                      visitsOpen = true;
                    "
                  >
                    <CalendarDays :size="16" /></button
                  ><template v-if="role === 'administrator'"
                    ><button
                      title="Affecter ou réattribuer"
                      aria-label="Affecter ou réattribuer"
                      :disabled="busy"
                      @click="open(row)"
                    >
                      <UserRoundCog :size="16" /></button
                    ><button
                      title="Historique d’affectation"
                      aria-label="Historique d’affectation"
                      @click="
                        run(async () => {
                          history = row;
                          historyPage = 1;
                          await loadHistory();
                        })
                      "
                    >
                      <History :size="16" /></button
                  ></template>
                </div>
              </footer>
            </article>
            <button
              v-if="column.next"
              class="secondary more-prospects"
              :disabled="column.busy"
              @click="loadColumn(column, generation, true)"
            >
              {{ column.busy ? 'Chargement…' : 'Afficher plus' }} · {{ column.rows.length }} /
              {{ column.count }}
            </button>
          </div>
        </section>
      </div>
      <SidePanel
        :open="!!activity"
        :title="activity?.name || 'Fiche et suivi'"
        eyebrow="ISOLATION"
        :close-disabled="activityBusy || callPending"
        @request-close="activityPanel?.close()"
        ><CallAction
          v-if="activity && ['setter', 'administrator'].includes(role)"
          workspace="isolation"
          :resource-id="activity.id"
          :phone="activity.phone || activity.raw_phone"
          :auto-open="workflow === 'call'"
          :auto-send="session && !recovering"
          @skip="activityPanel?.close()"
          :before-open="
            async () => {
              activity = await request(`work-queue/${activity.id}/`);
            }
          "
          :portal="portal"
          :prepare="(id: string) => callIntent(activity, id)"
          :disabled="activityBusy"
          @busy="callPending = $event" /><IsolationProspectActivity
          v-if="activity"
          ref="activityPanel"
          :key="activity.id"
          :prospect-id="activity.id"
          :role="role"
          :portal="portal"
          :request="request"
          :session="session"
          :auto-call="!recovering && (session || workflow === 'call')"
          @busy="activityBusy = $event"
          @close="activityClosed"
          @saved="load"
          @book="
            visitProspect = activity.id;
            visitsOpen = true;
          "
      /></SidePanel>
      <SidePanel
        :open="visitsOpen"
        title="Qualification et visites"
        eyebrow="ISOLATION"
        :close-disabled="visitBusy"
        @request-close="visitsPanel?.close()"
        ><IsolationVisits
          v-if="visitsOpen"
          ref="visitsPanel"
          :key="visitProspect || 0"
          :prospect-id="visitProspect"
          :role="role"
          :portal="portal"
          :request="request"
          @busy="visitBusy = $event"
          @close="visitsOpen = false"
          @changed="
            load();
            activityPanel?.reload();
          "
      /></SidePanel>
      <SidePanel
        :open="!!selected && role === 'administrator'"
        title="Affecter le prospect"
        eyebrow="ISOLATION · ADMINISTRATION"
        :close-disabled="busy"
        @request-close="selected = null"
        ><section v-if="selected">
          <h4>Affectation : {{ selected.name || selected.raw_phone }}</h4>
          <form @submit.prevent="run(() => directory())">
            <label>Rechercher un setter Isolation actif<input v-model="peopleSearch" /></label
            ><button class="secondary" :disabled="busy">Rechercher</button>
          </form>
          <form @submit.prevent="assign()">
            <label
              >Nouveau responsable<select v-model="target" required>
                <option value="">Choisir un setter</option>
                <option
                  v-for="person in people"
                  :key="person.id"
                  :value="String(person.id)"
                  :disabled="person.id === selected.assigned_setter?.id"
                >
                  {{ person.name }}
                </option>
              </select></label
            >
            <p>{{ peopleCount }} setter(s) · page {{ peoplePage }}</p>
            <button
              type="button"
              class="secondary"
              :disabled="busy || peoplePage === 1"
              @click="run(() => directory(-1))"
            >
              Précédent</button
            ><button
              type="button"
              class="secondary"
              :disabled="busy || peoplePage * 25 >= peopleCount"
              @click="run(() => directory(1))"
            >
              Suivant</button
            ><label
              >Motif obligatoire<textarea
                v-model="reason"
                required
                maxlength="1000"
              ></textarea></label
            ><button class="primary" :disabled="busy || !target">Confirmer l’affectation</button
            ><button
              type="button"
              class="secondary"
              :disabled="busy || !selected.assigned_setter || !reason.trim()"
              @click="assign(true)"
            >
              Retirer l’affectation</button
            ><button type="button" class="secondary" :disabled="busy" @click="selected = null">
              Fermer
            </button>
          </form>
        </section></SidePanel
      >
      <SidePanel
        :open="!!history"
        title="Historique d’affectation"
        eyebrow="ISOLATION · ADMINISTRATION"
        :close-disabled="busy"
        @request-close="history = null"
        ><section v-if="history">
          <h4>Historique d’affectation</h4>
          <article v-for="entry in historyRows" :key="entry.id">
            <small>{{
              new Date(entry.created_at).toLocaleString('fr-CA', { timeZone: 'America/Toronto' })
            }}</small>
            <p>
              {{ entry.metadata.before?.setter_name || 'Non affecté' }} →
              {{ entry.metadata.after?.setter_name || 'Non affecté' }}
            </p>
            <p v-if="entry.metadata.reason">{{ entry.metadata.reason }}</p>
          </article>
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
            Suivant</button
          ><button class="secondary" @click="history = null">Fermer l’historique</button>
        </section></SidePanel
      >
    </template>
  </section>
</template>
<style scoped>
.call-session {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin: 0 0 16px;
  padding: 12px 16px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #cfe0ff;
}
.call-session > span {
  flex: 1 1 200px;
}
.prospects-board {
  padding: 28px;
  background: #f6f7fb;
  min-height: calc(100dvh - 78px);
  box-sizing: border-box;
  color: #26364d;
}
.prospects-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  margin-bottom: 24px;
}
.prospects-heading span {
  font-size: 10px;
  letter-spacing: 1.3px;
  color: #8a97ad;
  font-weight: 700;
}
.prospects-heading h1 {
  font-size: 26px;
  letter-spacing: -0.7px;
  margin: 8px 0;
  color: #203249;
}
.prospects-heading p {
  font-size: 13px;
  color: #8693a5;
  margin: 0;
  line-height: 1.6;
}
.prospects-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}
.stage-filter {
  display: flex !important;
  align-items: center;
  background: white;
  border: 1px solid #e1e6f0;
  border-radius: 7px;
  padding-right: 12px;
}
.stage-filter select {
  appearance: none;
  background: none;
  border: 0;
  padding: 12px 30px 12px 13px;
  color: #6d7b90;
  min-width: 170px;
  font-size: 12px;
}
.prospects-count {
  font-size: 11px;
  color: #8794a7;
}
.prospects-toolbar form {
  display: flex;
  align-items: center;
  gap: 10px;
  background: white;
  border: 1px solid #e1e6f0;
  border-radius: 7px;
  padding: 0 10px;
  margin-left: auto;
  color: #94a0b1;
}
.prospects-toolbar input {
  border: 0 !important;
  background: none !important;
  padding: 11px 0 !important;
  font-size: 12px;
  min-width: 0;
}
.prospects-toolbar form button {
  background: none;
  border: 0;
  border-left: 1px solid #edf0f5;
  padding: 8px 0 8px 10px;
  font-size: 11px;
  color: #527fe0;
  cursor: pointer;
}
.prospects-columns {
  display: flex;
  align-items: stretch;
  gap: 16px;
  overflow-x: auto;
  height: calc(100dvh - 290px);
  min-height: 360px;
  padding-bottom: 12px;
  overscroll-behavior-x: contain;
}
.prospect-column {
  flex: 0 0 267px;
  min-width: 0;
  display: flex;
  flex-direction: column;
  max-height: 100%;
}
.prospect-column > header {
  display: flex;
  align-items: center;
  gap: 9px;
  background: white;
  padding: 13px 12px;
  border-radius: 7px;
  margin-bottom: 12px;
  flex-shrink: 0;
}
.stage-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--stage-tone);
  flex-shrink: 0;
}
.prospect-column h2 {
  font-size: 12px !important;
  font-weight: 600;
  margin: 0;
  flex: 1;
  color: #5f6c83;
}
.prospect-column h2 small {
  display: block;
  color: #9aa4b3;
  font-size: 10px;
  margin-top: 3px;
}
.column-count {
  font-size: 10px;
  padding: 4px 7px;
  background: #f0f4fa;
  border-radius: 4px;
  color: #78869b;
}
.prospect-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  scrollbar-width: thin;
  padding-right: 2px;
  min-height: 0;
}
.prospects-board .prospect-column .prospect-card {
  margin: 0 !important;
  border: 1px solid #edf0f5 !important;
  border-radius: 8px !important;
  background: #fff;
  padding: 17px !important;
  flex-shrink: 0;
  box-shadow: 0 2px 5px #34476c02;
}
.prospect-title {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #2d3b50;
  text-align: left;
  border: 0;
  background: none;
  padding: 0;
  cursor: pointer;
  width: 100%;
  overflow-wrap: anywhere;
}
.prospect-title:hover {
  color: #4378d8;
}
.prospect-updated {
  display: block;
  color: #9aa3b2;
  font-size: 10px !important;
  margin: 7px 0 14px !important;
}
.prospect-phone {
  border-top: 1px solid #f0f2f6;
  padding-top: 12px;
  display: flex;
  align-items: center;
  gap: 7px;
  color: #8a95a7;
  font-size: 11px;
}
.prospect-phone > svg {
  flex-shrink: 0;
}
.prospect-phone > span {
  min-width: 0;
  overflow-wrap: anywhere;
  flex: 1;
}
.number-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}
.number-actions button {
  display: grid;
  place-items: center;
  width: 27px;
  height: 27px;
  border: 0;
  border-radius: 6px;
  background: #f1f4fa;
  color: #8593ac;
  cursor: pointer;
}
.number-actions button.phone-button {
  background: #eaf7f0;
  color: #4ca77e;
}
.number-actions button:hover {
  box-shadow: 0 0 0 2px #dce6f8;
}
.prospect-email {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #8a95a7;
  font-size: 11px;
  margin: 9px 0 14px !important;
}
.prospect-email svg {
  flex-shrink: 0;
}
.prospect-email span {
  overflow-wrap: anywhere;
  min-width: 0;
}
.prospect-stage {
  display: inline-block;
  border-radius: 4px;
  background: color-mix(in srgb, var(--stage-tone) 14%, white);
  color: #68768d;
  padding: 5px 8px;
  font-size: 10px;
}
.board-empty {
  font-size: 12px;
  color: #a1aabc;
  text-align: center;
  padding: 24px 10px;
}
.more-prospects {
  width: 100%;
  font-size: 11px;
}
.prospects-board button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.prospect-dialog {
  width: min(1200px, 95vw);
  max-width: 95vw;
  max-height: 92dvh;
  padding: 0;
  border: 0;
  border-radius: 15px;
  box-shadow: 0 22px 100px #15274244;
  color: #26364d;
  overflow: auto;
}
.prospect-dialog::backdrop {
  background: #14243975;
  backdrop-filter: blur(3px);
}
.prospect-dialog:deep(.contact-editor) {
  border: 0;
  border-radius: 0;
}
.prospects-board button:focus-visible {
  outline: 3px solid #b3cbf8;
  outline-offset: 2px;
}
@media (max-width: 720px) {
  .prospects-board {
    padding: 20px 14px;
  }
  .prospects-toolbar {
    flex-wrap: wrap;
  }
  .prospects-toolbar form {
    width: 100%;
    margin: 0;
  }
  .prospects-toolbar input {
    flex: 1;
  }
  .prospects-heading h1 {
    font-size: 23px;
  }
  .prospects-heading p {
    font-size: 12px;
  }
  .prospect-column {
    flex-basis: 260px;
  }
  .prospects-columns {
    height: 65dvh;
  }
  .prospect-dialog {
    width: 96vw;
    max-width: 96vw;
    max-height: 95dvh;
  }
}
.processed-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #536b91;
}
</style>
<style scoped>
/* Let the remaining stages fill the board instead of keeping fixed narrow lanes. */
.prospects-board .prospects-toolbar .stage-filter {
  position: relative;
  display: block !important;
  min-width: 180px;
  height: 42px;
  padding: 0;
  gap: 0;
}
.prospects-board .prospects-toolbar .stage-filter select {
  display: block;
  appearance: none;
  width: 100%;
  height: 100%;
  min-width: 0;
  max-width: 100%;
  border: 0;
  border-radius: inherit;
  background: transparent;
  box-shadow: none;
  padding: 10px 36px 10px 13px;
  cursor: pointer;
  font-size: 12px;
  line-height: 20px;
}
.prospects-board .stage-filter > svg {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
  color: #8190a7;
}
.prospects-board .stage-filter:focus-within {
  outline: 3px solid #81b3ed;
  outline-offset: 2px;
}
.prospects-board .prospects-toolbar .stage-filter select:focus-visible {
  outline: none;
}
.prospects-columns .prospect-column {
  flex: 1 0 280px;
}
.prospects-columns.single-status .prospect-column {
  flex: 1 1 100%;
}
.single-status .prospect-stack {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  align-content: start;
  align-items: start;
  gap: 16px;
}
.single-status .prospect-stack > p,
.single-status .more-prospects {
  grid-column: 1/-1;
}
.single-status .prospect-card {
  min-width: 0;
  box-sizing: border-box;
}
@media (max-width: 1200px) {
  .single-status .prospect-stack {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 1000px) {
  .single-status .prospect-stack {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 600px) {
  .prospects-columns .prospect-column {
    flex-basis: 260px;
  }
  .single-status .prospect-stack {
    grid-template-columns: 1fr;
  }
}
.processed-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #536b91;
}
</style>

<style scoped>
.board-actions,
.isolation-filters {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.isolation-filters {
  margin: -10px 0 22px;
  color: #778499;
  font-size: 12px;
}
.isolation-filters label {
  display: flex !important;
  align-items: center;
  gap: 8px;
}
.isolation-filters input[type='checkbox'] {
  width: auto;
}
.isolation-filters select {
  width: auto;
  min-width: 160px;
  background: #fff;
  border: 1px solid #e0e6ef;
  border-radius: 7px;
  padding: 8px;
}
.isolation-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.isolation-card-footer > div {
  display: flex;
  gap: 5px;
}
.isolation-card-footer button {
  border: 0;
  background: #f4f6fa;
  border-radius: 6px;
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  color: #7a8ba5;
  cursor: pointer;
}
.prospect-reminder {
  font-size: 11px;
  color: #7c7798;
  line-height: 1.5;
}
.prospect-reminder.is-late {
  color: #b66857;
}
.admin-tools {
  padding: 20px;
  background: white;
  border: 1px solid #e4e9f2;
  border-radius: 12px;
  margin-bottom: 20px;
}
.admin-tools h2 {
  font-size: 16px;
}
.admin-tools p {
  font-size: 12px;
  color: #8190a4;
}
.isolation-board .prospects-columns {
  height: calc(100dvh - 335px);
}
@media (max-width: 720px) {
  .board-actions {
    gap: 6px;
  }
  .prospects-heading {
    align-items: flex-start;
  }
  .board-actions button {
    font-size: 11px;
  }
  .isolation-board .prospects-columns {
    height: 65dvh;
  }
}
.processed-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #536b91;
}
</style>

<style scoped>
.session-countdown-status {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
}
</style>
