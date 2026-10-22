<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount, markRaw } from 'vue';
import {
  Rocket,
  Clock3,
  CheckCircle2,
  ArrowUpRight,
  Search,
  RefreshCw,
  CalendarDays,
  Flag,
  AlertCircle,
  ListTodo,
  ShieldCheck,
} from 'lucide-vue-next';
import SidePanel from './SidePanel.vue';
import AssuranceFollowUps from './AssuranceFollowUps.vue';
import AssuranceFollowUpPolicy from './AssuranceFollowUpPolicy.vue';
import { bookingInterval } from './booking-time';
const props = defineProps<{
  request: (path: string, body?: any, method?: string) => Promise<any>;
  role?: string;
  portal?: (path: string, body?: any) => Promise<any>;
}>();
const adminEditor = ref<any>(null),
  adminBusy = ref(false),
  policyOpen = ref(false),
  policyBusy = ref(false),
  policyEditor = ref<any>(null);
const emit = defineEmits<{ changed: []; navigate: [value: string] }>();
type Column = {
  key: string;
  label: string;
  hint: string;
  icon: any;
  tone: string;
  rows: any[];
  count: number;
  page: number;
  next: boolean;
  busy: boolean;
  error: string;
};
const columns = ref<Column[]>([
  {
    key: 'todo',
    label: 'À traiter',
    hint: 'Les prochains suivis à faire avancer.',
    icon: markRaw(Rocket),
    tone: 'coral',
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
    hint: 'Les échéances qui demandent votre attention.',
    icon: markRaw(Clock3),
    tone: 'violet',
    rows: [],
    count: 0,
    page: 0,
    next: false,
    busy: false,
    error: '',
  },
  {
    key: 'closed',
    label: 'Clôturées',
    hint: 'Les suivis terminés, avec leur résolution.',
    icon: markRaw(CheckCircle2),
    tone: 'mint',
    rows: [],
    count: 0,
    page: 0,
    next: false,
    busy: false,
    error: '',
  },
]);
const summary = ref<any>(null),
  summaryError = ref(''),
  summaryBusy = ref(false),
  search = ref(''),
  priority = ref(''),
  appliedSearch = ref(''),
  appliedPriority = ref('');
const editing = ref(false),
  editReason = ref(''),
  editDue = ref(''),
  editPriority = ref('normal');
const selected = ref<any>(null),
  opening = ref(false),
  saving = ref(false),
  detailError = ref(''),
  boardMessage = ref(''),
  resolution = ref(''),
  discard = ref(false),
  confirmed = ref(false);
const busy = computed(() => summaryBusy.value || columns.value.some((c) => c.busy));
const percentage = computed(() =>
  summary.value?.total ? Math.round((100 * summary.value.closed) / summary.value.total) : null,
);
const filtered = computed(() => !!appliedSearch.value || !!appliedPriority.value);
const priorityLabels: Record<string, string> = {
  urgent: 'Urgente',
  high: 'Haute',
  normal: 'Normale',
  low: 'Basse',
};
const priorityRows = computed(() =>
  ['urgent', 'high', 'normal', 'low'].map((key) => ({
    key,
    label: priorityLabels[key],
    count: summary.value?.open_priorities?.[key] ?? 0,
  })),
);
let generation = 0,
  disposed = false;
