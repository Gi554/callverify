<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import {
  CalendarCheck,
  CircleCheck,
  UserX,
  FileWarning,
  Download,
  Info,
  RefreshCw,
} from 'lucide-vue-next';
const props = defineProps<{
  role: string;
  request: (path: string, body?: any, method?: string) => Promise<any>;
}>();
const DAY = 86400000;
const iso = (date: Date) => date.toISOString().slice(0, 10);
const today = new Date(),
  from = ref(iso(new Date(today.getTime() - 29 * DAY))),
  to = ref(iso(today)),
  page = ref(1),
  result = ref<any>(null),
  busy = ref(false),
  error = ref('');
// Quick periods only fill the dates; the API and its UTC day bounds are unchanged.
const presets = [
  {
    id: '7',
    label: '7 jours',
    range: () => [iso(new Date(Date.now() - 6 * DAY)), iso(new Date())],
  },
  {
    id: '30',
    label: '30 jours',
    range: () => [iso(new Date(Date.now() - 29 * DAY)), iso(new Date())],
  },
  {
    id: 'month',
    label: 'Ce mois',
    range: () => {
      const now = new Date();
      return [iso(new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1))), iso(now)];
    },
  },
  {
    id: 'previous',
    label: 'Mois dernier',
    range: () => {
      const now = new Date();
      return [
        iso(new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - 1, 1))),
        iso(new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 0))),
      ];
    },
  },
];
const activePreset = computed(
  () => presets.find((preset) => preset.range().join() === [from.value, to.value].join())?.id || '',
);
function applyPreset(id: string) {
  const preset = presets.find((item) => item.id === id);
  if (!preset) return;
  [from.value, to.value] = preset.range() as [string, string];
  page.value = 1;
  void load();
}
const totals = computed(() => result.value?.totals || {});
const value = (key: string) => (totals.value[key] === null ? '—' : (totals.value[key] ?? 0));
const rate = computed(() => totals.value.performed_rate);
const period = computed(() => {
  const format = (day: string) =>
    new Intl.DateTimeFormat('fr-FR', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      timeZone: 'UTC',
    }).format(new Date(day + 'T12:00:00Z'));
  return `Du ${format(from.value)} au ${format(to.value)}`;
});
const secondary = [
  { key: 'incidents', label: 'Signalements ultérieurs' },
  { key: 'problem_reports', label: 'Comptes rendus avec problème' },
  { key: 'open_tasks', label: 'Tâches ouvertes' },
  { key: 'overdue_tasks', label: 'Tâches en retard' },
  { key: 'closed_tasks', label: 'Tâches clôturées' },
];
async function load() {
  busy.value = true;
  error.value = '';
  try {
    result.value = await props.request(
      `statistics/?from=${from.value}&to=${to.value}&page=${page.value}`,
    );
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function download(kind: string) {
  busy.value = true;
  error.value = '';
  try {
    const blob = await props.request(
      `statistics/?from=${from.value}&to=${to.value}&export=${kind}`,
    );
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `statistiques-assurance-${from.value}-${to.value}.${kind}`;
    link.click();
    URL.revokeObjectURL(url);
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
onMounted(load);
</script>

<template>
  <section class="stats">
    <header class="stats-toolbar">
      <div class="stats-presets" role="group" aria-label="Période">
        <button
          v-for="preset in presets"
          :key="preset.id"
          type="button"
          :class="{ 'is-active': activePreset === preset.id }"
          :aria-pressed="activePreset === preset.id"
          :disabled="busy"
          @click="applyPreset(preset.id)"
        >
          {{ preset.label }}
        </button>
      </div>
      <form
        class="stats-range"
        @submit.prevent="
          page = 1;
          load();
        "
      >
        <label>Du<input v-model="from" type="date" required /></label>
        <label>Au<input v-model="to" type="date" required /></label>
        <button class="primary" :disabled="busy"><RefreshCw :size="15" />Calculer</button>
      </form>
      <div class="stats-exports">
        <span><Download :size="15" />Exporter</span>
        <button class="secondary" :disabled="busy" @click="download('xlsx')">Excel</button>
        <button class="secondary" :disabled="busy" @click="download('csv')">CSV</button>
      </div>
    </header>
    <p v-if="error" role="alert" class="stats-error">{{ error }}</p>
    <p class="stats-period">
      {{ period }} · {{ role === 'administrator' ? 'toute l’équipe' : 'vos rendez-vous' }}
      <span v-if="result"> · calculé le {{ new Date(result.as_of).toLocaleString('fr-FR') }}</span>
    </p>
    <p v-if="busy && !result" role="status" class="stats-loading">Calcul des statistiques…</p>
    <template v-if="result">
      <div class="stats-kpis">
        <article class="stat-card">
          <span class="stat-icon blue"><CalendarCheck :size="20" /></span>
          <small>Rendez-vous</small>
          <strong>{{ value('appointments') }}</strong>
          <p>{{ value('cancelled') }} annulés · {{ value('upcoming') }} à venir</p>
        </article>
        <article class="stat-card">
          <span class="stat-icon green"><CircleCheck :size="20" /></span>
          <small>Taux effectué</small>
          <strong>{{ rate === null || rate === undefined ? '—' : rate + ' %' }}</strong>
          <div class="stat-bar" aria-hidden="true">
            <span :style="{ width: (rate || 0) + '%' }"></span>
          </div>
          <p>{{ value('performed') }} effectués sur {{ value('reported') }} comptes rendus</p>
        </article>
        <article class="stat-card">
          <span class="stat-icon violet"><UserX :size="20" /></span>
          <small>Absences déclarées</small>
          <strong>{{ value('absent') }}</strong>
          <p>{{ value('other_not_performed') }} non effectués pour un autre motif</p>
        </article>
        <article class="stat-card" :class="{ warning: Number(totals.reports_due) > 0 }">
          <span class="stat-icon orange"><FileWarning :size="20" /></span>
          <small>Comptes rendus manquants</small>
          <strong>{{ value('reports_due') }}</strong>
          <p>Rendez-vous passés sans compte rendu du conseiller</p>
        </article>
      </div>
      <ul class="stats-secondary">
        <li v-for="item in secondary" :key="item.key">
          <strong>{{ value(item.key) }}</strong
          >{{ item.label }}
        </li>
      </ul>
      <div v-if="result.setters" class="stats-table">
        <h4>Détail par setter</h4>
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Setter</th>
                <th>RDV</th>
                <th>Effectués</th>
                <th>Non effectués</th>
                <th>CR manquants</th>
                <th>Tâches</th>
                <th>Taux effectué</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in result.setters.results" :key="row.setter_id">
                <td>{{ row.setter_name }}</td>
                <td data-label="RDV">{{ row.appointments }}</td>
                <td data-label="Effectués">{{ row.performed }}</td>
                <td data-label="Non effectués">
                  {{ row.not_performed
                  }}<small v-if="row.absent"> dont {{ row.absent }} absents</small>
                </td>
                <td data-label="CR manquants">
                  <span :class="['stats-badge', { warning: row.reports_due > 0 }]">{{
                    row.reports_due
                  }}</span>
                </td>
                <td data-label="Tâches">
                  {{ row.open_tasks }} ouvertes<small v-if="row.overdue_tasks">
                    · {{ row.overdue_tasks }} en retard</small
                  >
                </td>
                <td data-label="Taux effectué">
                  <div class="rate">
                    <span class="rate-bar" aria-hidden="true"
                      ><span :style="{ width: (row.performed_rate || 0) + '%' }"></span></span
                    >{{ row.performed_rate === null ? '—' : row.performed_rate + ' %' }}
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <footer class="stats-pages">
          <span>{{ result.setters.count }} setter(s) · page {{ page }}</span>
          <button
            class="secondary"
            :disabled="busy || !result.setters.previous"
            @click="
              page--;
              load();
            "
          >
            Précédent</button
          ><button
            class="secondary"
            :disabled="busy || !result.setters.next"
            @click="
              page++;
              load();
            "
          >
            Suivant
          </button>
        </footer>
      </div>
      <details class="stats-method">
        <summary><Info :size="15" />Comment sont calculés ces chiffres ?</summary>
        <p>{{ result.definition }}</p>
        <p>
          Une reprogrammation peut déplacer un rendez-vous dans une autre période. Les exports
          reprennent les dates choisies et tout le périmètre autorisé, au-delà de la page affichée.
        </p>
        <p>
          Les appels Phonetico, contrats et conversions commerciales ne sont pas encore
          comptabilisés.
        </p>
      </details>
    </template>
  </section>
</template>

<style scoped>
.stats {
  display: grid;
  gap: 18px;
}
.stats-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: 14px 20px;
}
.stats-presets {
  display: inline-flex;
  padding: 3px;
  border-radius: 10px;
  background: #eef1f6;
}
.stats-presets button {
  border: 0;
  border-radius: 8px;
  background: none;
  color: #5b6b82;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.stats-presets button.is-active {
  background: white;
  color: #1f2f45;
  box-shadow: 0 1px 4px #1f2f4518;
}
.stats-range {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: 10px;
}
.stats-range label {
  display: grid;
  gap: 4px;
  font-size: 12px;
  color: #5b6b82;
}
.stats-range button,
.stats-exports span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.stats-exports {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
  font-size: 12px;
  color: #5b6b82;
}
.stats-period {
  margin: 0;
  color: #5b6b82;
  font-size: 13px;
}
.stats-error {
  color: #b42318;
}
.stats-kpis {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 14px;
}
.stat-card {
  display: grid;
  gap: 6px;
  align-content: start;
  padding: 16px 18px;
  border: 1px solid #e3e7ee;
  border-radius: 14px;
  background: white;
}
.stat-card.warning {
  border-color: #f4c38b;
  background: #fffaf3;
}
.stat-card small {
  color: #5b6b82;
  font-size: 12px;
  font-weight: 600;
}
.stat-card strong {
  font-size: 28px;
  line-height: 1.1;
  color: #1f2f45;
  font-variant-numeric: tabular-nums;
}
.stat-card p {
  margin: 0;
  color: #6b7686;
  font-size: 12px;
}
.stat-icon {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
}
.stat-icon.blue {
  background: #e7f0fd;
  color: #1f5fa8;
}
.stat-icon.green {
  background: #e3f4ea;
  color: #23784a;
}
.stat-icon.violet {
  background: #efeafb;
  color: #6b4fc5;
}
.stat-icon.orange {
  background: #fdeedd;
  color: #b4610c;
}
.stat-bar,
.rate-bar {
  display: block;
  height: 6px;
  border-radius: 99px;
  background: #e8edf3;
  overflow: hidden;
}
.stat-bar span,
.rate-bar span {
  display: block;
  height: 100%;
  background: #23784a;
}
.stats-secondary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.stats-secondary li {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 99px;
  background: #f3f5f8;
  color: #5b6b82;
  font-size: 12px;
}
.stats-secondary strong {
  color: #1f2f45;
  font-size: 14px;
}
.stats-table h4 {
  margin: 6px 0 10px;
}
.stats-table td small {
  color: #6b7686;
}
.stats-badge {
  display: inline-block;
  min-width: 24px;
  padding: 2px 8px;
  border-radius: 99px;
  background: #f3f5f8;
  text-align: center;
}
.stats-badge.warning {
  background: #fdeedd;
  color: #b4610c;
  font-weight: 600;
}
.rate {
  display: grid;
  grid-template-columns: 70px auto;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}
.stats-pages {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  color: #5b6b82;
  font-size: 12px;
}
.stats-pages span {
  margin-right: auto;
}
.stats-method {
  padding: 12px 16px;
  border-radius: 12px;
  background: #f6f8fb;
  color: #5b6b82;
  font-size: 13px;
}
.stats-method summary {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-weight: 600;
  color: #1f2f45;
}
@media (max-width: 700px) {
  .stats-exports {
    margin-left: 0;
  }
}
</style>
