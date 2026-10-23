<script setup lang="ts">
// Phone extensions: which desk phone or softphone rings when a person clicks « Appeler ».
import { ref, computed, onMounted } from 'vue';
import { Phone, Search, Pencil, Trash2, RefreshCw, BookUser, Activity } from 'lucide-vue-next';
import PortalPhoneCdr from './PortalPhoneCdr.vue';
const props = defineProps<{
  space: string;
  request: (path: string, body?: any, method?: string) => Promise<any>;
}>();
const rows = ref<any[]>([]),
  page = ref(1),
  count = ref(0),
  busy = ref(false),
  error = ref(''),
  message = ref(''),
  search = ref('');
// One row at a time is edited or confirmed for removal.
const editing = ref<number | null>(null),
  removing = ref<number | null>(null),
  draft = ref({ extension: '', note: '' });
const endpoint = () => `workspaces/${props.space}/phone-extensions/`;
const visible = computed(() => {
  const term = search.value.trim().toLowerCase();
  return term
    ? rows.value.filter(
        (row) => row.username.toLowerCase().includes(term) || (row.extension || '').includes(term),
      )
    : rows.value;
});
const equipped = computed(() => rows.value.filter((row) => row.extension).length);
const initials = (name: string) =>
  name
    .split(/[.\s_-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('');
async function load() {
  busy.value = true;
  error.value = '';
  try {
    const data = await props.request(endpoint() + `?page=${page.value}`);
    rows.value = data.results;
    count.value = data.count;
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
function edit(row: any) {
  editing.value = row.membership_id;
  removing.value = null;
  draft.value = { extension: row.extension || '', note: '' };
  message.value = '';
  error.value = '';
}
const draftValid = computed(() => /^[0-9]{1,10}$/.test(draft.value.extension.trim()));
// Another person already holds this extension in the loaded page.
const takenBy = computed(() => {
  const value = draft.value.extension.trim();
  return rows.value.find((row) => row.extension === value && row.membership_id !== editing.value)
    ?.username;
});
const directoryName = computed(
  () => directory.value.find((item) => item.extension === draft.value.extension.trim())?.name,
);
async function save(row: any, remove = false) {
  busy.value = true;
  error.value = '';
  message.value = '';
  try {
    await props.request(endpoint(), {
      membership_id: row.membership_id,
      ...(remove ? {} : { extension: draft.value.extension.trim() }),
      ...(row.revision === null ? {} : { revision: row.revision }),
      remove,
      // The audit keeps a reason; administrators may add their own note.
      reason:
        (remove ? '' : draft.value.note.trim()) ||
        (remove ? 'Retrait du poste' : 'Association du poste') + ' depuis l’administration',
    });
    message.value = remove
      ? `Le poste de ${row.username} a été retiré.`
      : `${row.username} reçoit désormais ses appels sur le poste ${draft.value.extension.trim()}.`;
    editing.value = null;
    removing.value = null;
    await load();
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
const directory = ref<any[]>([]),
  directoryError = ref(''),
  directoryLoaded = ref(false);
async function loadDirectory() {
  busy.value = true;
  directoryError.value = '';
  try {
    const result = await props.request('phone-directory/', {});
    directory.value = result.results;
    directoryLoaded.value = true;
  } catch {
    directoryError.value =
      'La liste des postes NEWT n’est pas disponible pour le moment. Saisissez le numéro du poste à la main.';
  } finally {
    busy.value = false;
  }
}
const statuses = ref<Record<number, string>>({});
const stateLabels: Record<string, string> = {
  R: 'Sonne',
  C: 'En communication',
  H: 'En attente',
};
async function inspect(row: any) {
  busy.value = true;
  statuses.value = { ...statuses.value, [row.membership_id]: 'Vérification…' };
  try {
    const result = await props.request(endpoint() + `${row.membership_id}/status/`, {});
    const codes: string[] = result.states?.map((item: any) => item.code) || result.codes || [];
    statuses.value = {
      ...statuses.value,
      [row.membership_id]: codes.length
        ? codes.map((code) => stateLabels[code] || code).join(', ')
        : 'Aucune activité en ce moment',
    };
  } catch {
    statuses.value = { ...statuses.value, [row.membership_id]: 'État indisponible' };
  } finally {
    busy.value = false;
  }
}
onMounted(load);
</script>

<template>
  <section class="extensions">
    <header class="extensions-head">
      <div>
        <h3>Postes téléphoniques</h3>
        <p>
          Indiquez pour chaque personne le numéro de son poste. Quand elle clique sur « Appeler »
          dans une fiche, c’est ce poste qui sonne en premier.
        </p>
      </div>
      <span class="extensions-count"
        ><Phone :size="15" />{{ equipped }} / {{ rows.length }} avec un poste</span
      >
    </header>
    <div class="extensions-toolbar">
      <label class="extensions-search"
        ><Search :size="16" /><input
          v-model="search"
          aria-label="Rechercher une personne ou un poste"
          placeholder="Rechercher une personne ou un poste"
      /></label>
      <button type="button" class="secondary" :disabled="busy" @click="loadDirectory">
        <BookUser :size="16" />{{
          directoryLoaded ? 'Actualiser les postes NEWT' : 'Charger les postes NEWT'
        }}</button
      ><button type="button" class="secondary" :disabled="busy" @click="load">
        <RefreshCw :size="16" />Actualiser
      </button>
    </div>
    <p v-if="directoryLoaded" class="extensions-hint">
      {{ directory.length }} poste(s) NEWT chargé(s) : choisissez-les par nom lors de l’association.
    </p>
    <p v-if="directoryError" class="extensions-hint warning">{{ directoryError }}</p>
    <p v-if="error" role="alert" class="extensions-alert error">{{ error }}</p>
    <p v-if="message" role="status" class="extensions-alert success">{{ message }}</p>
    <ul class="extensions-list">
      <li v-for="row in visible" :key="row.membership_id" class="extension-row">
        <div class="extension-person">
          <span class="extension-avatar">{{ initials(row.username) }}</span>
          <div>
            <strong>{{ row.username }}</strong>
            <small :class="row.eligible ? 'ok' : 'off'">{{
              row.eligible ? 'Peut passer des appels' : 'Accès suspendu'
            }}</small>
          </div>
        </div>
        <div class="extension-value">
          <span v-if="row.extension" class="extension-badge"
            ><Phone :size="14" />Poste {{ row.extension }}</span
          >
          <span v-else class="extension-empty">Aucun poste</span>
          <small v-if="statuses[row.membership_id]" class="extension-status">{{
            statuses[row.membership_id]
          }}</small>
        </div>
        <div v-if="editing !== row.membership_id" class="extension-actions">
          <button
            v-if="row.extension"
            type="button"
            class="secondary"
            :disabled="busy || !row.eligible"
            :aria-label="'Vérifier l’état du poste de ' + row.username"
            @click="inspect(row)"
          >
            <Activity :size="15" />État</button
          ><button
            type="button"
            :class="row.extension ? 'secondary' : 'primary'"
            :disabled="busy || !row.eligible"
            @click="edit(row)"
          >
            <Pencil :size="15" />{{ row.extension ? 'Modifier' : 'Associer un poste' }}</button
          ><button
            v-if="row.revision !== null && row.extension"
            type="button"
            class="secondary danger"
            :disabled="busy"
            :aria-label="'Retirer le poste de ' + row.username"
            @click="
              removing = row.membership_id;
              editing = null;
            "
          >
            <Trash2 :size="15" />
          </button>
        </div>
        <form
          v-if="editing === row.membership_id"
          class="extension-editor"
          @submit.prevent="save(row)"
        >
          <label
            >Numéro du poste<input
              v-model="draft.extension"
              :list="'extensions-' + row.membership_id"
              inputmode="numeric"
              maxlength="10"
              placeholder="ex. 501"
              required
              autofocus
          /></label>
          <datalist :id="'extensions-' + row.membership_id">
            <option v-for="item in directory" :key="item.extension" :value="item.extension">
              {{ item.extension }} · {{ item.name || 'Sans nom' }}
            </option>
          </datalist>
          <label class="extension-note"
            >Note (facultatif)<input
              v-model="draft.note"
              maxlength="1000"
              placeholder="ex. nouveau casque"
          /></label>
          <p v-if="directoryName" class="extensions-hint">Poste NEWT : {{ directoryName }}</p>
          <p v-if="takenBy" class="extensions-hint warning">
            Ce poste est déjà associé à {{ takenBy }}.
          </p>
          <div class="extension-editor-actions">
            <button type="button" class="secondary" :disabled="busy" @click="editing = null">
              Annuler</button
            ><button class="primary" :disabled="busy || !draftValid || !!takenBy">
              Enregistrer
            </button>
          </div>
        </form>
        <div v-if="removing === row.membership_id" class="extension-confirm" role="group">
          <span
            >Retirer le poste {{ row.extension }} de {{ row.username }} ? Cette personne ne pourra
            plus lancer d’appel.</span
          >
          <div class="extension-editor-actions">
            <button type="button" class="secondary" :disabled="busy" @click="removing = null">
              Annuler</button
            ><button type="button" class="primary danger" :disabled="busy" @click="save(row, true)">
              Retirer le poste
            </button>
          </div>
        </div>
      </li>
      <li v-if="!visible.length" class="extensions-empty">
        {{ busy ? 'Chargement…' : 'Aucune personne ne correspond.' }}
      </li>
    </ul>
    <footer v-if="count > 25" class="extensions-pages">
      <span>{{ count }} personne(s) · page {{ page }}</span
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
    <details class="extensions-advanced">
      <summary>Outils avancés (diagnostic NEWT)</summary>
      <p>
        L’annuaire et l’état des postes viennent de NEWT, en lecture seule ; ils ne modifient ni les
        postes ni les appels en cours. Le nom affiché par NEWT est indicatif. Pour une personne
        présente dans les deux espaces, l’association exige les droits d’administration dans les
        deux.
      </p>
      <PortalPhoneCdr :request="request" />
    </details>
  </section>
</template>

<style scoped>
.extensions {
  display: grid;
  gap: 16px;
}
.extensions-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.extensions-head h3 {
  margin: 0;
  color: #101828;
  font-size: 18px;
}
.extensions-head p {
  max-width: 640px;
  margin: 6px 0 0;
  color: #475467;
  font-size: 14px;
}
.extensions-count {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 99px;
  background: #ecfdf3;
  color: #067647;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}
.extensions-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.extensions-toolbar button,
.extension-actions button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.extensions-search {
  display: flex;
  flex: 1 1 260px;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
  border: 1px solid #d0d5dd;
  border-radius: 10px;
  background: white;
  color: #667085;
}
.extensions-search input {
  flex: 1;
  min-height: 40px;
  border: 0;
  padding: 0;
  background: none;
  outline: none;
}
.extensions-hint {
  margin: 0;
  color: #475467;
  font-size: 13px;
}
.extensions-hint.warning {
  color: #b54708;
}
.extensions-alert {
  margin: 0;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 14px;
}
.extensions-alert.error {
  background: #fef3f2;
  color: #b42318;
}
.extensions-alert.success {
  background: #ecfdf3;
  color: #067647;
}
.extensions-list {
  display: grid;
  margin: 0;
  padding: 0;
  list-style: none;
  border: 1px solid #e6e9f0;
  border-radius: 14px;
  background: white;
  overflow: hidden;
}
.extension-row {
  display: grid;
  grid-template-columns: minmax(180px, 1.4fr) minmax(140px, 1fr) auto;
  align-items: center;
  gap: 12px 16px;
  padding: 14px 18px;
  border-top: 1px solid #eef1f5;
}
.extension-row:first-child {
  border-top: 0;
}
.extension-person {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.extension-avatar {
  display: grid;
  flex: none;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: #eef4ff;
  color: #3538cd;
  font-size: 13px;
  font-weight: 700;
}
.extension-person strong {
  display: block;
  color: #101828;
  overflow-wrap: anywhere;
}
.extension-person small {
  font-size: 12px;
}
.extension-person small.ok {
  color: #067647;
}
.extension-person small.off {
  color: #98a2b3;
}
.extension-value {
  display: grid;
  gap: 4px;
  justify-items: start;
}
.extension-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 8px;
  background: #eff8ff;
  color: #175cd3;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.extension-empty {
  color: #98a2b3;
  font-size: 13px;
}
.extension-status {
  color: #475467;
  font-size: 12px;
}
.extension-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}
button.danger {
  color: #b42318;
}
button.primary.danger {
  border-color: #d92d20;
  background: #d92d20;
  color: white;
}
.extension-editor,
.extension-confirm {
  display: flex;
  flex-wrap: wrap;
  grid-column: 1 / -1;
  align-items: flex-end;
  gap: 12px;
  padding: 14px;
  border-radius: 12px;
  background: #f5f8ff;
}
.extension-confirm {
  align-items: center;
  justify-content: space-between;
  background: #fef3f2;
  color: #7a271a;
  font-size: 14px;
}
.extension-editor label {
  display: grid;
  gap: 4px;
  color: #344054;
  font-size: 13px;
  font-weight: 600;
}
.extension-editor label input {
  min-width: 140px;
}
.extension-note {
  flex: 1 1 220px;
}
.extension-editor .extensions-hint {
  flex-basis: 100%;
}
.extension-editor-actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
}
.extensions-empty {
  padding: 24px;
  color: #667085;
  text-align: center;
}
.extensions-pages {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #475467;
  font-size: 13px;
}
.extensions-pages span {
  margin-right: auto;
}
.extensions-advanced {
  padding: 12px 16px;
  border-radius: 12px;
  background: #f6f8fb;
  color: #475467;
  font-size: 13px;
}
.extensions-advanced summary {
  cursor: pointer;
  color: #344054;
  font-weight: 600;
}
@media (max-width: 720px) {
  .extension-row {
    grid-template-columns: 1fr;
  }
  .extension-actions {
    justify-content: flex-start;
  }
}
</style>
