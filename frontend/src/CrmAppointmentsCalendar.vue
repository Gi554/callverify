<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount } from 'vue';
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Plus,
  Clock3,
  RefreshCw,
  ArrowRight,
  Search,
} from 'lucide-vue-next';
import SidePanel from './SidePanel.vue';
import { appointmentStatus, appointmentStatusLabels, appointmentTone } from './appointment-status';
import AssuranceAppointments from './AssuranceAppointments.vue';
import AssuranceAdvisorAppointment from './AssuranceAdvisorAppointment.vue';
import IsolationVisits from './IsolationVisits.vue';
import {
  dayKey,
  monthGrid,
  gridWindow,
  eventsForDay,
  loadCalendarRows,
  calendarCells,
} from './calendar-grid';
const props = defineProps<{
  workspace: string;
  role: string;
  request: (path: string, body?: any, method?: string) => Promise<any>;
  portal: (path: string, body?: any) => Promise<any>;
}>();
const emit = defineEmits<{ navigate: [value: string]; changed: [] }>();
const zone = ref('America/Toronto'),
  month = ref(dayKey(new Date(), zone.value).slice(0, 7)),
  status = ref(''),
  search = ref('');
const rows = ref<any[]>([]),
  busy = ref(false),
  error = ref(''),
  loadedCount = ref(0),
  expectedCount = ref(0);
const selected = ref<any>(null),
  selectedDay = ref(''),
  creating = ref(false),
  detailBusy = ref(false);
const advisorDetail = ref<InstanceType<typeof AssuranceAdvisorAppointment> | null>(null);
const assurance = computed(() => props.workspace === 'assurance'),
  canBook = computed(() => ['setter', 'administrator'].includes(props.role)),
  admin = computed(() => props.role === 'administrator');
// Administrator only: the existing list keeps its management tools.
const listView = ref(false);
// Team filter: participants are only exposed to administrators. Members met in any loaded
// month stay selectable; a selected member is filtered by the API, not only in the browser.
const member = ref('');
const known = ref<Record<string, Record<string, string>>>({});
const memberKinds = computed(() =>
  assurance.value
    ? [
        { kind: 'setter', label: 'Setters', of: (row: any) => row.setter },
        { kind: 'advisor', label: 'Conseillers', of: (row: any) => row.advisor },
      ]
    : [
        { kind: 'setter', label: 'Setters', of: (row: any) => row.original_setter },
        { kind: 'closer', label: 'Closers', of: (row: any) => row.closer },
        { kind: 'client', label: 'Clients', of: (row: any) => row.client },
      ],
);
function remember(loaded: any[]) {
  for (const { kind, of } of memberKinds.value) {
    const people = { ...known.value[kind] };
    for (const row of loaded) {
      const person = of(row);
      if (person?.id != null) people[String(person.id)] = person.name || `#${person.id}`;
    }
    known.value = { ...known.value, [kind]: people };
  }
}
const memberParams: Record<string, string> = {
  setter: 'setter_id',
  advisor: 'advisor_id',
  closer: 'closer_id',
  client: 'client_id',
};
const memberGroups = computed(() =>
  memberKinds.value
    .map(({ kind, label }) => {
      return {
        kind,
        label,
        options: Object.entries(known.value[kind] || {})
          .map(([id, name]) => ({ value: `${kind}:${id}`, name }))
          .sort((a, b) => a.name.localeCompare(b.name, 'fr')),
      };
    })
    .filter((group) => group.options.length),
);
function matchesMember(row: any) {
  if (!member.value) return true;
  const [kind, id] = member.value.split(':');
  const person = memberKinds.value.find((entry) => entry.kind === kind)?.of(row);
  return String(person?.id ?? '') === id;
}
const days = computed(() => monthGrid(month.value)),
  today = computed(() => dayKey(new Date(), zone.value));
