<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed } from 'vue';
import {
  BarChart3,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  PhoneCall,
  Users,
} from 'lucide-vue-next';
import IsolationPageHeader from './IsolationPageHeader.vue';
import StatKpi from './StatKpi.vue';
import StatBars from './StatBars.vue';
const props = defineProps<{
  workspace: string;
  role: string;
  request: (path: string) => Promise<any>;
  portal: (path: string) => Promise<any>;
}>();
const now = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'America/Toronto',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
}).format(new Date());
const from = ref(now.slice(0, 8) + '01'),
  to = ref(now),
  agents = ref<any[]>([]),
  agent = ref(''),
  data = ref<any>(null),
  calls = ref<any>(null),
  teamRows = ref<any[]>([]),
  teamBusy = ref(false),
  busy = ref(false),
  error = ref(''),
  callError = ref('');
const reportDay = ref(now);
let version = 0;
const admin = computed(() => props.role === 'administrator');
const metrics = [
  { key: 'booked', label: 'Rendez-vous pris pendant la période' },
  { key: 'upcoming', label: 'Rendez-vous à présenter' },
  { key: 'in_progress', label: 'Rendez-vous en cours' },
  { key: 'assigned_now', label: 'Prospects affectés actuellement' },
  { key: 'current_assignments_in_period', label: 'Affectations actuelles reçues sur la période' },
  { key: 'qualified', label: 'Fiches qualifiées dans les rendez-vous' },
  { key: 'scheduled', label: 'Rendez-vous planifiés' },
  { key: 'held', label: 'Rendez-vous présentés' },
  { key: 'cancelled', label: 'Rendez-vous annulés' },
  { key: 'closed', label: 'Ventes conclues' },
  { key: 'not_closed', label: 'Ventes non conclues' },
  { key: 'not_held', label: 'Rendez-vous non tenus' },
  { key: 'awaiting_result', label: 'Résultats attendus' },
  { key: 'sale_unknown', label: 'Résultat commercial attendu' },
];
const days = computed(() => data.value?.daily || []);
const reportDayLabel = computed(() =>
  new Intl.DateTimeFormat('fr-CA', {
    timeZone: 'America/Toronto',
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(new Date(`${reportDay.value}T12:00:00`)),
);
const callDays = computed(() =>
  days.value.map((row: any) => ({
    ...row,
    ...(calls.value?.daily.find((item: any) => item.day === row.day) || {
      calls: 0,
      attempts: 0,
      uncertain: 0,
    }),
  })),
);
function formatDuration(seconds: number | null | undefined) {
  if (seconds == null) return '—';
  const rounded = Math.round(seconds);
  return `${Math.floor(rounded / 60)} min ${String(rounded % 60).padStart(2, '0')} s`;
}
function teamCallCount(row: any, key: string) {
  return row.phone?.totals?.[key] ?? 0;
}
function callUserKey(value: unknown) {
  return String(value ?? '')
    .trim()
    .toLocaleLowerCase('fr-CA')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');
}
function shiftReportDay(offset: number) {
  const next = new Date(`${reportDay.value}T12:00:00`);
  next.setDate(next.getDate() + offset);
  reportDay.value = next.toISOString().slice(0, 10);
  // The team report is its own daily view. Do not overwrite the period used
  // by the selected setter below it.
  loadTeam();
}
function resetReportDay() {
  reportDay.value = now;
  // “Période complète” only resets the daily report cursor. The top period
  // remains the admin's selected analysis period.
  loadTeam();
}
async function loadTeam() {
  if (!admin.value || !agents.value.length) return;
  teamBusy.value = true;
  const query = new URLSearchParams({ from: reportDay.value, to: reportDay.value });
  try {
    const phone = await props.portal(
      `${props.workspace}/performance-calls/?${new URLSearchParams({
        from: reportDay.value,
        to: reportDay.value,
        team: '1',
      })}`,
    );
    const callsByUser = new Map<string, any>();
    for (const item of phone.team || []) {
      callsByUser.set(String(item.user_id), item);
      if (item.user__username) callsByUser.set(callUserKey(item.user__username), item);
    }
    const rows = await Promise.all(
      agents.value.map(async (item) => ({
        ...item,
        performance: await props.request(`setter-performance/${item.id}/?${query}`),
        phone: callsByUser.get(String(item.id)) || callsByUser.get(callUserKey(item.name)),
      })),
    );
    teamRows.value = rows;
  } catch (e: any) {
    callError.value = e.message || 'Rapport équipe indisponible.';
  } finally {
    teamBusy.value = false;
  }
}
async function load() {
  const current = ++version;
  busy.value = true;
  error.value = '';
  callError.value = '';
  data.value = null;
  calls.value = null;
  try {
    const suffix = agent.value ? agent.value + '/' : '';
    const value = await props.request(
      'setter-performance/' +
        suffix +
        '?' +
        new URLSearchParams({ from: from.value, to: to.value }),
    );
    if (current !== version) return;
    if (value.agents) {
      agents.value = value.agents;
      if (!agent.value && agents.value.length) {
        agent.value = String(agents.value[0].id);
        await load();
      }
      return;
    }
    data.value = value;
    try {
      const callData = await props.portal(
        props.workspace +
          '/performance-calls/?' +
          new URLSearchParams({
            from: from.value,
            to: to.value,
            setter_id: String(value.agent_id),
          }),
      );
      if (current === version) calls.value = callData;
    } catch (e: any) {
      if (current === version) callError.value = e.message || 'Compteurs d’appels indisponibles.';
    }
    if (current === version) await loadTeam();
  } catch (e: any) {
    if (current === version) error.value = e.message || 'Performance indisponible.';
  } finally {
    if (current === version) busy.value = false;
  }
}
onMounted(load);
onBeforeUnmount(() => version++);
</script>
<template>
  <div class="iso-page setter-performance">
    <IsolationPageHeader
      :title="admin ? 'Performance des setters' : 'Ma performance'"
      subtitle="Votre activité et vos résultats, dans un seul espace. Heure du Québec."
      :eyebrow="workspace.toUpperCase() + ' · PERFORMANCE'"
      :busy="busy"
      @refresh="load"
    />
    <form class="iso-panel performance-filters" @submit.prevent="load">
      <div class="filter-intro">
        <span class="filter-icon"><CalendarDays :size="18" /></span>
        <div>
          <strong>Période d’analyse</strong
          ><small>Heure du Québec · sélectionnez un setter ou toute l’équipe.</small>
        </div>
      </div>
      <label v-if="admin"
        >Setter à consulter<select v-model="agent" :disabled="busy" @change="load">
          <option v-for="item in agents" :key="item.id" :value="String(item.id)">
            {{ item.name }}
          </option>
        </select></label
      ><label>Du<input v-model="from" type="date" required :disabled="busy" /></label
      ><label>Au<input v-model="to" type="date" required :disabled="busy" /></label
      ><button class="primary" :disabled="busy">Afficher</button>
    </form>
    <p v-if="error" role="alert" class="error">{{ error }}</p>
    <p v-if="admin && !busy && !error && !agents.length">Aucun setter connu de cet espace.</p>
    <section v-if="admin && agents.length" class="iso-panel team-report">
      <div class="section-heading">
        <div>
          <div class="section-kicker"><Users :size="15" /> SUIVI DE L’ÉQUIPE</div>
          <h2>Rapport quotidien</h2>
          <p>Comparez les setters sur une journée précise.</p>
        </div>
        <div class="day-nav">
          <button
            type="button"
            class="icon-button"
            aria-label="Jour précédent"
            @click="shiftReportDay(-1)"
          >
            <ChevronLeft :size="18" />
          </button>
          <span
            ><strong>{{ reportDayLabel }}</strong
            ><small>Montréal</small></span
          >
          <button
            type="button"
            class="icon-button"
            aria-label="Jour suivant"
            @click="shiftReportDay(1)"
          >
            <ChevronRight :size="18" />
          </button>
          <button type="button" class="today-button" @click="resetReportDay">Aujourd’hui</button>
        </div>
      </div>
      <p v-if="teamBusy" class="loading-line" role="status">
        <span class="spinner" /> Calcul des performances…
      </p>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Setter</th>
              <th>Appels émis</th>
              <th>Poste accepté</th>
              <th>Incertain</th>
              <th>&gt; 1 minute</th>
              <th>Durée totale</th>
              <th>Durée moyenne</th>
              <th>RDV pris</th>
              <th>RDV présentés</th>
              <th>Ventes</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in teamRows"
              :key="row.id"
              :class="{ 'is-selected': String(row.id) === agent }"
              @click="
                agent = String(row.id);
                load();
              "
            >
              <td>
                <strong>{{ row.name }}</strong>
              </td>
              <td>{{ teamCallCount(row, 'attempts') }}</td>
              <td>{{ teamCallCount(row, 'calls') }}</td>
              <td>{{ teamCallCount(row, 'uncertain') }}</td>
              <td>{{ teamCallCount(row, 'calls_over_minute') }}</td>
              <td>{{ formatDuration(row.phone?.totals?.duration_total_seconds) }}</td>
              <td>{{ formatDuration(row.phone?.totals?.duration_average_seconds) }}</td>
              <td>{{ row.performance?.totals?.booked ?? '—' }}</td>
              <td>{{ row.performance?.totals?.held ?? '—' }}</td>
              <td>{{ row.performance?.totals?.closed ?? '—' }}</td>
            </tr>
            <tr v-if="!teamBusy && !teamRows.length">
              <td colspan="10">Aucune donnée sur cette période.</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="performance-definition">
        « Appels émis » correspond aux commandes acceptées, refusées ou incertaines enregistrées par
        Orvia. Un compteur à 0 signifie qu’aucune commande de ce setter n’est enregistrée sur la
        période. Les durées viennent du journal NEWT et peuvent rester en attente quelques minutes.
        « Poste accepté » ne signifie pas que le prospect a décroché.
      </p>
    </section>
    <template v-if="data"
      ><section class="selected-setter-heading">
        <div>
          <span class="selected-setter-eyebrow">DÉTAIL DU SETTER SÉLECTIONNÉ</span>
          <h2><BarChart3 :size="20" />{{ data.agent_name }}</h2>
        </div>
        <span class="selected-setter-period">{{ from }} → {{ to }}</span>
      </section>
      <section class="metric-group">
        <div class="metric-group-title"><CalendarDays :size="16" /> Rendez-vous</div>
        <div class="performance-kpis">
          <StatKpi
            v-for="item in metrics.slice(0, 3)"
            :key="item.key"
            :label="item.label"
            :value="data.totals[item.key]"
          />
        </div>
      </section>
      <section class="metric-group">
        <div class="metric-group-title"><Users :size="16" /> Portefeuille</div>
        <div class="performance-kpis">
          <StatKpi
            v-for="item in metrics.slice(3, 6)"
            :key="item.key"
            :label="item.label"
            :value="data.totals[item.key]"
          />
        </div>
      </section>
      <section class="metric-group">
        <div class="metric-group-title"><BarChart3 :size="16" /> Résultats commerciaux</div>
        <div class="performance-kpis">
          <StatKpi
            v-for="item in metrics.slice(6)"
            :key="item.key"
            :label="item.label"
            :value="data.totals[item.key]"
          />
        </div>
      </section>
      <section v-if="data.outcomes" class="iso-panel">
        <h2>Résultats d’appel déclarés pendant la période</h2>
        <div class="performance-kpis">
          <StatKpi
            v-for="item in data.outcomes"
            :key="item.key"
            :label="item.label"
            :value="item.count"
          />
        </div>
        <p class="performance-definition">
          Les résultats déclarés comptent les actions enregistrées. Les rendez-vous pris comptent
          les réservations effectivement créées.
        </p>
      </section>
      <section class="iso-panel calls-panel">
        <div class="section-kicker"><PhoneCall :size="15" /> TÉLÉPHONIE</div>
        <h2>Appels Orvia</h2>
        <p v-if="callError" role="alert" class="error">{{ callError }}</p>
        <div class="performance-kpis">
          <StatKpi label="Tentatives émises" :value="calls?.totals.attempts ?? '—'" /><StatKpi
            label="Appels acceptés par le poste"
            :value="calls?.totals.calls ?? '—'"
          /><StatKpi label="Réponses incertaines" :value="calls?.totals.uncertain ?? '—'" /><StatKpi
            label="Appels de plus d’une minute"
            :value="calls?.totals.calls_over_minute ?? '—'"
          /><StatKpi
            label="Durée totale"
            :value="formatDuration(calls?.totals.duration_total_seconds)"
          /><StatKpi
            label="Durée moyenne"
            :value="formatDuration(calls?.totals.duration_average_seconds)"
          /><StatKpi
            label="Prospects joints"
            value="Non disponible"
            hint="Le décrochage du poste ne prouve pas la réponse du prospect."
          />
        </div>
        <p v-if="calls" class="performance-definition">{{ calls.definition }}</p>
      </section>
      <StatBars
        title="Rendez-vous et résultats"
        :days="days"
        :series="[
          { key: 'scheduled', label: 'Planifiés', color: '#7661e8' },
          { key: 'held', label: 'Tenus', color: '#2f6fed' },
          { key: 'closed', label: 'Ventes', color: '#2ab48b' },
        ]"
      />
      <StatBars
        v-if="calls"
        title="Appels Orvia"
        :days="callDays"
        :series="[
          { key: 'attempts', label: 'Tentatives', color: '#a5b4fc' },
          { key: 'calls', label: 'Acceptés par le poste', color: '#2f6fed' },
        ]"
      />
      <p class="performance-definition">{{ data.definition }}</p></template
    >
  </div>
