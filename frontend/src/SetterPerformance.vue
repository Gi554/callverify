<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed } from 'vue';
import { BarChart3 } from 'lucide-vue-next';
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
  busy = ref(false),
  error = ref(''),
  callError = ref('');
let version = 0;
const admin = computed(() => props.role === 'administrator');
const metrics = [
  { key: 'assigned_now', label: 'Prospects affectés actuellement' },
  { key: 'current_assignments_in_period', label: 'Affectations actuelles reçues sur la période' },
  { key: 'qualified', label: 'Fiches qualifiées dans les rendez-vous' },
  { key: 'scheduled', label: 'Rendez-vous planifiés' },
  { key: 'held', label: 'Rendez-vous tenus' },
  { key: 'closed', label: 'Ventes conclues' },
  { key: 'not_closed', label: 'Ventes non conclues' },
  { key: 'not_held', label: 'Rendez-vous non tenus' },
  { key: 'awaiting_result', label: 'Résultats attendus' },
  { key: 'sale_unknown', label: 'Résultat commercial attendu' },
];
const days = computed(() => data.value?.daily || []);
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
      <label v-if="admin"
        >Setter<select v-model="agent" :disabled="busy" @change="load">
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
    <template v-if="data"
      ><h2><BarChart3 :size="20" />{{ data.agent_name }}</h2>
      <div class="performance-kpis">
        <StatKpi
          v-for="item in metrics"
          :key="item.key"
          :label="item.label"
          :value="data.totals[item.key]"
        />
      </div>
      <section class="iso-panel">
        <h2>Appels Orvia</h2>
        <p v-if="callError" role="alert" class="error">{{ callError }}</p>
        <div class="performance-kpis">
          <StatKpi label="Tentatives émises" :value="calls?.totals.attempts ?? '—'" /><StatKpi
            label="Appels acceptés par le poste"
            :value="calls?.totals.calls ?? '—'"
          /><StatKpi label="Réponses incertaines" :value="calls?.totals.uncertain ?? '—'" /><StatKpi
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
}
</style>
