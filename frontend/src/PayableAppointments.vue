<script setup lang="ts">
// Appointments to pay for: counted from the recorded results, per setter and per period.
// The platform prices and pays nothing; it only gives the quantities.
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import IsolationPageHeader from './IsolationPageHeader.vue';
import StatKpi from './StatKpi.vue';
const props = defineProps<{
  workspace: string;
  role: string;
  request: (path: string) => Promise<any>;
}>();
const admin = computed(() => props.role === 'administrator');
const split = computed(() => props.workspace === 'isolation');
const day = (value: Date) =>
  new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/Toronto',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(value);
// Monday to Sunday of the current week, on the Québec calendar.
function thisWeek() {
  const today = new Date(day(new Date()) + 'T12:00:00Z');
  const monday = new Date(today.getTime() - ((today.getUTCDay() + 6) % 7) * 86400000);
  return { from: day(monday), to: day(new Date(monday.getTime() + 6 * 86400000)) };
}
const week = thisWeek();
const from = ref(week.from),
  to = ref(week.to),
  agent = ref(''),
  agents = ref<any[]>([]),
  data = ref<any>(null),
  busy = ref(false),
  error = ref('');
let version = 0;
const columns = computed(() =>
  split.value
    ? [
        { key: 'not_closed', label: 'Présentés – Non closés' },
        { key: 'closed', label: 'Présentés – Closés' },
        { key: 'payable', label: 'Total des rendez-vous payables' },
      ]
    : [
        { key: 'presented', label: 'Rendez-vous présentés' },
        { key: 'payable', label: 'Total des rendez-vous payables' },
      ],
);
async function load() {
  const current = ++version;
  busy.value = true;
  error.value = '';
  try {
    const params = new URLSearchParams({ from: from.value, to: to.value });
    if (admin.value && agent.value) params.set('agent', agent.value);
    const value = await props.request('payable-appointments/?' + params);
    if (current !== version) return;
    data.value = value;
    if (admin.value) agents.value = value.agents;
  } catch (e: any) {
    if (current === version) error.value = e.message || 'Chiffres indisponibles.';
  } finally {
    if (current === version) busy.value = false;
  }
}
function showWeek() {
  const current = thisWeek();
  from.value = current.from;
  to.value = current.to;
  void load();
}
onMounted(load);
onBeforeUnmount(() => version++);
</script>
<template>
  <div class="iso-page payable">
    <IsolationPageHeader
      :title="admin ? 'Suivi et rémunération' : 'Mes gains et mon objectif'"
      subtitle="Les rendez-vous à rémunérer, comptés à partir des résultats enregistrés. Heure du Québec."
      :eyebrow="workspace.toUpperCase() + ' · RENDEZ-VOUS PAYABLES'"
      :busy="busy"
      @refresh="load"
    />
    <form class="iso-panel payable-filters" @submit.prevent="load">
      <label v-if="admin"
        >Setter<select v-model="agent" :disabled="busy" @change="load">
          <option value="">Tous les setters</option>
          <option v-for="item in agents" :key="item.id" :value="String(item.id)">
            {{ item.name }}
          </option>
        </select></label
      ><label>Du<input v-model="from" type="date" required :disabled="busy" /></label
      ><label>Au<input v-model="to" type="date" required :disabled="busy" /></label
      ><button type="button" class="secondary" :disabled="busy" @click="showWeek">
        Cette semaine</button
      ><button class="primary" :disabled="busy">Afficher</button>
    </form>
    <p v-if="error" role="alert" class="error">{{ error }}</p>
    <template v-if="data">
      <p class="payable-scope">
        {{
          admin && !agent
            ? 'Toute l’équipe'
            : data.rows[0]?.agent_name ||
              agents.find((item) => String(item.id) === agent)?.name ||
              'Vos rendez-vous'
        }}
        · du {{ data.from }} au {{ data.to }}
      </p>
      <div class="payable-kpis">
        <StatKpi
          v-for="item in columns"
          :key="item.key"
          :label="item.label"
          :value="data.totals[item.key]"
        />
      </div>
      <section v-if="admin && !agent" class="iso-panel">
        <h2>Par setter</h2>
        <p v-if="!data.rows.length">Aucun rendez-vous payable sur cette période.</p>
        <div v-else class="payable-table">
          <table>
            <thead>
              <tr>
                <th>Setter</th>
                <th v-for="item in columns" :key="item.key">{{ item.label }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in data.rows" :key="row.agent_id">
                <td>
                  <strong>{{ row.agent_name }}</strong>
                </td>
                <td v-for="item in columns" :key="item.key">{{ row[item.key] }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
      <p class="payable-definition">{{ data.definition }}</p>
    </template>
  </div>
</template>
<style scoped>
.payable-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: 16px;
}
.payable-filters label {
  display: grid;
  gap: 8px;
  flex: 1 1 180px;
  font-size: 12px;
}
.payable-scope {
  margin: 18px 0 10px;
  color: #3a4b63;
  font-weight: 600;
}
.payable-kpis {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}
.payable-table {
  overflow-x: auto;
}
.payable-table table {
  width: 100%;
  border-collapse: collapse;
}
.payable-table th,
.payable-table td {
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid #eef1f6;
}
.payable-definition {
  font-size: 12px;
  color: #65758e;
  line-height: 1.7;
}
@media (max-width: 760px) {
  .payable-kpis {
    grid-template-columns: 1fr;
  }
  .payable-filters button {
    width: 100%;
  }
}
</style>
