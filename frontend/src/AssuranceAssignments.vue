<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import {
  Plus,
  Search,
  ArrowRight,
  History,
  PauseCircle,
  PlayCircle,
  RefreshCw,
  Users,
  CalendarCheck,
  Target,
} from 'lucide-vue-next';
import SidePanel from './SidePanel.vue';
import { loadQuotas, type AdvisorQuota } from './advisor-quota';
const props = defineProps<{
  role: string;
  request: (path: string, body?: any, method?: string) => Promise<any>;
  portal: (path: string, body?: any) => Promise<any>;
}>();
const emit = defineEmits<{ navigate: [value: string] }>();
const quotas = ref(new Map<number, AdvisorQuota>());
const quotaLoading = ref(true),
  quotaError = ref(false);
async function loadQuotaBoard() {
  quotaLoading.value = true;
  quotaError.value = false;
  try {
    quotas.value = await loadQuotas(props.portal, props.request);
  } catch {
    quotas.value = new Map();
    quotaError.value = true;
  } finally {
    quotaLoading.value = false;
  }
}
const rows = ref<any[]>([]),
  count = ref(0),
  page = ref(1),
  search = ref(''),
  state = ref(''),
  busy = ref(false),
  error = ref(''),
  message = ref('');
const directory = reactive<
  Record<string, { rows: any[]; page: number; count: number; search: string; selected: string }>
>({
  setter: { rows: [], page: 1, count: 0, search: '', selected: '' },
  advisor: { rows: [], page: 1, count: 0, search: '', selected: '' },
});
const creating = ref(false);
const history = ref<any[]>([]),
  historyPage = ref(1),
  historyCount = ref(0),
  historyRow = ref<any>(null);
