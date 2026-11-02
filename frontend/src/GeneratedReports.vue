<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';
import { FileBarChart, Download, Plus, CalendarClock } from 'lucide-vue-next';
import IsolationPageHeader from './IsolationPageHeader.vue';
import SidePanel from './SidePanel.vue';
const props = defineProps<{
  workspace: string;
  request: (path: string, body?: any) => Promise<any>;
}>();
const day = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'America/Toronto',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
}).format(new Date());
const kinds: Record<string, string> = {
  performance: 'Performance des agents',
  campaigns: 'Campagnes et lots',
  financial: 'Rémunérations et soldes',
};
const cadence: Record<string, string> = {
  manual: 'À la demande',
  daily: 'Quotidien',
  weekly: 'Hebdomadaire',
  monthly: 'Mensuel',
};
const eventLabels: Record<string, string> = {
  'report.requested': 'Rapport demandé',
  'report.started': 'Génération démarrée',
  'report.completed': 'Génération terminée',
  'report.failed': 'Échec de génération',
  'report.downloaded': 'Téléchargement',
};
const rows = ref<any[]>([]),
  count = ref(0),
  page = ref(1),
  busy = ref(false),
  error = ref(''),
  message = ref(''),
  plan = ref({ enabled: false, hour: 19, revision: 0, authorized: true }),
  dirty = ref(false),
  loaded = ref(false),
  panel = ref(false),
  history = ref<any>(null),
  events = ref<any[]>([]);
const form = ref({ kind: 'performance', starts_on: day.slice(0, 8) + '01', ends_on: day });
let requestId = crypto.randomUUID();
let version = 0,
  timer: ReturnType<typeof setInterval> | undefined;
const date = (value: string) =>
  new Intl.DateTimeFormat('fr-CA', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'America/Toronto',
  }).format(new Date(value));