function query() {
  return new URLSearchParams({
    state: 'all',
    search: appliedSearch.value,
    priority: appliedPriority.value,
  });
}
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
    const data = await props.request(
      `follow-ups/?${query()}&bucket=${column.key}&page=${append ? column.page + 1 : 1}`,
    );
    if (version !== generation || disposed) return;
    column.rows = append ? [...column.rows, ...data.results] : data.results;
    column.count = data.count;
    column.next = !!data.next;
    column.page = append ? column.page + 1 : 1;
  } catch (e: any) {
    if (version === generation && !disposed) column.error = e.message;
  } finally {
    if (version === generation && !disposed) column.busy = false;
  }
}
async function loadSummary(version: number) {
  summaryBusy.value = true;
  summaryError.value = '';
  summary.value = null;
  try {
    const data = await props.request(`follow-ups/summary/?${query()}`);
    if (version === generation && !disposed) summary.value = data;
  } catch (e: any) {
    if (version === generation && !disposed) summaryError.value = e.message;
  } finally {
    if (version === generation && !disposed) summaryBusy.value = false;
  }
}
async function load() {
  const version = ++generation;
  appliedSearch.value = search.value.trim();
  appliedPriority.value = priority.value;
  for (const column of columns.value) {
    column.rows = [];
    column.count = 0;
    column.page = 0;
    column.next = false;
  }
  await Promise.allSettled([
    loadSummary(version),
    ...columns.value.map((column) => loadColumn(column, version)),
  ]);
}
async function open(row: any) {
  if (opening.value || selected.value) return;
  opening.value = true;
  boardMessage.value = '';
  try {
    const detail = await props.request(`follow-ups/${row.id}/?state=all`);
    if (disposed) return;
    selected.value = detail;
    editing.value = false;
    resolution.value = '';
    discard.value = false;
    confirmed.value = false;
    detailError.value = '';
  } catch (e: any) {
    boardMessage.value = e.message;
  } finally {
    opening.value = false;
  }
}
function closePanel() {
  if (saving.value) return;
  if ((editing.value || resolution.value.trim()) && !selected.value?.closed_at) {
    discard.value = true;
    return;
  }
  selected.value = null;
  resolution.value = '';
  discard.value = false;
}
async function reloadSelected() {
  if (saving.value || !selected.value) return;
  saving.value = true;
  detailError.value = '';
  try {
    const row = await props.request(`follow-ups/${selected.value.id}/?state=all`);
    if (!disposed) selected.value = row;
  } catch (e: any) {
    if (!disposed) detailError.value = e.message;
  } finally {
    saving.value = false;
  }
}
function editTask() {
  const row = selected.value;
  editing.value = true;
  editReason.value = row.reason;
  editPriority.value = row.priority;
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-CA', {
      timeZone: 'America/Toronto',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
    })
      .formatToParts(new Date(row.due_at))
      .map((p) => [p.type, p.value]),
  );
  editDue.value = `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}
async function saveTask() {
  if (saving.value) return;
  saving.value = true;
  detailError.value = '';
  try {
    const row = await props.request(`follow-ups/${selected.value.id}/edit/?state=all`, {
      revision: selected.value.revision,
      reason: editReason.value,
      priority: editPriority.value,
      due_at: bookingInterval(editDue.value, 'America/Toronto', 30).starts_at,
    });
    if (disposed) return;
    selected.value = row;
    editing.value = false;
    emit('changed');
    await load();
  } catch (e: any) {
    detailError.value = e.message;
  } finally {
    saving.value = false;
  }
}
async function finish() {
  if (saving.value || !selected.value || selected.value.closed_at || !resolution.value.trim())
    return;
  saving.value = true;
  detailError.value = '';
  try {
    const row = await props.request(`follow-ups/${selected.value.id}/close/?state=all`, {
      revision: selected.value.revision,
      resolution: resolution.value.trim(),
    });
    if (disposed) return;
    selected.value = row;
    resolution.value = '';
    confirmed.value = true;
    emit('changed');
    await load();
  } catch (e: any) {
    if (!disposed) detailError.value = e.message;
  } finally {
    saving.value = false;
  }
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
        <span>ESPACE ASSURANCE · {{ role === 'administrator' ? 'ADMINISTRATION' : 'SETTER' }}</span>
        <h1>{{ role === 'administrator' ? 'Tâches de l’équipe' : 'Mes tâches' }}</h1>
        <p>Un suivi après l’autre, faites avancer vos prospects.</p>
      </div>
      <button class="tasks-agenda" @click="emit('navigate', 'appointments')">
        <CalendarDays :size="16" />{{
          role === 'administrator' ? 'Voir l’agenda de l’équipe' : 'Voir mes rendez-vous'
        }}<ArrowUpRight :size="16" />
      </button>
    </header>
    <form class="tasks-toolbar" @submit.prevent="load">
      <label class="tasks-search"
        ><Search :size="17" /><input
          v-model="search"
          aria-label="Rechercher une tâche par prospect ou motif"
          placeholder="Rechercher un prospect ou un suivi…" /></label
      ><label class="tasks-priority-select"
        ><span>Priorité</span
        ><select v-model="priority" :disabled="busy">
          <option value="">Toutes les priorités</option>
          <option v-for="(label, key) in priorityLabels" :key="key" :value="key">
            {{ label }}
          </option>
        </select></label
      ><button class="tasks-filter" :disabled="busy">Filtrer</button
      ><button class="tasks-refresh" type="button" :disabled="busy" @click="load">
        <RefreshCw :size="15" />Actualiser</button
      ><span class="tasks-scope"
        >{{ filtered ? 'Vue filtrée' : 'Tous mes suivis' }} · Heures de Montréal</span
      >
    </form>
    <button v-if="role === 'administrator'" class="tasks-refresh" @click="policyOpen = true">
      Règles des suivis
    </button>
    <p v-if="boardMessage" role="alert" class="tasks-error">{{ boardMessage }}</p>
    <div class="tasks-layout">
      <div
        class="tasks-columns"
        role="region"
        tabindex="0"
        aria-label="Tableau des tâches par état"
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
            <span>{{
              column.busy && !column.page ? '…' : column.error && !column.page ? '—' : column.count
            }}</span>
          </header>
          <p class="task-column-hint">{{ column.hint }}</p>
          <div
            class="task-column-stack"
            role="region"
            tabindex="0"
            :aria-label="`Tâches ${column.label.toLocaleLowerCase('fr')}`"
          >
            <div v-if="column.error" class="tasks-error" role="alert">
              <p>{{ column.error }}</p>
              <button
                class="tasks-filter"
                :disabled="column.busy"
                @click="loadColumn(column, generation, column.page > 0)"
              >
                Réessayer
              </button>
            </div>
            <div v-if="column.busy && !column.page" class="task-empty" role="status">
              <ListTodo :size="22" /><strong>Chargement des suivis…</strong>
            </div>
            <div v-else-if="!column.error && !column.count" class="task-empty">
              <component :is="column.icon" :size="23" /><strong>{{
                filtered
                  ? 'Aucun suivi correspondant'
                  : column.key === 'closed'
                    ? 'La suite s’écrit ici'
                    : column.key === 'overdue'
                      ? 'Tout est dans les temps'
                      : 'Rien à traiter ici'
              }}</strong>
              <p>
                {{
                  filtered
                    ? 'Aucune tâche pour ces filtres.'
                    : column.key === 'closed'
                      ? 'Vos tâches terminées apparaîtront ici.'
                      : column.key === 'overdue'
                        ? 'Aucune échéance dépassée pour le moment.'
                        : 'Les rappels et suivis de rendez-vous apparaîtront ici.'
                }}
              </p>
            </div>
            <div v-for="row in column.rows" :key="row.id" class="task-card">
              <div class="task-card-top">
                <button :disabled="opening" @click="open(row)">
                  {{ row.contact_name || 'Prospect sans nom' }}</button
                ><span class="task-priority" :class="row.priority"
                  ><Flag :size="10" />{{ priorityLabels[row.priority] || row.priority }}</span
                >
              </div>
              <div class="task-deadline" :class="{ 'deadline-late': row.overdue }">
                <Clock3 :size="13" /><time :datetime="row.closed_at || row.due_at"
                  >{{ row.closed_at ? 'Clôturée le ' : 'Échéance : '
                  }}{{ date(row.closed_at || row.due_at) }}</time
                >
              </div>
              <p class="task-reason">{{ row.reason }}</p>
              <div v-if="row.closed_at" class="task-completed">
                <CheckCircle2 :size="13" />Suivi terminé
              </div>
              <div v-else-if="row.latest_incident" class="task-incident">
                <AlertCircle :size="13" />Signalement à consulter
              </div>
              <span v-else class="task-context">{{
                row.appointment_id ? 'Suivi de rendez-vous' : 'Rappel du prospect'
              }}</span>
              <footer class="task-card-footer">
                <span
                  ><CalendarDays :size="13" />{{
                    row.appointment_id ? 'RDV #' + row.appointment_id : 'Rappel contact'
                  }}</span
                ><button
                  :disabled="opening"
                  :aria-label="`Ouvrir le suivi de ${row.contact_name || 'ce prospect'}`"
                  @click="open(row)"
                >
                  Ouvrir<ArrowUpRight :size="15" />
                </button>
              </footer>
            </div>
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
          <span class="progress-kicker">CHAQUE SUIVI COMPTE</span>
          <h2>{{ role === 'administrator' ? 'Avancement de l’équipe' : 'Mon avancement' }}</h2>
          <p>
            {{
              filtered ? 'Sur les tâches correspondant aux filtres' : 'Sur l’ensemble de mes tâches'
            }}
          </p>
          <p v-if="summaryBusy" role="status">Chargement…</p>
          <div v-else-if="summaryError" role="alert">
            <p>{{ summaryError }}</p>
            <button class="tasks-filter" @click="loadSummary(generation)">Réessayer</button>
          </div>
          <template v-else-if="summary"
            ><div class="progress-main">
              <div
                class="task-donut"
                :style="{ '--progress': `${percentage ?? 0}%` }"
                role="img"
                :aria-label="
                  percentage === null
                    ? 'Aucune tâche à mesurer'
                    : `${percentage} % des tâches clôturées`
                "
              >
                <strong>{{ percentage === null ? '—' : percentage + '%' }}</strong
                ><small>Clôturées</small>
              </div>
              <div>
                <strong>{{ summary.open }}</strong
                ><span>suivi(s) ouvert(s)</span>
              </div>
            </div>
            <div class="progress-stat">
              <span>Clôturées</span
              ><strong>{{
                summary.total ? summary.closed + ' / ' + summary.total : 'Aucune tâche'
              }}</strong>
            </div>
            <div class="progress-track">
              <span :style="{ width: `${percentage ?? 0}%` }"></span>
            </div>
            <div class="progress-stat">
              <span>En retard</span
              ><strong>{{
                summary.open ? summary.overdue + ' / ' + summary.open : 'Aucune ouverte'
              }}</strong>
            </div>
            <div class="progress-track warm">
              <span
                :style="{ width: `${summary.open ? (100 * summary.overdue) / summary.open : 0}%` }"
              ></span></div
          ></template>
        </div>
        <div class="task-priorities">
          <header>
            <h2>{{ role === 'administrator' ? 'Priorités de l’équipe' : 'Mes priorités' }}</h2>
            <Flag :size="17" />
          </header>
          <p>Les tâches encore ouvertes</p>
          <template v-if="summary && !summaryBusy && !summaryError"
            ><div v-for="item in priorityRows" :key="item.key" class="priority-row">
              <span><i :class="item.key"></i>{{ item.label }}</span
              ><strong>{{ item.count }}</strong>
            </div></template
          >
          <p v-else>
            {{ summaryBusy ? 'Chargement…' : 'Le résumé des priorités est indisponible.' }}
          </p>
        </div>
        <div class="tasks-help">
          <ShieldCheck :size="23" /><strong>Un suivi bien terminé</strong>
          <p>
            Renseignez ce qui a été fait avant de clôturer. Votre résolution reste conservée dans le
            dossier.
          </p>
        </div>
      </aside>
    </div>
    <SidePanel
      :open="!!selected"
      :title="selected?.contact_name || 'Tâche de suivi'"
      eyebrow="MON SUIVI PROSPECT"
      :subtitle="
        selected
          ? `Tâche #${selected.id}${selected.appointment_id ? ' · RDV #' + selected.appointment_id : ' · Rappel contact'}`
          : ''
      "
      :close-disabled="saving || adminBusy"
      @request-close="role === 'administrator' ? adminEditor?.close() : closePanel()"
      ><AssuranceFollowUps
        v-if="selected && role === 'administrator' && portal"
        ref="adminEditor"
        :key="selected.id"
        role="administrator"
        :task-id="selected.id"
        :portal="portal"
        :request="request"
        @busy="adminBusy = $event"
        @changed="
          load();
          emit('changed');
        "
        @close="selected = null"
      />
      <div v-else-if="selected" class="task-detail">
        <p v-if="confirmed" role="status" class="task-success">
          <CheckCircle2 :size="18" />Tâche clôturée. Votre résolution a été enregistrée.
        </p>
        <p v-if="detailError" role="alert" class="tasks-error">{{ detailError }}</p>
        <div v-if="discard" class="task-discard">
          <strong>Garder votre justification ?</strong>
          <p>Elle n’a pas encore été enregistrée.</p>
          <button class="tasks-filter" @click="discard = false">Continuer la saisie</button
          ><button
            class="tasks-filter"
            @click="
              resolution = '';
              discard = false;
              selected = null;
            "
          >
            Abandonner et fermer
          </button>
        </div>
        <div class="task-detail-status">
          <span :class="selected.priority">{{
            priorityLabels[selected.priority] || selected.priority
          }}</span
          ><strong>{{
            selected.closed_at ? 'Clôturée' : selected.overdue ? 'Échéance dépassée' : 'À traiter'
          }}</strong>
        </div>
        <dl>
          <div>
            <dt>Échéance</dt>
            <dd>{{ date(selected.due_at) }} · Montréal</dd>
          </div>
          <div>
            <dt>Origine</dt>
            <dd>
              {{
                selected.appointment_id
                  ? 'Rendez-vous #' + selected.appointment_id
                  : 'Rappel créé depuis le contact'
              }}
            </dd>
          </div>
        </dl>
        <section class="task-detail-block">
          <h3>Le suivi à réaliser</h3>
          <p>{{ selected.reason }}</p>
        </section>
        <section v-if="selected.latest_incident" class="task-detail-block incident">
          <h3>Dernier signalement</h3>
          <small>{{ date(selected.latest_incident.created_at) }} · Montréal</small>
          <p>{{ selected.latest_incident.note }}</p>
        </section>
        <section v-if="selected.closed_at" class="task-detail-block resolved">
          <h3>Résolution enregistrée</h3>
          <small>{{ date(selected.closed_at) }} · Montréal</small>
          <p>{{ selected.resolution }}</p>
        </section>
        <template v-if="!selected.closed_at"
          ><button
            class="tasks-filter"
            :disabled="saving"
            @click="editing ? (editing = false) : editTask()"
          >
            {{ editing ? 'Annuler la modification' : 'Modifier le rappel' }}
          </button>
          <form v-if="editing" class="task-resolution-form" @submit.prevent="saveTask">
            <h3>Modifier mon suivi</h3>
            <label
              >Date et heure · Montréal<input
                v-model="editDue"
                type="datetime-local"
                required
                :disabled="saving" /></label
            ><label
              >Note<textarea
                v-model="editReason"
                maxlength="3000"
                required
                :disabled="saving"
              ></textarea></label
            ><label
              >Priorité<select v-model="editPriority" :disabled="saving">
                <option v-for="(label, key) in priorityLabels" :key="key" :value="key">
                  {{ label }}
                </option>
              </select></label
            ><button class="tasks-finish" :disabled="saving">Enregistrer les modifications</button>
          </form></template
        >
        <form
          v-if="!selected.closed_at && !editing"
          id="task-resolution-form"
          class="task-resolution-form"
          @submit.prevent="finish"
        >
          <h3>Terminer ce suivi</h3>
          <p>Décrivez l’action réalisée et le résultat obtenu.</p>
          <label
            >Votre résolution<textarea
              v-model="resolution"
              required
              maxlength="3000"
              :disabled="saving"
              placeholder="Ex. : prospect recontacté, informations complétées…"
            ></textarea></label
          ><span>{{ resolution.length }} / 3 000</span>
        </form>
        <button v-if="detailError" class="tasks-filter" :disabled="saving" @click="reloadSelected">
          Actualiser la tâche
        </button>
      </div>
      <template #footer
        ><div v-if="role === 'administrator'" class="task-detail-footer">
          <button class="tasks-filter" :disabled="adminBusy" @click="adminEditor?.close()">
            Fermer
          </button>
        </div>
        <div v-else class="task-detail-footer">
          <button class="tasks-filter" :disabled="saving" @click="closePanel">Fermer</button
          ><button
            v-if="selected && !selected.closed_at && !editing"
            class="tasks-finish"
            type="submit"
            form="task-resolution-form"
            :disabled="saving || !resolution.trim()"
          >
            <CheckCircle2 :size="16" />{{ saving ? 'Enregistrement…' : 'Clôturer le suivi' }}
          </button>
        </div></template
      ></SidePanel
    ><SidePanel
      :open="policyOpen"
      title="Règles des suivis"
      eyebrow="ASSURANCE · ADMINISTRATION"
      :close-disabled="policyBusy"
      @request-close="policyEditor?.close()"
      ><AssuranceFollowUpPolicy
        ref="policyEditor"
        @busy="policyBusy = $event"
        @close="policyOpen = false"
        v-if="policyOpen && role === 'administrator'"
        :request="request"
    /></SidePanel>
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