const states = [
  { value: '', label: 'Toutes' },
  { value: 'true', label: 'Actives' },
  { value: 'false', label: 'Suspendues' },
];
const pickers = [
  { kind: 'setter', label: 'Setter', placeholder: 'Rechercher un setter' },
  { kind: 'advisor', label: 'Conseiller', placeholder: 'Rechercher un conseiller' },
];
const initials = (name: string) =>
  String(name || '?')
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase();
async function load() {
  const result = await props.request(
    `assignments/?page=${page.value}&search=${encodeURIComponent(search.value)}&active=${state.value}`,
  );
  rows.value = result.results;
  count.value = result.count;
}
async function loadPeople(role: string) {
  const group = directory[role];
  const result = await props.portal(
    `assurance/participants/?role=${role}&search=${encodeURIComponent(group.search)}&page=${group.page}`,
  );
  group.rows = result.results;
  group.count = result.count;
}
async function run(action: () => Promise<void>) {
  busy.value = true;
  error.value = '';
  message.value = '';
  try {
    await action();
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function people(role: string, step = 0) {
  await run(async () => {
    const group = directory[role];
    group.page = step ? group.page + step : 1;
    group.selected = '';
    await loadPeople(role);
  });
}
function filter(value = state.value) {
  state.value = value;
  void run(async () => {
    page.value = 1;
    await load();
  });
}
async function attest(setterId: number, advisorId: number) {
  return (
    await props.portal('assurance/participants/', { setter_id: setterId, advisor_id: advisorId })
  ).proof;
}
async function create() {
  await run(async () => {
    const proof = await attest(
      Number(directory.setter.selected),
      Number(directory.advisor.selected),
    );
    await props.request('assignments/', { proof });
    directory.setter.selected = '';
    directory.advisor.selected = '';
    page.value = 1;
    search.value = '';
    state.value = '';
    await load();
    creating.value = false;
    message.value = 'Conseiller associé au setter.';
  });
}
async function toggle(row: any) {
  await run(async () => {
    const body: any = { active: !row.active, revision: row.revision };
    if (body.active) body.proof = await attest(row.setter.id, row.advisor.id);
    await props.request(`assignments/${row.id}/`, body, 'PATCH');
    await load();
    message.value = body.active
      ? 'Association réactivée.'
      : 'Association suspendue. Les historiques sont conservés.';
  });
}
async function loadHistory() {
  const result = await props.request(
    `assignments/${historyRow.value.id}/history/?page=${historyPage.value}`,
  );
  history.value = result.results;
  historyCount.value = result.count;
}
function openHistory(row: any) {
  void run(async () => {
    historyRow.value = row;
    historyPage.value = 1;
    await loadHistory();
  });
}
function describe(entry: any) {
  if (entry.action === 'assignment.created') return 'Association créée';
  if (entry.action === 'assignment.updated')
    return entry.metadata?.after?.active ? 'Association réactivée' : 'Association suspendue';
  return entry.action;
}
onMounted(() =>
  run(async () => {
    await load();
    void loadQuotaBoard();
    if (props.role === 'administrator') {
      await loadPeople('setter');
      await loadPeople('advisor');
    }
  }),
);
</script>

<template>
  <section class="assignments" :class="{ 'setter-advisors': role !== 'administrator' }">
    <template v-if="role !== 'administrator'">
      <header class="advisors-heading">
        <div>
          <span class="advisors-eyebrow">MON ÉQUIPE · ASSURANCE</span>
          <h1>Mes conseillers<span>.</span></h1>
          <p>Les conseillers avec lesquels vous pouvez réserver vos rendez-vous.</p>
        </div>
        <button
          class="secondary"
          :disabled="busy"
          @click="
            run(async () => {
              await load();
              await loadQuotaBoard();
            })
          "
        >
          <RefreshCw :size="16" />Actualiser
        </button>
      </header>
      <div class="advisor-discovery">
        <div class="discovery-copy">
          <span class="discovery-mark"><Users :size="25" /></span>
          <div>
            <h2>Votre équipe, vos prochains rendez-vous.</h2>
            <p>Retrouvez vos conseillers et préparez la suite de chaque échange.</p>
          </div>
        </div>
        <form class="advisor-search" @submit.prevent="filter()">
          <label class="advisor-name-filter"
            ><span>Nom du conseiller</span
            ><input
              v-model="search"
              aria-label="Rechercher un conseiller"
              placeholder="Tous vos conseillers"
          /></label>
          <label class="advisor-state-filter"
            ><span>Association</span
            ><select
              v-model="state"
              aria-label="Filtrer les conseillers par association"
              @change="filter()"
            >
              <option value="">Toutes les associations</option>
              <option value="true">Actives</option>
              <option value="false">Suspendues</option>
            </select></label
          >
          <div class="advisor-search-context">
            <span>Décompte de l’objectif</span><strong>Rendez-vous tenus uniquement</strong>
          </div>
          <button class="advisor-search-submit" :disabled="busy" aria-label="Rechercher">
            <Search :size="23" />
          </button>
        </form>
      </div>
      <header class="advisor-list-heading">
        <div>
          <h2>
            Vos conseillers <span>{{ busy ? '…' : count }}</span>
          </h2>
          <p>Les conseillers avec lesquels vous pouvez réserver vos rendez-vous.</p>
        </div>
        <button
          v-if="search || state"
          class="secondary"
          :disabled="busy"
          @click="
            search = '';
            filter('');
          "
        >
          Tout afficher<ArrowRight :size="15" />
        </button>
      </header>
    </template>
    <p v-if="error" role="alert" class="assignments-error">{{ error }}</p>
    <p v-if="message" role="status" class="assignments-message">{{ message }}</p>
    <template v-if="role === 'administrator'">
      <header class="assignments-toolbar">
        <form class="assignments-search" @submit.prevent="filter()">
          <Search :size="16" />
          <input
            v-model="search"
            aria-label="Rechercher une association"
            placeholder="Nom du setter ou du conseiller"
          />
        </form>
        <div class="assignments-states" role="group" aria-label="État">
          <button
            v-for="option in states"
            :key="option.value"
            type="button"
            :class="{ 'is-active': state === option.value }"
            :aria-pressed="state === option.value"
            :disabled="busy"
            @click="filter(option.value)"
          >
            {{ option.label }}
          </button>
        </div>
        <button class="primary assignments-new" :disabled="busy" @click="creating = true">
          <Plus :size="16" />Nouvelle association
        </button>
      </header>
      <p class="assignments-hint">
        Un setter peut travailler avec plusieurs conseillers ; il ne réserve qu’avec ses
        associations actives. Suspendre une association conserve les rendez-vous déjà pris.
      </p>
    </template>
    <div v-if="role !== 'administrator'" class="advisor-grid" :aria-busy="busy">
      <article v-for="row in rows" :key="row.id" class="advisor-card">
        <header>
          <span class="advisor-monogram">{{ initials(row.advisor.name) }}</span>
          <div class="advisor-identity">
            <h2>{{ row.advisor.name }}</h2>
            <p class="advisor-speciality">Conseiller en sécurité financière</p>
          </div>
        </header>
        <div class="advisor-tags">
          <span :class="['state', row.active ? 'active' : 'suspended']">{{
            row.active ? 'Association active' : 'Association suspendue'
          }}</span>
        </div>
        <div class="advisor-quota">
          <span class="quota-caption"><Target :size="16" />Objectif du conseiller</span>
          <p v-if="quotaLoading">Chargement de l’objectif…</p>
          <p v-else-if="quotaError">Objectif indisponible</p>
          <template v-else-if="quotas.get(row.advisor.id)?.quota != null">
            <div class="quota-figure">
              <strong>{{ quotas.get(row.advisor.id)?.remaining }}</strong
              ><span>{{ ' ' }}restant(s) sur {{ quotas.get(row.advisor.id)?.quota }}</span>
            </div>
            <progress
              :value="
                Math.min(
                  quotas.get(row.advisor.id)?.attended || 0,
                  quotas.get(row.advisor.id)?.quota || 0,
                )
              "
              :max="quotas.get(row.advisor.id)?.quota || 1"
              :aria-label="'Progression de l’objectif de ' + row.advisor.name"
            ></progress>
            <small>{{ quotas.get(row.advisor.id)?.attended }} rendez-vous tenu(s) au total</small>
          </template>
          <p v-else class="quota-undefined">
            Objectif non défini<span>L’administrateur peut renseigner un quota.</span>
          </p>
        </div>
        <footer>
          <span class="advisor-booking-hint"
            ><CalendarCheck :size="16" />Depuis une fiche prospect</span
          ><button
            class="advisor-book"
            :disabled="!row.active || busy"
            @click="emit('navigate', 'contacts')"
          >
            Préparer un rendez-vous<ArrowRight :size="15" />
          </button>
        </footer>
      </article>
      <div v-if="!rows.length" class="advisors-empty">
        <Users :size="35" />
        <h2>
          {{
            busy
              ? 'Chargement des conseillers…'
              : search
                ? 'Aucun conseiller trouvé'
                : 'Votre équipe se prépare'
          }}
        </h2>
        <p>
          {{
            search
              ? 'Essayez un autre nom.'
              : 'Les conseillers associés à votre compte apparaîtront ici.'
          }}
        </p>
      </div>
    </div>
    <div v-else class="table-scroll">
      <table class="assignments-table">
        <thead>
          <tr>
            <th v-if="role === 'administrator'">Setter</th>
            <th>Conseiller</th>
            <th>Prospects à fournir</th>
            <th>État</th>
            <th v-if="role === 'administrator'"><span class="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id" :class="{ inactive: !row.active }">
            <td v-if="role === 'administrator'">
              <span class="person"
                ><span class="avatar">{{ initials(row.setter.name) }}</span
                >{{ row.setter.name }}</span
              >
            </td>
            <td data-label="Conseiller">
              <span class="person"
                ><ArrowRight v-if="role === 'administrator'" class="link-arrow" :size="15" /><span
                  class="avatar advisor"
                  >{{ initials(row.advisor.name) }}</span
                >{{ row.advisor.name }}</span
              >
            </td>
            <td data-label="Prospects à fournir">
              <span
                v-if="quotas.get(row.advisor.id)?.quota != null"
                :class="['quota', { done: !quotas.get(row.advisor.id)?.remaining }]"
                >{{ quotas.get(row.advisor.id)?.remaining }} restant(s) sur
                {{ quotas.get(row.advisor.id)?.quota }}</span
              ><span v-else class="quota unset">Non défini</span>
            </td>
            <td data-label="État">
              <span :class="['state', row.active ? 'active' : 'suspended']">{{
                row.active ? 'Active' : 'Suspendue'
              }}</span>
            </td>
            <td v-if="role === 'administrator'" class="row-actions">
              <button
                class="secondary"
                :disabled="busy"
                :title="row.active ? 'Suspendre l’association' : 'Réactiver l’association'"
                @click="toggle(row)"
              >
                <PauseCircle v-if="row.active" :size="15" /><PlayCircle v-else :size="15" />{{
                  row.active ? 'Suspendre' : 'Réactiver'
                }}</button
              ><button class="secondary" :disabled="busy" @click="openHistory(row)">
                <History :size="15" />Historique
              </button>
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td :colspan="role === 'administrator' ? 5 : 3" class="empty">
              {{ busy ? 'Chargement…' : 'Aucune association pour ces critères.' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <footer class="assignments-pages">
      <span>{{ count }} association(s) · page {{ page }}</span
      ><button
        class="secondary"
        :disabled="busy || page === 1"
        @click="
          run(async () => {
            page--;
            await load();
          })
        "
      >
        Précédent</button
      ><button
        class="secondary"
        :disabled="busy || page * 25 >= count"
        @click="
          run(async () => {
            page++;
            await load();
          })
        "
      >
        Suivant
      </button>
    </footer>
    <SidePanel
      v-if="role === 'administrator'"
      :open="creating"
      title="Nouvelle association"
      eyebrow="AFFECTATIONS"
      subtitle="Choisissez un setter actif et le conseiller avec lequel il pourra réserver."
      :close-disabled="busy"
      @request-close="creating = false"
    >
      <form class="assignment-create" @submit.prevent="create">
        <fieldset v-for="picker in pickers" :key="picker.kind" :disabled="busy">
          <legend>{{ picker.label }}</legend>
          <div class="picker-search">
            <input
              v-model="directory[picker.kind].search"
              :placeholder="picker.placeholder"
              @keydown.enter.prevent="people(picker.kind)"
            /><button type="button" class="secondary" @click="people(picker.kind)">
              <Search :size="15" />
            </button>
          </div>
          <select v-model="directory[picker.kind].selected" required :aria-label="picker.label">
            <option value="">Sélectionner…</option>
            <option
              v-for="person in directory[picker.kind].rows"
              :key="person.id"
              :value="String(person.id)"
            >
              {{ person.name }}
            </option>
          </select>
          <div class="picker-pages">
            <button
              type="button"
              class="secondary"
              :disabled="directory[picker.kind].page === 1"
              @click="people(picker.kind, -1)"
            >
              Précédent</button
            ><span>{{ directory[picker.kind].count }} compte(s)</span
            ><button
              type="button"
              class="secondary"
              :disabled="directory[picker.kind].page * 25 >= directory[picker.kind].count"
              @click="people(picker.kind, 1)"
            >
              Suivant
            </button>
          </div>
        </fieldset>
        <button
          class="primary"
          :disabled="busy || !directory.setter.selected || !directory.advisor.selected"
        >
          Associer ce conseiller au setter
        </button>
      </form>
    </SidePanel>
    <SidePanel
      v-if="role === 'administrator'"
      :open="!!historyRow"
      title="Historique de l’association"
      eyebrow="AFFECTATIONS"
      :subtitle="historyRow ? `${historyRow.setter.name} → ${historyRow.advisor.name}` : ''"
      :close-disabled="busy"
      @request-close="historyRow = null"
    >
      <ol class="history">
        <li v-for="entry in history" :key="entry.id">
          <strong>{{ describe(entry) }}</strong>
          <small
            >{{ new Date(entry.created_at).toLocaleString('fr-FR') }} · par l’utilisateur n°
            {{ entry.actor_id }}</small
          >
        </li>
        <li v-if="!history.length && !busy" class="empty">Aucun événement enregistré.</li>
      </ol>
      <div v-if="historyCount > 25" class="picker-pages">
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
        ><span>Page {{ historyPage }}</span
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
          Suivant
        </button>
      </div>
    </SidePanel>
  </section>
</template>

<style scoped>
.quota {
  font-weight: 600;
  color: #054f31;
}
.quota.done {
  color: #b54708;
}
.quota.unset {
  font-weight: 400;
  color: #667085;
}
.assignments {
  display: grid;
  gap: 14px;
}
.assignments-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}
.assignments-search {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1 1 260px;
  padding: 0 12px;
  border: 1px solid #dfe4ec;
  border-radius: 10px;
  background: white;
  color: #6b7686;
}
.assignments-search input {
  flex: 1;
  border: 0;
  padding: 10px 0;
  background: none;
  outline: none;
}
.assignments-states {
  display: inline-flex;
  padding: 3px;
  border-radius: 10px;
  background: #eef1f6;
}
.assignments-states button {
  border: 0;
  border-radius: 8px;
  background: none;
  color: #5b6b82;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.assignments-states button.is-active {
  background: white;
  color: #1f2f45;
  box-shadow: 0 1px 4px #1f2f4518;
}
.assignments-new,
.row-actions button,
.picker-search button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.assignments-hint {
  margin: 0;
  color: #6b7686;
  font-size: 13px;
}
.assignments-error {
  color: #b42318;
}
.assignments-message {
  color: #23784a;
}
.person {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
  color: #1f2f45;
}
.avatar {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: #e7f0fd;
  color: #1f5fa8;
  font-size: 11px;
  font-weight: 700;
}
.avatar.advisor {
  background: #efeafb;
  color: #6b4fc5;
}
.link-arrow {
  color: #9aa5b4;
}
.state {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 99px;
  font-size: 12px;
  font-weight: 600;
}
.state.active {
  background: #e3f4ea;
  color: #23784a;
}
.state.suspended {
  background: #f1f3f6;
  color: #6b7686;
}
tr.inactive .person {
  color: #6b7686;
}
.row-actions {
  text-align: right;
  white-space: nowrap;
}
.row-actions button + button {
  margin-left: 8px;
}
.empty {
  color: #6b7686;
  text-align: center;
}
.assignments-pages,
.picker-pages {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #5b6b82;
  font-size: 12px;
}
.assignments-pages span {
  margin-right: auto;
}
.assignment-create {
  display: grid;
  gap: 18px;
}
.assignment-create fieldset {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 14px;
  border: 1px solid #e3e7ee;
  border-radius: 12px;
}
.assignment-create legend {
  padding: 0 6px;
  font-weight: 600;
}
.picker-search {
  display: flex;
  gap: 8px;
}
.picker-search input {
  flex: 1;
}
.assignment-create select {
  padding: 10px;
  border: 1px solid #dfe4ec;
  border-radius: 10px;
  background: white;
}
.history {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.history li {
  display: grid;
  gap: 2px;
  padding: 10px 12px;
  border-left: 3px solid #1f5fa8;
  border-radius: 6px;
  background: #f6f8fb;
}
.history small {
  color: #6b7686;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}

.setter-advisors {
  padding: 32px;
  gap: 28px;
  color: #3c4354;
}
.advisors-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
}
.advisors-eyebrow {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #9399ac;
}
.advisors-heading h1 {
  font-size: 32px;
  font-weight: 750;
  letter-spacing: -1px;
  margin: 8px 0;
  color: #353b4b;
}
.advisors-heading h1 span {
  color: #526bdb;
}
.advisors-heading p {
  display: none;
}
.advisors-heading button {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 0;
  background: #eceff9;
  border-radius: 14px;
  color: #64709a;
}
.advisor-discovery {
  background: linear-gradient(115deg, #e9edf5, #eef0f6 65%, #e8edf5);
  border-radius: 26px;
  padding: 28px 26px 0;
  margin-bottom: 24px;
}
.discovery-copy {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 0 4px 30px;
}
.discovery-mark {
  width: 46px;
  height: 46px;
  flex-shrink: 0;
  display: grid;
  place-items: center;
  border-radius: 16px;
  background: #e0e6f7;
  color: #6d7cb7;
}
.discovery-copy h2 {
  margin: 0 0 6px;
  font-size: 18px;
  font-weight: 650;
}
.discovery-copy p {
  margin: 0;
  font-size: 13px;
  color: #82899a;
}
.advisor-search {
  display: grid;
  grid-template-columns: minmax(140px, 1.2fr) minmax(150px, 1fr) minmax(180px, 1fr) 66px;
  align-items: center;
  gap: 20px;
  background: #ffffffef;
  border: 1px solid #f4f5f9;
  padding: 20px 24px;
  border-radius: 20px;
  box-shadow: 0 16px 34px #5c6e9410;
  transform: translateY(24px);
  margin-top: -24px;
}
.advisor-search label,
.advisor-search-context {
  display: grid;
  gap: 7px;
  min-width: 0;
}
.advisor-search label > span,
.advisor-search-context > span {
  font-size: 11px;
  color: #949aa8;
}
.setter-advisors .advisor-search input,
.setter-advisors .advisor-search select {
  padding: 0;
  margin: 0;
  border: 0;
  border-radius: 0;
  box-shadow: none;
  background: transparent;
  min-width: 0;
  width: 100%;
  color: #525a6d;
  font-size: 13px;
  height: 25px;
}
.advisor-state-filter,
.advisor-search-context {
  border-left: 1px solid #eeeff4;
  padding-left: 20px;
}
.advisor-search-context strong {
  font-size: 12px;
  font-weight: 500;
  color: #66718a;
}
.setter-advisors .advisor-search-submit {
  height: 64px;
  width: 64px;
  border-radius: 20px;
  border: 0;
  background: #e5e9fa;
  display: grid;
  place-items: center;
  color: #576588;
  cursor: pointer;
}
.advisor-list-heading {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 12px;
  margin-top: 8px;
}
.advisor-list-heading h2 {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 0 7px;
  font-size: 24px;
  letter-spacing: -0.7px;
}
.advisor-list-heading h2 span {
  font-size: 11px;
  letter-spacing: 0;
  border-radius: 20px;
  padding: 4px 9px;
  background: #e9ebf1;
  color: #7c8393;
}
.advisor-list-heading p {
  margin: 0;
  font-size: 12px;
  color: #8a91a2;
}
.advisor-list-heading button {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 0;
  border-radius: 30px;
  background: #e9edf9;
}
.advisor-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 22px;
  align-items: stretch;
}
.advisor-card {
  display: flex;
  flex-direction: column;
  background: linear-gradient(145deg, #fff, #fcfcfe);
  border: 1px solid #fff;
  border-radius: 24px;
  padding: 24px;
  min-width: 0;
  box-shadow: 0 10px 32px #67779108;
}
.advisor-card header {
  display: flex;
  align-items: center;
  gap: 12px;
}
.advisor-monogram {
  display: grid;
  place-items: center;
  flex-shrink: 0;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: 4px solid white;
  box-shadow: 0 2px 9px #7482a120;
  background: #e2e9f7;
  color: #6f80ae;
  font-size: 13px;
  font-weight: 700;
}
.advisor-card:nth-child(3n + 2) .advisor-monogram {
  background: #eee5f6;
  color: #9881b0;
}
.advisor-card:nth-child(3n + 3) .advisor-monogram {
  background: #e3f0ea;
  color: #779a8a;
}
.advisor-identity {
  min-width: 0;
}
.advisor-identity h2 {
  font-size: 16px;
  margin: 0 0 5px;
  overflow-wrap: anywhere;
  font-weight: 700;
  color: #454c60;
}
.advisor-speciality {
  font-size: 11px;
  color: #979baa;
  margin: 0;
  line-height: 1.5;
}
.advisor-tags {
  margin: 18px 0 22px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.advisor-card .state {
  font-size: 10px;
  padding: 5px 10px;
  font-weight: 500;
}
.advisor-card .state.active {
  background: #e8f2ec;
  color: #52856c;
}
.advisor-quota {
  background: #f6f7fb;
  padding: 18px;
  border-radius: 17px;
  flex: 1;
  min-height: 155px;
}
.quota-caption {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 11px;
  color: #8b93a7;
}
.quota-figure {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 7px;
  margin: 15px 0 12px;
}
.quota-figure strong {
  font-size: 29px;
  letter-spacing: -1px;
  color: #536895;
}
.quota-figure span,
.advisor-quota small {
  font-size: 11px;
  color: #8e95a5;
}
.advisor-quota progress {
  display: block;
  width: 100%;
  height: 5px;
  border: 0;
  border-radius: 10px;
  background: #e5e9f5;
  accent-color: #7089df;
  margin-bottom: 12px;
}
.advisor-quota progress::-webkit-progress-bar {
  background: #e5e9f5;
  border-radius: 10px;
}
.advisor-quota progress::-webkit-progress-value {
  background: #7089df;
  border-radius: 10px;
}
.quota-undefined {
  font-size: 14px;
  margin: 24px 0 0;
  color: #68758e;
}
.quota-undefined span {
  display: block;
  margin-top: 9px;
  line-height: 1.6;
  color: #9a9fac;
  font-size: 11px;
}
.advisor-card footer {
  display: flex;
  flex-direction: column;
  gap: 13px;
  margin-top: 22px;
}
.advisor-booking-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #8f97aa;
  font-size: 11px;
}
.setter-advisors .advisor-book {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 14px 12px;
  background: #4765e9;
  border: 0;
  border-radius: 30px;
  color: white;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition:
    background 0.15s,
    transform 0.15s;
}
.setter-advisors .advisor-book:hover:not(:disabled) {
  background: #3654d6;
  transform: translateY(-1px);
}
.setter-advisors button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.setter-advisors button:focus-visible,
.setter-advisors input:focus-visible,
.setter-advisors select:focus-visible {
  outline: 3px solid #99aaf1;
  outline-offset: 4px;
}
.advisors-empty {
  grid-column: 1/-1;
  text-align: center;
  background: #fff;
  padding: 55px 20px;
  border-radius: 24px;
  color: #8a93a9;
}
.advisors-empty h2 {
  font-size: 19px;
  color: #53607a;
}
.setter-advisors .assignments-pages {
  flex-wrap: wrap;
  font-size: 11px;
  color: #959aaa;
}
@media (max-width: 1150px) {
  .advisor-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .advisor-search {
    grid-template-columns: minmax(140px, 1fr) minmax(140px, 1fr) 64px;
  }
  .advisor-search-context {
    display: none;
  }
}
@media (max-width: 720px) {
  .setter-advisors {
    padding: 18px;
    gap: 22px;
  }
  .advisor-grid {
    grid-template-columns: 1fr;
  }
  .advisor-discovery {
    padding: 22px 16px 0;
  }
  .advisor-search {
    padding: 16px;
    grid-template-columns: minmax(0, 1fr) 50px;
    gap: 16px;
  }
  .advisor-name-filter {
    grid-column: 1/-1;
  }
  .advisor-state-filter {
    border: 0;
    padding: 0;
  }
  .setter-advisors .advisor-search-submit {
    width: 50px;
    height: 50px;
    border-radius: 16px;
  }
  .advisors-heading h1 {
    font-size: 28px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .setter-advisors .advisor-book {
    transition: none;
  }
}
</style>