const title = computed(() =>
  new Intl.DateTimeFormat('fr-FR', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(
    new Date(month.value + '-01T12:00:00Z'),
  ),
);
const weekday = computed(() =>
  new Intl.DateTimeFormat('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    timeZone: zone.value,
  }).format(new Date()),
);
const filtered = computed(() => {
  const term = search.value.trim().toLocaleLowerCase('fr');
  return rows.value.filter((row) => {
    const person = row.contact || row.prospect;
    if (!matchesMember(row)) return false;
    return (
      !term ||
      [
        person?.name,
        person?.phone,
        row.advisor?.name,
        row.client?.name,
        row.setter?.name,
        row.original_setter?.name,
        row.closer?.name,
      ].some((value) =>
        String(value || '')
          .toLocaleLowerCase('fr')
          .includes(term),
      )
    );
  });
});
const cells = computed(() => calendarCells(filtered.value, days.value, zone.value));
const dayRows = computed(() =>
  selectedDay.value ? eventsForDay(filtered.value, selectedDay.value, zone.value) : [],
);
const monthCount = computed(
  () =>
    filtered.value.filter(
      (row) =>
        dayKey(row.starts_at, zone.value).slice(0, 7) <= month.value &&
        dayKey(new Date(Date.parse(row.ends_at) - 1), zone.value).slice(0, 7) >= month.value,
    ).length,
);
function person(row: any) {
  return (
    (row.contact || row.prospect)?.name ||
    (row.contact || row.prospect)?.phone ||
    'Prospect sans nom'
  );
}
function time(value: string) {
  return new Intl.DateTimeFormat('fr-FR', {
    timeZone: zone.value,
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}
function fullDay(value: string) {
  return new Intl.DateTimeFormat('fr-FR', {
    timeZone: 'UTC',
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(new Date(value + 'T12:00:00Z'));
}
function color(row: any) {
  if (assurance.value) return appointmentTone(row);
  return row.status === 'cancelled'
    ? 'cancelled'
    : ['peach', 'violet', 'mint', 'blue'][Number(row.advisor?.id ?? row.client?.id ?? row.id) % 4];
}
function move(delta: number) {
  const date = new Date(month.value + '-01T12:00:00Z');
  date.setUTCMonth(date.getUTCMonth() + delta);
  month.value = date.toISOString().slice(0, 7);
}
let generation = 0,
  disposed = false;
async function load() {
  const version = ++generation;
  busy.value = true;
  error.value = '';
  rows.value = [];
  loadedCount.value = 0;
  expectedCount.value = 0;
  try {
    const window = gridWindow(days.value, zone.value),
      query = new URLSearchParams({
        ...window,
        ...(assurance.value ? { business_status: status.value } : { status: status.value }),
        page_size: '100',
      });
    if (member.value) {
      const [kind, id] = member.value.split(':');
      query.set(memberParams[kind], id);
    }
    const result = await loadCalendarRows(
      props.request,
      assurance.value ? 'appointments' : 'visits',
      query,
      () => version === generation && !disposed,
      (loaded, total) => {
        loadedCount.value = loaded;
        expectedCount.value = total;
      },
    );
    if (result) {
      rows.value = result;
      remember(result);
    }
  } catch (e: any) {
    if (version === generation && !disposed) error.value = e.message;
  } finally {
    if (version === generation && !disposed) busy.value = false;
  }
}
function open(row: any) {
  selectedDay.value = '';
  selected.value = row;
}
function closeDetail() {
  if (detailBusy.value) return;
  if (advisorDetail.value && !advisorDetail.value.close()) return;
  selected.value = null;
  void load();
}
watch([month, zone, status, member], load, { immediate: true });
onBeforeUnmount(() => {
  disposed = true;
  generation++;
});
</script>
<template>
  <section class="appointment-calendar">
    <header class="calendar-heading">
      <div>
        <span class="calendar-eyebrow"
          >{{ admin ? 'ÉQUIPE' : 'MON ESPACE' }} {{ assurance ? 'ASSURANCE' : 'ISOLATION' }}</span
        >
        <h1>{{ assurance ? 'Rendez-vous' : 'Visites' }}</h1>
        <p>
          {{ admin ? 'L’agenda de toute l’équipe.' : 'Vos prochains échanges prennent place ici.' }}
        </p>
      </div>
      <div v-if="admin" class="calendar-view-switch" role="group" aria-label="Affichage">
        <button
          :class="{ 'is-active': !listView }"
          :aria-pressed="!listView"
          @click="listView = false"
        >
          Calendrier</button
        ><button
          :class="{ 'is-active': listView }"
          :aria-pressed="listView"
          @click="listView = true"
        >
          Liste
        </button>
      </div>
      <button v-if="canBook && !listView" class="calendar-new" @click="creating = true">
        <Plus :size="16" />Réserver un {{ assurance ? 'rendez-vous' : 'créneau' }}
      </button>
    </header>
    <div v-if="admin && listView" class="calendar-list-view">
      <AssuranceAppointments
        v-if="assurance"
        :request="request"
        :portal="portal"
        :role="role"
      /><IsolationVisits
        v-else
        :role="role"
        :portal="portal"
        :request="request"
        @close="listView = false"
        @changed="emit('changed')"
      />
    </div>
    <div v-else class="calendar-surface">
      <div class="calendar-toolbar">
        <div class="calendar-today">
          <strong>{{ weekday }}</strong
          ><span>{{
            busy
              ? 'Chargement…'
              : `${monthCount} ${assurance ? 'rendez-vous' : 'visite(s)'} sur ce mois`
          }}</span>
        </div>
        <div class="calendar-month-nav">
          <button aria-label="Mois précédent" :disabled="month <= '1901-01'" @click="move(-1)">
            <ChevronLeft :size="17" />
          </button>
          <h2 aria-live="polite">{{ title }}</h2>
          <button aria-label="Mois suivant" :disabled="month >= '2099-12'" @click="move(1)">
            <ChevronRight :size="17" />
          </button>
        </div>
        <div class="calendar-toolbar-end">
          <button class="calendar-today-button" @click="month = today.slice(0, 7)">
            Aujourd’hui</button
          ><button
            class="calendar-icon-button"
            :disabled="busy"
            aria-label="Actualiser le calendrier"
            @click="load"
          >
            <RefreshCw :size="16" />
          </button>
        </div>
      </div>
      <div class="calendar-filters">
        <label class="calendar-search"
          ><Search :size="15" /><input
            v-model="search"
            :placeholder="admin ? 'Prospect ou membre de l’équipe…' : 'Prospect ou conseiller…'"
            aria-label="Rechercher dans les rendez-vous chargés" /></label
        ><label v-if="admin" class="calendar-select"
          ><span>Membre de l’équipe</span
          ><select v-model="member">
            <option value="">Toute l’équipe</option>
            <optgroup v-for="group in memberGroups" :key="group.kind" :label="group.label">
              <option v-for="option in group.options" :key="option.value" :value="option.value">
                {{ option.name }}
              </option>
            </optgroup>
            <option
              v-if="
                member &&
                !memberGroups.some((group) =>
                  group.options.some((option) => option.value === member),
                )
              "
              :value="member"
            >
              Membre sans rendez-vous ce mois
            </option>
          </select></label
        ><label class="calendar-select"
          ><span>Statut</span
          ><select v-model="status">
            <option value="">Tous les statuts</option>
            <template v-if="assurance"
              ><option v-for="(label, key) in appointmentStatusLabels" :key="key" :value="key">
                {{ label }}
              </option></template
            ><template v-else
              ><option value="scheduled">Planifiés</option>
              <option value="cancelled">Annulés</option></template
            >
          </select></label
        ><label class="calendar-select"
          ><span>Heures affichées</span
          ><select v-model="zone">
            <option value="America/Toronto">Toronto / Montréal</option>
            <option value="America/Vancouver">Vancouver</option>
            <option value="America/Edmonton">Edmonton</option>
            <option value="America/Winnipeg">Winnipeg</option>
            <option value="America/Halifax">Halifax</option>
            <option value="America/St_Johns">Saint-Jean</option>
          </select></label
        >
      </div>
      <div v-if="error" class="calendar-error" role="alert">
        <strong>Le calendrier n’a pas pu être chargé.</strong>
        <p>{{ error }}</p>
        <button class="calendar-today-button" @click="load">Réessayer</button>
      </div>
      <p v-else-if="busy" class="calendar-notice" role="status">
        Chargement des rendez-vous{{ expectedCount ? ` · ${loadedCount} / ${expectedCount}` : '…' }}
      </p>
      <p v-else-if="!filtered.length" class="calendar-notice" role="status">
        {{
          search.trim() || member
            ? 'Aucun rendez-vous ne correspond à votre recherche.'
            : 'Aucun rendez-vous pour cette période et ce statut.'
        }}
      </p>
      <p class="calendar-mobile-hint">
        Faites défiler le calendrier vers la droite pour voir toute la semaine.<ArrowRight
          :size="13"
        />
      </p>
      <div
        class="calendar-scroll"
        tabindex="0"
        role="region"
        :aria-label="`Calendrier de ${title}`"
        :aria-busy="busy"
      >
        <div class="calendar-weekdays">
          <span
            v-for="(day, index) in ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']"
            :key="day"
            :class="{
              'weekday-today':
                (new Date(today + 'T12:00:00Z').getUTCDay() + 6) % 7 === index &&
                month === today.slice(0, 7),
            }"
            >{{ day }}</span
          >
        </div>
        <div class="calendar-grid">
          <div
            v-for="cell in cells"
            :key="cell.day"
            class="calendar-cell"
            :class="{
              'outside-month': !cell.day.startsWith(month),
              'is-today': cell.day === today,
              'is-weekend': [0, 6].includes(new Date(cell.day + 'T12:00:00Z').getUTCDay()),
            }"
          >
            <button
              class="calendar-day"
              :aria-label="`${fullDay(cell.day)} : ${cell.rows.length} rendez-vous`"
              :aria-current="cell.day === today ? 'date' : undefined"
              @click="selectedDay = cell.day"
            >
              <time :datetime="cell.day">{{ Number(cell.day.slice(-2)) }}</time>
            </button>
            <button
              v-for="row in cell.rows.slice(0, 3)"
              :key="row.id"
              class="calendar-event"
              :class="color(row)"
              :title="`${person(row)} · ${time(row.starts_at)} – ${time(row.ends_at)} · ${zone}`"
              @click="open(row)"
            >
              <strong>{{ person(row) }}</strong
              ><small v-if="row.advisor">{{ row.advisor.name }}</small
              ><span><Clock3 :size="11" />{{ time(row.starts_at) }} – {{ time(row.ends_at) }}</span
              ><small v-if="assurance || row.status === 'cancelled'">{{
                assurance ? appointmentStatus(row) : 'Annulé'
              }}</small>
            </button>
            <button
              v-if="cell.rows.length > 3"
              class="calendar-more"
              @click="selectedDay = cell.day"
            >
              + {{ cell.rows.length - 3 }} autres
            </button>
          </div>
        </div>
      </div>
      <footer class="calendar-footer">
        <span><span class="legend-dot"></span>Planifié</span
        ><template v-if="assurance"
          ><span><span class="legend-dot done"></span>Fait</span
          ><span><span class="legend-dot absent"></span>Absent / non effectué</span
          ><span><span class="legend-dot pending"></span>Report / à renseigner</span></template
        ><span><span class="legend-dot cancelled"></span>Annulé</span
        ><small>Cliquer sur un créneau pour consulter et gérer le rendez-vous.</small>
      </footer>
    </div>
    <SidePanel
      :open="!!selected"
      :title="selected ? person(selected) : 'Rendez-vous'"
      eyebrow="RENDEZ-VOUS"
      :subtitle="
        selected
          ? assurance
            ? appointmentStatus(selected)
            : selected.status === 'cancelled'
              ? 'Annulé'
              : 'Planifié'
          : ''
      "
      :close-disabled="detailBusy"
      @request-close="closeDetail"
      ><AssuranceAdvisorAppointment
        v-if="selected && assurance && role === 'advisor'"
        :key="selected.id"
        ref="advisorDetail"
        :appointment-id="selected.id"
        :request="request"
        @busy="detailBusy = $event"
        @updated="selected = $event" /><AssuranceAppointments
        v-else-if="selected && assurance"
        :key="selected.id"
        :appointment-id="selected.id"
        :request="request"
        :portal="portal"
        :role="role"
        @busy="detailBusy = $event"
        @updated="selected = $event" /><IsolationVisits
        v-else-if="selected"
        :key="selected.id"
        :visit-id="selected.id"
        :request="request"
        :portal="portal"
        :role="role"
        @busy="detailBusy = $event"
        @updated="selected = $event"
        @close="closeDetail"
    /></SidePanel>
    <SidePanel
      :open="!!selectedDay"
      :title="selectedDay ? fullDay(selectedDay) : 'Rendez-vous du jour'"
      eyebrow="MON AGENDA"
      @request-close="selectedDay = ''"
      ><div class="calendar-day-list">
        <p v-if="!dayRows.length">
          Aucun rendez-vous ce jour. Pour réserver, ouvrez d’abord la fiche du prospect.
        </p>
        <button
          v-for="row in dayRows"
          :key="row.id"
          class="calendar-event"
          :class="color(row)"
          @click="open(row)"
        >
          <strong>{{ person(row) }}</strong
          ><span>{{ time(row.starts_at) }} – {{ time(row.ends_at) }} · {{ zone }}</span
          ><small>{{
            assurance ? appointmentStatus(row) : row.status === 'cancelled' ? 'Annulé' : 'Planifié'
          }}</small>
        </button>
      </div></SidePanel
    >
    <SidePanel
      :open="creating"
      title="Préparer un rendez-vous"
      eyebrow="UNE NOUVELLE RENCONTRE"
      @request-close="creating = false"
      ><div class="calendar-booking-intro">
        <span><CalendarDays :size="32" /></span>
        <h3>Tout commence par un prospect</h3>
        <p>
          Ouvrez sa fiche, complétez les informations utiles puis choisissez un
          {{
            assurance
              ? 'conseiller attribué et un créneau dans son agenda'
              : 'créneau pour le client Isolation'
          }}.
        </p>
        <ol>
          <li>Choisir le prospect</li>
          <li>{{ assurance ? 'Sélectionner le conseiller' : 'Compléter la fiche' }}</li>
          <li>Confirmer le rendez-vous</li>
        </ol>
        <p>Les conflits de calendrier sont contrôlés lors de la confirmation.</p>
        <button
          class="calendar-new"
          @click="
            creating = false;
            emit('navigate', 'contacts');
          "
        >
          Choisir un prospect<ArrowRight :size="17" />
        </button></div
    ></SidePanel>
  </section>
</template>
<style scoped>
.appointment-calendar {
  color: #282830;
  padding: 28px;
  background: #f5f5f8;
  min-height: calc(100dvh - 78px);
  font-family: Inter, 'Segoe UI', sans-serif;
  box-sizing: border-box;
}
.calendar-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  margin: 0 0 26px;
}
.calendar-eyebrow {
  font-size: 9px;
  letter-spacing: 1.7px;
  color: #9b90aa;
  font-weight: 650;
}
.calendar-heading h1 {
  font-size: 28px;
  letter-spacing: -0.8px;
  color: #29242f;
  margin: 8px 0;
}
.calendar-heading p {
  font-size: 12px;
  color: #93909e;
  margin: 0;
}
.appointment-calendar button {
  font-family: inherit;
  cursor: pointer;
}
.appointment-calendar button:disabled {
  opacity: 0.45;
  cursor: wait;
}
.calendar-view-switch {
  display: inline-flex;
  margin-left: auto;
  padding: 3px;
  border-radius: 10px;
  background: #f1eff4;
}
.calendar-view-switch button {
  border: 0;
  border-radius: 8px;
  background: none;
  color: #5d5866;
  padding: 9px 15px;
  font-size: 12px;
  font-weight: 550;
  cursor: pointer;
}
.calendar-view-switch button.is-active {
  background: white;
  color: #242127;
  box-shadow: 0 1px 4px #24212718;
}
.calendar-new {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 9px;
  background: #242127;
  border: 0;
  border-radius: 9px;
  color: white;
  padding: 13px 17px;
  font-size: 12px;
  font-weight: 550;
  white-space: nowrap;
  cursor: pointer;
}
.calendar-new:hover {
  background: #494050;
}
.calendar-surface {
  border: 1px solid #ebe9ef;
  border-radius: 18px;
  background: white;
  padding: 24px;
  box-shadow: 0 8px 30px #28233403;
}
.calendar-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin: 0 0 22px;
}
.calendar-today strong {
  display: block;
  font-size: 16px;
  font-weight: 600;
  text-transform: capitalize;
  letter-spacing: -0.3px;
}
.calendar-today > span {
  display: block;
  font-size: 10px;
  color: #a19aa9;
  margin-top: 6px;
}
.calendar-month-nav {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 7px;
  border-radius: 9px;
  background: #f8f7f9;
}
.calendar-month-nav h2 {
  margin: 0;
  min-width: 140px;
  text-align: center;
  text-transform: capitalize;
  font-size: 13px !important;
  color: #403946;
  letter-spacing: -0.2px;
}
.calendar-month-nav button,
.calendar-icon-button {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border: 1px solid #eeeaf1;
  border-radius: 7px;
  background: white;
  color: #96889e;
  padding: 0;
}
.calendar-toolbar-end {
  display: flex;
  gap: 10px;
  align-items: center;
}
.calendar-today-button {
  background: white;
  border: 1px solid #e7e2eb;
  border-radius: 7px;
  padding: 9px 12px;
  color: #75697f;
  font-size: 11px;
  cursor: pointer;
}
.calendar-filters {
  display: flex;
  gap: 14px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 22px;
}
.calendar-search {
  display: flex !important;
  align-items: center;
  gap: 9px;
  border: 1px solid #ece8f0;
  border-radius: 8px;
  padding: 0 12px;
  max-width: 300px;
  flex: 1;
  color: #b0a5b7;
}
.appointment-calendar .calendar-search input {
  border: 0;
  background: none;
  padding: 10px 0;
  width: 100%;
  min-width: 0;
  outline: 0;
  box-shadow: none;
  font-size: 11px;
}
.calendar-select {
  display: flex !important;
  align-items: center;
  gap: 8px;
  color: #a298aa;
  font-size: 10px;
}
.appointment-calendar .calendar-select select {
  border: 1px solid #e9e5ee;
  background: #fff;
  padding: 9px 11px;
  border-radius: 7px;
  color: #6d6278;
  font-size: 11px;
  width: auto;
  max-width: 210px;
}
.calendar-scroll {
  overflow: auto;
  overscroll-behavior: contain;
}
.calendar-weekdays,
.calendar-grid {
  min-width: 720px;
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
}
.calendar-weekdays {
  gap: 1px;
  margin-bottom: 12px;
  background: repeating-linear-gradient(55deg, #faf9fb, #faf9fb 3px, #fff 3px, #fff 7px);
  border-radius: 8px;
  overflow: hidden;
}
.calendar-weekdays > span {
  text-align: center;
  padding: 13px 5px;
  font-size: 11px;
  font-weight: 550;
  color: #8f8498;
}
.calendar-weekdays > span.weekday-today {
  background: #ed9674;
  color: white;
  border-radius: 7px;
}
.calendar-grid {
  border-top: 1px solid #eae6ee;
  border-left: 1px solid #eae6ee;
}
.calendar-cell {
  min-width: 0;
  min-height: 134px;
  border-right: 1px solid #eae6ee;
  border-bottom: 1px solid #eae6ee;
  padding: 7px;
  box-sizing: border-box;
  background: white;
}
.calendar-cell.is-weekend {
  background: #fdfcfe;
}
.calendar-cell.outside-month {
  background: #faf9fb;
}
.calendar-day {
  display: grid;
  place-items: center;
  background: none;
  border: 0;
  width: 25px;
  height: 25px;
  border-radius: 50%;
  padding: 0;
  margin: 0 0 6px;
  color: #887c94;
  font-size: 10px;
}
.outside-month .calendar-day {
  color: #c4bacd;
}
.is-today .calendar-day {
  background: #ee9674;
  color: white;
  font-weight: 700;
}
.calendar-event {
  display: block;
  width: 100%;
  border: 0;
  border-left: 2px solid #e9bdac;
  background: #fff1e9;
  border-radius: 4px;
  text-align: left;
  padding: 9px 8px;
  color: #826558;
  margin-bottom: 5px;
  transition:
    transform 0.15s,
    box-shadow 0.15s;
  cursor: pointer;
}
.calendar-event:hover {
  transform: translateY(-1px);
  box-shadow: 0 3px 9px #49335c12;
}
.calendar-event.violet {
  background: #f6edfb;
  border-left-color: #cbb2e3;
  color: #79568f;
}
.calendar-event.mint {
  background: #edf7f2;
  border-left-color: #b2d8c5;
  color: #4d7863;
}
.calendar-event.blue {
  background: #edf5fa;
  border-left-color: #b4d1e5;
  color: #507189;
}
.calendar-event.cancelled {
  background: #f3f1f4;
  border-left-color: #cac1cf;
  color: #7c7085;
}
.calendar-event.cancelled > strong {
  text-decoration: line-through;
}
.calendar-event strong {
  display: block;
  font-size: 10px;
  font-weight: 550;
  line-height: 1.5;
  overflow-wrap: anywhere;
}
.calendar-event small {
  display: block;
  font-size: 9px;
  line-height: 1.5;
  margin-top: 4px;
}
.calendar-event > span {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 9px;
  margin-top: 7px;
  white-space: nowrap;
}
.calendar-more {
  font-size: 10px;
  background: none;
  border: 0;
  color: #987aaa;
  padding: 5px;
}
.calendar-notice {
  background: #faf8fc;
  border-radius: 8px;
  color: #9985a9;
  padding: 12px 15px;
  font-size: 11px;
  line-height: 1.6;
  margin: 0 0 14px;
}
.calendar-error {
  color: #ad6f77;
  background: #fff4f4;
  padding: 15px;
  margin-bottom: 16px;
  border-radius: 10px;
  font-size: 12px;
}
.calendar-footer {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 18px 0 0;
  font-size: 10px;
  color: #a195aa;
}
.calendar-footer > span {
  display: flex;
  align-items: center;
  gap: 6px;
}
.legend-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #c7b1e3;
}
.legend-dot.done {
  background: #a6d1ba;
}
.legend-dot.absent {
  background: #e7baa6;
}
.legend-dot.pending {
  background: #c6b1e1;
}
.legend-dot.cancelled {
  background: #c7c2ca;
}
.calendar-footer small {
  margin-left: auto;
  font-size: 10px;
}
.calendar-day-list {
  display: grid;
  gap: 10px;
  color: #93869f;
  font-size: 13px;
  line-height: 1.7;
}
.calendar-day-list .calendar-event {
  padding: 18px;
}
.calendar-day-list .calendar-event strong {
  font-size: 14px;
}
.calendar-day-list .calendar-event span,
.calendar-day-list .calendar-event small {
  font-size: 12px;
}
.calendar-booking-intro {
  font-size: 13px;
  line-height: 1.8;
  color: #8e7f9b;
}
.calendar-booking-intro > span {
  display: grid;
  place-items: center;
  width: 70px;
  height: 70px;
  border-radius: 22px;
  background: #f0eafb;
  color: #a28ac2;
}
.calendar-booking-intro h3 {
  font-size: 20px !important;
  color: #786289;
  margin: 24px 0 10px;
}
.calendar-booking-intro ol {
  padding-left: 20px;
  margin: 25px 0;
}
.calendar-booking-intro li {
  padding: 5px;
}
.appointment-calendar button:focus-visible,
.calendar-scroll:focus-visible,
.calendar-search:focus-within {
  outline: 3px solid #c6b3e9;
  outline-offset: 3px;
}
@media (max-width: 1100px) {
  .calendar-toolbar {
    flex-wrap: wrap;
  }
  .calendar-toolbar-end {
    margin-left: auto;
  }
  .calendar-heading {
    align-items: flex-start;
  }
  .calendar-filters {
    gap: 10px;
  }
  .calendar-select {
    flex-wrap: wrap;
  }
  .calendar-surface {
    padding: 18px;
  }
}
@media (max-width: 650px) {
  .appointment-calendar {
    padding: 20px 14px;
  }
  .calendar-heading {
    flex-direction: column;
    gap: 17px;
  }
  .calendar-heading h1 {
    font-size: 25px;
  }
  .calendar-surface {
    padding: 14px;
    border-radius: 13px;
  }
  .calendar-toolbar {
    gap: 16px;
  }
  .calendar-today {
    width: 100%;
  }
  .calendar-month-nav {
    gap: 4px;
  }
  .calendar-month-nav h2 {
    min-width: 110px;
    font-size: 12px !important;
  }
  .calendar-today-button {
    font-size: 10px;
    padding: 9px;
  }
  .calendar-toolbar-end {
    gap: 6px;
  }
  .calendar-search {
    flex-basis: 100%;
    max-width: none;
  }
  .calendar-select {
    font-size: 9px;
  }
  .appointment-calendar .calendar-select select {
    max-width: 185px;
  }
  .calendar-footer {
    flex-wrap: wrap;
    gap: 12px;
  }
  .calendar-footer small {
    margin: 0;
    width: 100%;
  }
}
@media (prefers-reduced-motion: reduce) {
  .calendar-event {
    transition: none;
  }
  .calendar-event:hover {
    transform: none;
  }
}
.calendar-mobile-hint {
  display: none;
}
@media (max-width: 650px) {
  .calendar-mobile-hint {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 10px;
    color: #9986a7;
    line-height: 1.6;
  }
}
.calendar-cell {
  min-height: 105px;
}
.calendar-day {
  font-size: 11px;
  color: #756580;
}
.appointment-calendar
  .calendar-filters
  .calendar-search
  input:not([type='checkbox']):not([type='radio']):not([type='file']) {
  border: 0;
  background: none;
  box-shadow: none;
  padding: 10px 0;
  font-size: 12px;
  color: #706077;
}
.appointment-calendar .calendar-filters .calendar-select select {
  font-size: 12px;
  color: #786681;
  border-color: #e9e2ed;
  background: white;
}
.appointment-calendar .calendar-cell .calendar-event small {
  font-size: 10px;
  color: inherit;
}
.calendar-event strong {
  font-size: 11px;
}
.calendar-event > span {
  font-size: 10px;
}
</style>