</template>
<style scoped>
.performance-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: 16px;
  padding: 18px;
  background: #fff;
}
.filter-intro {
  display: flex;
  align-items: center;
  gap: 11px;
  flex: 1 1 240px;
  color: #183a66;
}
.filter-intro small,
.day-nav small {
  display: block;
  margin-top: 3px;
  color: #72839c;
  font-size: 11px;
}
.filter-icon {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 11px;
  color: #2864b0;
  background: #edf4ff;
}
.performance-filters label {
  display: grid;
  gap: 8px;
  flex: 1 1 180px;
  font-size: 12px;
}
.performance-kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}
h2 {
  display: flex;
  align-items: center;
  gap: 9px;
}
.performance-definition {
  font-size: 12px;
  color: #65758e;
  line-height: 1.7;
}
.selected-setter-heading {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 16px;
  margin: 28px 0 14px;
  padding: 18px 20px;
  border: 1px solid #dce5f2;
  border-radius: 16px;
  background: linear-gradient(120deg, #f4f7ff, #ffffff);
}
.section-kicker {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #6f82a1;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
}
.metric-group {
  margin: 20px 0;
}
.metric-group-title {
  display: flex;
  align-items: center;
  gap: 7px;
  margin: 0 0 10px 2px;
  color: #2d5484;
  font-size: 13px;
  font-weight: 750;
}
.day-nav {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #294c79;
}
.day-nav > span {
  min-width: 150px;
  text-align: center;
  font-size: 12px;
}
.icon-button,
.today-button {
  border: 1px solid #d5e1f0;
  background: #fff;
  color: #2b5f9d;
  border-radius: 9px;
  cursor: pointer;
}
.icon-button {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  padding: 0;
}
.today-button {
  padding: 8px 10px;
  font-size: 11px;
}
.icon-button:hover,
.today-button:hover {
  background: #edf4ff;
}
.loading-line {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #58718f;
  font-size: 12px;
}
.spinner {
  width: 12px;
  height: 12px;
  border: 2px solid #d7e3f3;
  border-top-color: #2f6fed;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.calls-panel {
  border-top: 3px solid #2f6fed;
}
.selected-setter-heading h2 {
  margin: 6px 0 0;
  color: #173a67;
}
.selected-setter-eyebrow {
  color: #6d7fa0;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
}
.selected-setter-period {
  color: #61738f;
  font-size: 12px;
  white-space: nowrap;
}
.team-report tbody tr {
  cursor: pointer;
  transition: background 0.15s ease;
}
.team-report tbody tr:hover,
.team-report tbody tr.is-selected {
  background: #eef4ff;
}
.team-report .section-heading {
  display: flex;
  justify-content: space-between;
  align-items: start;
  gap: 16px;
}
.team-report .table-scroll {
  overflow-x: auto;
}
.team-report table {
  width: 100%;
  min-width: 900px;
  border-collapse: collapse;
}
.team-report th,
.team-report td {
  padding: 12px 10px;
  border-bottom: 1px solid #e3e9f3;
  text-align: left;
  white-space: nowrap;
}
.team-report th {
  color: #52647f;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
@media (max-width: 1000px) {
  .performance-kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 560px) {
  .performance-kpis {
    grid-template-columns: 1fr;
  }
  .performance-filters button {
    width: 100%;
  }
  .day-nav {
    width: 100%;
    justify-content: space-between;
    flex-wrap: wrap;
  }
  .day-nav > span {
    order: -1;
    width: 100%;
  }
}
</style>
