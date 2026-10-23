<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue';
import { Search, RefreshCw, Pencil, Phone, Mail, ChevronDown } from 'lucide-vue-next';
import AssuranceContactEditor from './AssuranceContactEditor.vue';
import AssuranceContacts from './AssuranceContacts.vue';
import SidePanel from './SidePanel.vue';
import ProspectExport from './ProspectExport.vue';
const props = defineProps<{
  request: (path: string, body?: any, method?: string) => Promise<any>;
  portal: (path: string, body?: any) => Promise<any>;
  role: string;
  // Prospect to open on arrival, e.g. from the calls module.
  focus?: { id: number; mode: 'edit' | 'call' } | null;
}>();
const emit = defineEmits<{ imported: [count: number] }>();
const admin = computed(() => props.role === 'administrator');
// Administrator only: the existing list keeps imports, filters and history.
const listView = ref(false);
function showBoard() {
  if (!listView.value) return;
  listView.value = false;
  void load();
}
type Column = {
  key: string;
  label: string;
  active: boolean;
  rows: any[];
  count: number;
  page: number;
  next: boolean;
  busy: boolean;
  error: string;
};
const columns = ref<Column[]>([]),
  search = ref(''),
  applied = ref(''),
  stage = ref(''),
  busy = ref(false),
  error = ref(''),
  opening = ref(false);
const selected = ref<any>(null),
  workflow = ref<'edit' | 'call'>('edit'),
  panelBusy = ref(false),
  editor = ref<InstanceType<typeof AssuranceContactEditor> | null>(null);
const visible = computed(() =>
  columns.value.filter(
    (column) =>
      (!stage.value || column.key === stage.value) && (column.count > 0 || !!column.error),
  ),
);
const total = computed(() => visible.value.reduce((n, c) => n + c.count, 0));
let generation = 0,
  disposed = false;