function state(row: any) {
  return row.state === 'succeeded'
    ? 'Disponible'
    : row.state === 'running'
      ? 'En préparation'
      : row.state === 'queued'
        ? 'En attente'
        : row.attempts < 3
          ? 'Nouvelle tentative prévue'
          : 'Échec de génération';
}
async function load() {
  const current = ++version;
  busy.value = true;
  error.value = '';
  try {
    const [p, data] = await Promise.all([
      props.request(props.workspace + '/report-plan/'),
      props.request(props.workspace + '/reports/?page=' + page.value),
    ]);
    if (current === version) {
      if (!dirty.value) plan.value = p;
      rows.value = data.results;
      count.value = data.count;
      loaded.value = true;
    }
  } catch (e: any) {
    if (current === version) {
      error.value = e.message || 'Rapports indisponibles.';
      loaded.value = false;
    }
  } finally {
    if (current === version) busy.value = false;
  }
}
async function save() {
  busy.value = true;
  error.value = '';
  try {
    plan.value = await props.request(props.workspace + '/report-plan/', plan.value);
    dirty.value = false;
    message.value = 'Planification enregistrée.';
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
function open() {
  requestId = crypto.randomUUID();
  panel.value = true;
}
async function create() {
  busy.value = true;
  error.value = '';
  try {
    await props.request(props.workspace + '/reports/', {
      ...form.value,
      request_id: requestId,
    });
    panel.value = false;
    page.value = 1;
    message.value = 'Rapport demandé. Les fichiers apparaîtront après génération.';
    await load();
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function download(row: any, format: string) {
  busy.value = true;
  error.value = '';
  try {
    const blob = await props.request(`${props.workspace}/reports/${row.id}/download/${format}/`);
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `orvia-${props.workspace}-${row.kind}-${row.starts_on}-${row.ends_on}.${format}`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function showHistory(row: any) {
  history.value = row;
  events.value = [];
  busy.value = true;
  try {
    events.value = (await props.request(`${props.workspace}/reports/${row.id}/history/`)).results;
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
onMounted(() => {
  load();
  timer = setInterval(() => {
    if (!document.hidden && !busy.value && !panel.value && !history.value) load();
  }, 60000);
});
onBeforeUnmount(() => {
  version++;
  if (timer) clearInterval(timer);
});
</script>
<template>
  <div class="iso-page generated-reports">
    <IsolationPageHeader
      title="Rapports"
      subtitle="Vos rapports de performance, de campagnes et de rémunération, en PDF et Excel."
      :eyebrow="'ADMINISTRATION · ' + workspace.toUpperCase()"
      :busy="busy"
      @refresh="load"
      ><template #actions
        ><button class="primary" :disabled="busy" @click="open">
          <Plus :size="16" />Nouveau rapport
        </button></template
      ></IsolationPageHeader
    >
    <p v-if="error" role="alert" class="error">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <form v-if="loaded" class="iso-panel report-plan" @submit.prevent="save">
      <h2><CalendarClock :size="20" />Planification automatique</h2>
      <label class="plan-check"
        ><input
          v-model="plan.enabled"
          type="checkbox"
          :disabled="busy"
          @change="dirty = true"
        />Activer les rapports automatiques pour cet espace</label
      ><label
        >Heure de génération au Québec<select
          v-model.number="plan.hour"
          :disabled="busy"
          @change="dirty = true"
        >
          <option v-for="h in 24" :key="h - 1" :value="h - 1">{{ h - 1 }} h</option>
        </select></label
      >
      <p>
        Chaque jour : la veille. Chaque lundi : la semaine précédente. Le premier du mois : le mois
        précédent. Trois rapports sont produits à chaque échéance. Les fichiers restent consultables
        dans cet espace ; aucun courriel n’est envoyé.
      </p>
      <p v-if="plan.enabled && !plan.authorized" role="alert" class="error">
        Le compte qui autorisait cette planification n’a plus accès à cet espace. Enregistrez de
        nouveau la planification depuis un compte administrateur actif.
      </p>
      <button class="primary" :disabled="busy || !dirty">Enregistrer la planification</button>
    </form>
    <section v-if="loaded" class="iso-panel">
      <header class="iso-panel-heading">
        <div>
          <h2><FileBarChart :size="20" />Historique des rapports</h2>
          <p>Les fichiers terminés conservent les chiffres capturés lors de leur génération.</p>
        </div>
      </header>
      <article v-for="row in rows" :key="row.id" class="report-row">
        <div>
          <strong>{{ kinds[row.kind] }}</strong>
          <p>{{ row.starts_on }} → {{ row.ends_on }} · {{ cadence[row.cadence] }}</p>
          <span :class="['report-state', row.state]">{{ state(row) }}</span
          ><small
            >Demandé le {{ date(row.created_at)
            }}<template v-if="row.completed_at">
              · Terminé le {{ date(row.completed_at) }}</template
            ></small
          >
        </div>
        <div class="report-actions">
          <button
            v-if="row.state === 'succeeded'"
            class="secondary"
            :disabled="busy"
            @click="download(row, 'pdf')"
          >
            <Download :size="14" />PDF</button
          ><button
            v-if="row.state === 'succeeded'"
            class="secondary"
            :disabled="busy"
            @click="download(row, 'xlsx')"
          >
            Excel</button
          ><button class="secondary" :disabled="busy" @click="showHistory(row)">Historique</button>
        </div>
      </article>
      <p v-if="!rows.length">
        Aucun rapport généré. Activez la planification ou demandez un premier rapport.
      </p>
      <footer class="iso-pagination">
        <span>{{ count }} rapport(s) · Page {{ page }}</span
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
    </section>
    <SidePanel
      :open="panel"
      title="Générer un rapport"
      eyebrow="RAPPORTS · HEURE DU QUÉBEC"
      :close-disabled="busy"
      @request-close="panel = false"
      ><form class="report-form" @submit.prevent="create">
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <label
          >Rapport<select v-model="form.kind" :disabled="busy">
            <option v-for="(label, key) in kinds" :key="key" :value="key">{{ label }}</option>
          </select></label
        ><label>Du<input v-model="form.starts_on" type="date" required :disabled="busy" /></label
        ><label
          >Au inclus<input v-model="form.ends_on" type="date" required :max="day" :disabled="busy"
        /></label>
        <p>
          La génération prépare les deux formats. Une nouvelle demande produit un nouvel instantané
          ; les rapports précédents sont conservés.
        </p>
        <button class="primary" :disabled="busy">Générer PDF et Excel</button>
      </form></SidePanel
    >
    <SidePanel
      :open="!!history"
      title="Historique du rapport"
      eyebrow="TRAÇABILITÉ"
      :close-disabled="busy"
      @request-close="history = null"
      ><article v-for="item in events" :key="item.id" class="report-row">
        <div>
          <strong>{{ eventLabels[item.action] || item.action }}</strong>
          <p>Compte #{{ item.actor_id }} · {{ date(item.created_at) }}</p>
          <p v-if="item.metadata.format">Format : {{ item.metadata.format }}</p>
        </div>
      </article>
      <p v-if="!busy && !events.length">Aucun événement enregistré pour ce rapport.</p></SidePanel
    >
  </div>
</template>
<style scoped>
.report-plan {
  display: grid;
  gap: 14px;
}
.report-plan label {
  display: grid;
  gap: 8px;
  max-width: 440px;
  font-size: 13px;
}
.report-plan .plan-check {
  display: flex;
  align-items: center;
}
.report-plan p,
.report-form p {
  font-size: 12px;
  line-height: 1.65;
  color: #64758d;
}
.report-plan button {
  justify-self: start;
}
.report-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 20px 0;
  border-bottom: 1px solid #e4eaf3;
}
.report-row p,
.report-row small {
  display: block;
  font-size: 12px;
  color: #65758d;
}
.report-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.report-state {
  display: inline-block;
  border-radius: 99px;
  padding: 5px 10px;
  background: #f1eefc;
  color: #684fca;
  font-size: 11px;
  margin: 4px 0 8px;
}
.report-state.succeeded {
  background: #e4f6ee;
  color: #198464;
}
.report-state.failed {
  background: #fff0e6;
  color: #b86b2e;
}
.report-form {
  display: grid;
  gap: 16px;
}
.report-form label {
  display: grid;
  gap: 8px;
}
@media (max-width: 650px) {
  .report-row {
    align-items: flex-start;
    flex-direction: column;
  }
  .report-actions {
    width: 100%;
  }
  .report-actions button {
    flex: 1;
  }
  .report-plan button {
    width: 100%;
  }
}
</style>
