<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { Plus, Search, ArrowRight, History, PauseCircle, PlayCircle } from 'lucide-vue-next';
import SidePanel from './SidePanel.vue';
import { loadQuotas, type AdvisorQuota } from './advisor-quota';
const props = defineProps<{
  role: string;
  request: (path: string, body?: any, method?: string) => Promise<any>;
  portal: (path: string, body?: any) => Promise<any>;
}>();
const quotas = ref(new Map<number, AdvisorQuota>());
async function loadQuotaBoard() {
  try {
    quotas.value = await loadQuotas(props.portal, props.request);
  } catch {
    quotas.value = new Map();
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
  <section class="assignments">
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
    <p v-else class="assignments-hint">
      Les conseillers avec lesquels vous pouvez réserver des rendez-vous.
    </p>
    <div class="table-scroll">
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
</style>