async function loadColumn(column: Column, version: number, append = false) {
  if (append && column.busy) return;
  column.busy = true;
  column.error = '';
  try {
    const data = await props.request(
      `contacts/?status=${encodeURIComponent(column.key)}&search=${encodeURIComponent(applied.value)}&page=${append ? column.page + 1 : 1}`,
    );
    if (version !== generation || disposed) return;
    column.rows = append ? [...column.rows, ...data.results] : data.results;
    column.count = data.count;
    column.page = append ? column.page + 1 : 1;
    column.next = !!data.next;
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
  applied.value = search.value.trim();
  try {
    const data = await props.request('pipeline/');
    if (version !== generation || disposed) return;
    columns.value = data.stages.map((s: any) => ({
      ...s,
      rows: [],
      count: 0,
      page: 0,
      next: false,
      busy: true,
      error: '',
    }));
    const queue = [...columns.value];
    await Promise.all(
      Array.from({ length: 3 }, async () => {
        while (queue.length && version === generation && !disposed)
          await loadColumn(queue.shift()!, version);
      }),
    );
  } catch (e: any) {
    if (version === generation) error.value = e.message;
  } finally {
    if (version === generation) busy.value = false;
  }
}
async function open(row: any, mode: 'edit' | 'call') {
  if (opening.value || selected.value) return;
  opening.value = true;
  error.value = '';
  try {
    const detail = await props.request(`contacts/${row.id}/`);
    if (disposed) return;
    workflow.value = mode;
    selected.value = detail;
  } catch (e: any) {
    selected.value = null;
    error.value = e.message;
  } finally {
    opening.value = false;
  }
}
function closed() {
  const id = selected.value?.id;
  selected.value = null;
  panelBusy.value = false;
  void load().then(async () => {
    await nextTick();
    if (!selected.value && !disposed)
      document.querySelector<HTMLButtonElement>(`[data-prospect-id="${Number(id)}"]`)?.focus();
  });
}
onMounted(async () => {
  await load();
  if (props.focus) await open({ id: props.focus.id }, props.focus.mode);
});
onBeforeUnmount(() => {
  disposed = true;
  generation++;
});
</script>
<template>
  <section class="prospects-board">
    <header class="prospects-heading">
      <div>
        <span>{{ admin ? 'ÉQUIPE ASSURANCE' : 'MON ESPACE ASSURANCE' }}</span>
        <h1>Prospects</h1>
        <p>
          {{
            admin
              ? 'Tous les prospects de l’équipe, par statut.'
              : 'Retrouvez vos prospects, appelez et préparez leurs rendez-vous.'
          }}
        </p>
      </div>
      <div class="prospects-heading-actions">
        <div v-if="admin" class="prospects-view-switch" role="group" aria-label="Affichage">
          <button :class="{ 'is-active': !listView }" :aria-pressed="!listView" @click="showBoard">
            Tableau</button
          ><button
            :class="{ 'is-active': listView }"
            :aria-pressed="listView"
            @click="listView = true"
          >
            Liste et imports
          </button>
        </div>
        <ProspectExport
          v-if="!listView"
          :request="request"
          path="contacts/export/"
          :filters="{ search: applied }"
        />
        <button v-if="!listView" class="secondary" :disabled="busy" @click="load">
          <RefreshCw :size="16" />Actualiser
        </button>
      </div>
    </header>
    <AssuranceContacts
      v-if="admin && listView"
      :portal="portal"
      :request="request"
      :role="role"
      @imported="emit('imported', $event)"
    />
    <template v-else>
      <div class="prospects-toolbar">
        <label class="stage-filter"
          ><select v-model="stage" aria-label="Filtrer les prospects par statut">
            <option value="">Tous les statuts</option>
            <option v-for="column in columns" :key="column.key" :value="column.key">
              {{ column.label }}{{ column.active ? '' : ' (archivé)' }}
            </option></select
          ><ChevronDown :size="15" /></label
        ><span class="prospects-count" role="status"
          >{{ busy ? 'Chargement…' : `${total} prospect(s)`
          }}{{ columns.some((c) => c.error) ? ' · résultat partiel' : '' }}</span
        >
        <form @submit.prevent="load">
          <Search :size="17" /><input
            v-model="search"
            aria-label="Rechercher un prospect"
            placeholder="Nom, téléphone ou e-mail"
          /><button :disabled="busy">Rechercher</button>
        </form>
      </div>
      <p v-if="error" role="alert" class="error">{{ error }}</p>
      <p v-if="!busy && !error && !columns.length" class="board-empty">
        Aucun statut configuré. Contactez votre administrateur.
      </p>
      <p v-else-if="!busy && !error && !visible.length" class="board-empty" role="status">
        {{
          stage
            ? 'Aucun prospect pour ce statut et cette recherche.'
            : 'Aucun prospect ne correspond à votre recherche.'
        }}
      </p>
      <div
        class="prospects-columns"
        :class="{ 'single-status': visible.length === 1 }"
        role="region"
        tabindex="0"
        aria-label="Prospects par statut"
      >
        <section
          v-for="column in visible"
          :key="column.key"
          class="prospect-column"
          :style="{
            '--stage-tone': ['#f1ad54', '#5b8def', '#a18be2', '#48b3be', '#69b694'][
              columns.indexOf(column) % 5
            ],
          }"
        >
          <header>
            <span class="stage-dot"></span>
            <h2>{{ column.label }}<small v-if="!column.active">Archivé</small></h2>
            <span class="column-count">{{ column.busy && !column.page ? '…' : column.count }}</span>
          </header>
          <div class="prospect-stack">
            <p v-if="column.error" role="alert">
              {{ column.error
              }}<button class="secondary" @click="loadColumn(column, generation, column.page > 0)">
                Réessayer
              </button>
            </p>
            <article v-for="row in column.rows" :key="row.id" class="prospect-card">
              <button
                class="prospect-title"
                :data-prospect-id="row.id"
                :disabled="opening"
                @click="open(row, 'edit')"
              >
                {{ row.name || 'Prospect sans nom' }}
              </button>
              <small class="prospect-updated"
                >Mis à jour {{ new Date(row.updated_at).toLocaleDateString('fr-FR') }}</small
              >
              <div class="prospect-phone">
                <Phone :size="14" /><span>{{ row.phone || 'Non renseigné' }}</span>
                <div class="number-actions">
                  <button
                    :disabled="opening"
                    :aria-label="'Modifier le numéro de ' + (row.name || 'ce prospect')"
                    title="Modifier la fiche et le numéro"
                    @click="open(row, 'edit')"
                  >
                    <Pencil :size="15" /></button
                  ><button
                    v-if="!admin"
                    class="phone-button"
                    :disabled="opening || !row.phone"
                    :aria-label="'Préparer l’appel vers ' + row.phone"
                    title="Appeler et qualifier le prospect"
                    @click="open(row, 'call')"
                  >
                    <Phone :size="15" />
                  </button>
                </div>
              </div>
              <p class="prospect-email">
                <Mail :size="14" /><span>{{ row.email || 'E-mail non renseigné' }}</span>
              </p>
              <footer>
                <span class="prospect-stage">{{ row.status_label || column.label }}</span>
              </footer>
            </article>
            <p v-if="!column.busy && !column.error && !column.count" class="board-empty">
              Aucun prospect
            </p>
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
    </template>
    <SidePanel
      :scrollable="false"
      :open="!!selected"
      :title="selected?.name || 'Prospect sans nom'"
      :subtitle="selected?.status_label || selected?.status"
      eyebrow="FICHE PROSPECT"
      :close-disabled="panelBusy"
      @request-close="editor?.close()"
      ><AssuranceContactEditor
        v-if="selected"
        ref="editor"
        :key="selected.id"
        :contact="selected"
        :portal="portal"
        :request="request"
        :role="role"
        :workflow="workflow"
        @busy="panelBusy = $event"
        @summary="selected = { ...selected, ...$event }"
        @close="closed"
    /></SidePanel>
  </section>
</template>
<style scoped>
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
.prospects-heading-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.prospects-view-switch {
  display: inline-flex;
  padding: 3px;
  border-radius: 10px;
  background: #eef1f6;
}
.prospects-view-switch button {
  border: 0;
  border-radius: 8px;
  background: none;
  color: #5b6b82;
  padding: 9px 15px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.prospects-view-switch button.is-active {
  background: white;
  color: #26364d;
  box-shadow: 0 1px 4px #26364d18;
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
</style>
