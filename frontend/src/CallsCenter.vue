<script setup lang="ts">
// Calls module: setters and administrators dial through a prospect card; everyone in
// charge reads the call history. Real dialing stays governed by the telephony settings.
import { ref, computed, onMounted } from 'vue';
import {
  Phone,
  Search,
  Delete,
  History,
  Info,
  ArrowUpRight,
  RefreshCw,
  ContactRound,
  ArrowRight,
} from 'lucide-vue-next';
const props = defineProps<{
  workspace: string;
  role: string;
  request: (path: string, body?: any, method?: string) => Promise<any>;
  portal: (path: string, body?: any) => Promise<any>;
}>();
const emit = defineEmits<{ openProspect: [value: { id: number; mode: 'edit' | 'call' }] }>();
const admin = computed(() => props.role === 'administrator');
const tab = ref<'compose' | 'history'>(admin.value ? 'history' : 'compose');
const options = ref<{ enabled: boolean; post_associated: boolean } | null>(null);
const query = ref(''),
  matches = ref<any[] | null>(null),
  searching = ref(false),
  error = ref('');
const history = ref<any[]>([]),
  count = ref(0),
  page = ref(1),
  state = ref(''),
  caller = ref(''),
  callers = ref<any[]>([]),
  loading = ref(false);
const keys = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '+', '0', '#'];
const states: Record<string, string> = {
  dispatching: 'Envoi en cours',
  accepted: 'Poste joint',
  rejected: 'Échec du poste',
  blocked: 'Bloqué par les contrôles',
  unknown: 'Indéterminé',
};
function when(value: string) {
  return new Intl.DateTimeFormat('fr-FR', { dateStyle: 'medium', timeStyle: 'short' }).format(
    new Date(value),
  );
}
const phoneOf = (row: any) => row.phone || row.raw_phone || '';
// Duration reported by the NEWT 511 journal once the call line is reconciled.
const journalLabels: Record<string, string> = {
  pending: 'En attente du journal',
  not_found: 'Absent du journal',
  ambiguous: 'À vérifier',
};
function duration(row: any) {
  if (!['accepted', 'unknown'].includes(row.state) || row.journal_status === 'unavailable')
    return '—';
  if (row.journal_status !== 'matched') return journalLabels[row.journal_status] || '—';
  const seconds = row.journal_duration;
  if (seconds == null) return 'Durée non lisible';
  if (seconds < 60) return `${seconds} s`;
  return `${Math.floor(seconds / 60)} min ${String(seconds % 60).padStart(2, '0')} s`;
}
const reconciling = ref(false),
  reconciled = ref('');
async function reconcile() {
  reconciling.value = true;
  error.value = '';
  reconciled.value = '';
  try {
    const result = await props.portal(`${props.workspace}/call-history/reconcile/`, {});
    reconciled.value = result.checked
      ? `${result.matched} durée(s) récupérée(s) sur ${result.checked} appel(s) vérifié(s)` +
        (result.ambiguous ? `, ${result.ambiguous} à vérifier` : '') +
        (result.not_found ? `, ${result.not_found} absent(s) du journal` : '') +
        '.'
      : 'Aucun appel récent à rapprocher.';
    await loadHistory();
  } catch (e: any) {
    error.value = e.message;
  } finally {
    reconciling.value = false;
  }
}
async function loadOptions() {
  try {
    options.value = await props.portal(`${props.workspace}/calls/options/`);
  } catch {
    options.value = null;
  }
}
async function search() {
  const term = query.value.trim();
  if (!term) return;
  searching.value = true;
  error.value = '';
  try {
    const path = props.workspace === 'assurance' ? 'contacts' : 'work-queue';
    const data = await props.request(`${path}/?search=${encodeURIComponent(term)}`);
    matches.value = data.results.slice(0, 10);
  } catch (e: any) {
    error.value = e.message;
    matches.value = null;
  } finally {
    searching.value = false;
  }
}
function press(key: string) {
  query.value += key;
}
async function loadHistory() {
  loading.value = true;
  error.value = '';
  try {
    const params = new URLSearchParams({ page: String(page.value) });
    if (state.value) params.set('state', state.value);
    if (caller.value) params.set('user_id', caller.value);
    const data = await props.portal(`${props.workspace}/call-history/?${params}`);
    history.value = data.results;
    count.value = data.count;
  } catch (e: any) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}
async function loadCallers() {
  if (!admin.value) return;
  try {
    const data = await props.portal(
      props.workspace === 'assurance'
        ? 'assurance/participants/?role=setter&page=1'
        : 'isolation/setters/?page=1',
    );
    callers.value = data.results;
  } catch {
    callers.value = [];
  }
}
function filter() {
  page.value = 1;
  void loadHistory();
}
function show(next: 'compose' | 'history') {
  tab.value = next;
  if (next === 'history') void loadHistory();
}
onMounted(() => {
  void loadOptions();
  void loadCallers();
  if (tab.value === 'history') void loadHistory();
});
</script>

<template>
  <section class="calls">
    <header class="calls-heading">
      <div>
        <span class="calls-eyebrow"
          >MON ESPACE · {{ workspace === 'assurance' ? 'ASSURANCE' : 'ISOLATION' }}</span
        >
        <h1>Gardez le contact<span>.</span></h1>
        <p>Un prospect, un échange, une prochaine étape.</p>
      </div>
      <button
        class="secondary"
        :disabled="loading"
        @click="
          loadOptions();
          tab === 'history' && loadHistory();
        "
      >
        <RefreshCw :size="16" />Actualiser
      </button>
    </header>
    <div class="calls-topline">
      <div class="calls-tabs" role="tablist" aria-label="Appels">
        <button
          type="button"
          role="tab"
          :aria-selected="tab === 'compose'"
          :class="{ 'is-active': tab === 'compose' }"
          @click="show('compose')"
        >
          <Phone :size="15" />Composer
        </button>
        <button
          type="button"
          role="tab"
          :aria-selected="tab === 'history'"
          :class="{ 'is-active': tab === 'history' }"
          @click="show('history')"
        >
          <History :size="15" />{{ admin ? 'Historique de l’équipe' : 'Mon historique' }}
        </button>
      </div>
      <span class="phone-status"
        ><i :class="{ ready: options?.enabled && options?.post_associated }"></i
        >{{
          admin && tab === 'history'
            ? 'Historique de l’équipe'
            : !options
              ? 'Téléphonie à vérifier'
              : options.enabled && options.post_associated
                ? 'Poste associé'
                : 'Préparation des appels'
        }}</span
      >
    </div>
    <p
      v-if="options && (!options.enabled || !options.post_associated)"
      class="calls-notice"
      role="status"
    >
      <Info :size="16" />
      <span v-if="!options.enabled"
        >Les appels réels ne sont pas encore activés pour cet espace. Vous pouvez retrouver vos
        prospects et préparer l’appel depuis leur fiche ; la commande sera refusée tant que la
        téléphonie n’est pas activée.</span
      >
      <span v-else
        >Aucun poste téléphonique n’est associé à votre compte : demandez-le à un
        administrateur.</span
      >
    </p>
    <p v-if="error" role="alert" class="calls-error">{{ error }}</p>
    <p v-if="reconciled" role="status" class="calls-reconciled">{{ reconciled }}</p>
    <div v-if="tab === 'compose'" class="compose-layout">
      <div class="dialer">
        <header class="dialer-heading">
          <span class="dialer-symbol"><Phone :size="23" /></span>
          <div>
            <h2>À qui pensez-vous ?</h2>
            <p>Retrouvez un prospect par nom ou numéro.</p>
          </div>
        </header>
        <form class="dialer-input" @submit.prevent="search">
          <Search :size="18" />
          <input
            v-model="query"
            aria-label="Numéro ou nom du prospect"
            placeholder="Numéro ou nom du prospect"
            autocomplete="off"
          />
          <button
            v-if="query"
            type="button"
            class="dialer-erase"
            aria-label="Effacer le dernier caractère"
            @click="query = query.slice(0, -1)"
          >
            <Delete :size="18" />
          </button>
        </form>
        <div class="dialer-pad" aria-label="Pavé numérique">
          <button v-for="key in keys" :key="key" type="button" @click="press(key)">
            {{ key }}
          </button>
        </div>
        <button
          class="primary dialer-search"
          :disabled="searching || !query.trim()"
          @click="search"
        >
          <Search :size="16" />{{ searching ? 'Recherche…' : 'Trouver la fiche' }}
        </button>
        <p class="dialer-hint">
          L’appel se lance toujours depuis la fiche du prospect : contrôles, qualification et
          historique restent rattachés au bon dossier.
        </p>
      </div>
      <aside class="contact-results" aria-live="polite" :aria-busy="searching">
        <header>
          <span class="results-icon"><ContactRound :size="21" /></span>
          <div>
            <h2>La bonne fiche, au bon moment</h2>
            <p>Préparez votre échange sans perdre le fil.</p>
          </div>
        </header>
        <ul v-if="matches" class="dialer-results">
          <li v-for="row in matches" :key="row.id">
            <div>
              <strong>{{ row.name || 'Prospect sans nom' }}</strong>
              <span>{{ phoneOf(row) || 'Numéro non renseigné' }}</span>
            </div>
            <button
              class="primary"
              :disabled="!phoneOf(row)"
              @click="emit('openProspect', { id: row.id, mode: 'call' })"
            >
              <Phone :size="15" />Appeler
            </button>
          </li>
          <li v-if="!matches.length" class="dialer-empty">
            Aucune fiche ne correspond. Les prospects s’ajoutent par import depuis l’écran Prospects
            ; vérifiez le numéro ou cherchez par nom.
          </li>
        </ul>

        <div v-if="matches === null" class="contact-placeholder">
          <span class="placeholder-orbit"><ContactRound :size="38" /></span>
          <h3>Votre prochain échange commence ici</h3>
          <p>
            Saisissez un nom ou un numéro, puis ouvrez la fiche pour retrouver les informations du
            prospect et préparer l’appel.
          </p>
          <div class="contact-steps">
            <span>01 · Trouver</span><ArrowRight :size="15" /><span>02 · Échanger</span
            ><ArrowRight :size="15" /><span>03 · Qualifier</span>
          </div>
        </div>
      </aside>
    </div>
    <div v-else class="calls-history">
      <header class="history-toolbar">
        <h3>{{ admin ? 'Appels de l’équipe' : 'Mes appels' }}</h3>
        <label
          >Résultat<select v-model="state" @change="filter">
            <option value="">Tous</option>
            <option v-for="(label, key) in states" :key="key" :value="key">{{ label }}</option>
          </select></label
        >
        <button
          v-if="admin"
          type="button"
          class="secondary"
          :disabled="reconciling || loading"
          title="Récupère la durée des appels des sept derniers jours dans le journal NEWT"
          @click="reconcile"
        >
          <RefreshCw :size="15" />{{
            reconciling ? 'Rapprochement…' : 'Rapprocher le journal NEWT'
          }}
        </button>
        <label v-if="admin"
          >Appelant<select v-model="caller" @change="filter">
            <option value="">Toute l’équipe</option>
            <option v-for="person in callers" :key="person.id" :value="String(person.id)">
              {{ person.name }}
            </option>
          </select></label
        >
      </header>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Prospect</th>
              <th>Date</th>
              <th v-if="admin">Appelant</th>
              <th>Résultat</th>
              <th>Durée</th>
              <th><span class="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in history" :key="row.request_id">
              <td>{{ row.contact_label || `Fiche n° ${row.contact_id}` }}</td>
              <td data-label="Date">{{ when(row.created_at) }}</td>
              <td v-if="admin" data-label="Appelant">
                {{ row.caller.username }}<small> · poste {{ row.extension }}</small>
              </td>
              <td data-label="Résultat">
                <span :class="['call-state', row.state]">{{ states[row.state] || row.state }}</span>
              </td>
              <td data-label="Durée" :class="['call-duration', row.journal_status]">
                {{ duration(row) }}
              </td>
              <td class="row-action">
                <button
                  class="secondary"
                  @click="emit('openProspect', { id: row.contact_id, mode: 'edit' })"
                >
                  Ouvrir la fiche<ArrowUpRight :size="14" />
                </button>
              </td>
            </tr>
            <tr v-if="!history.length">
              <td :colspan="admin ? 6 : 5" class="calls-empty">
                <History :size="28" />
                {{
                  loading
                    ? 'Chargement…'
                    : admin
                      ? 'Aucun appel enregistré pour ces critères.'
                      : 'Aucun appel pour le moment : vos appels lancés depuis une fiche apparaîtront ici.'
                }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <footer class="history-pages">
        <span>{{ count }} appel(s) · page {{ page }}</span
        ><button
          class="secondary"
          :disabled="loading || page === 1"
          @click="
            page--;
            loadHistory();
          "
        >
          Précédent</button
        ><button
          class="secondary"
          :disabled="loading || page * 25 >= count"
          @click="
            page++;
            loadHistory();
          "
        >
          Suivant
        </button>
      </footer>
      <p class="dialer-hint">
        « Poste joint » signifie que votre poste a décroché et que la composition a démarré. La
        durée provient du journal NEWT (heure de Montréal), rapproché par poste, numéro et heure ;
        une durée de quelques secondes signale en général un appel sans conversation.
      </p>
    </div>
  </section>
</template>

<style scoped>
.calls-reconciled {
  margin: 0 0 12px;
  color: #054f31;
}
.call-duration {
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.call-duration.pending,
.call-duration.not_found,
.call-duration.ambiguous {
  color: #667085;
  font-size: 13px;
}
.calls {
  display: grid;
  gap: 16px;
}
.calls-tabs {
  display: inline-flex;
  justify-self: start;
  padding: 3px;
  border-radius: 10px;
  background: #eef1f6;
}
.calls-tabs button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  border-radius: 8px;
  background: none;
  color: #5b6b82;
  padding: 9px 16px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.calls-tabs button.is-active {
  background: white;
  color: #1f2f45;
  box-shadow: 0 1px 4px #1f2f4518;
}
.calls-notice {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin: 0;
  padding: 12px 14px;
  border: 1px solid #c9dbf5;
  border-radius: 12px;
  background: #f4f8fe;
  color: #1f4a7a;
  font-size: 13px;
}
.calls-notice svg {
  flex-shrink: 0;
  margin-top: 2px;
}
.calls-error {
  color: #b42318;
}
.dialer {
  display: grid;
  gap: 14px;
  max-width: 420px;
}
.dialer-input {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 12px;
  border: 1px solid #dfe4ec;
  border-radius: 12px;
  background: white;
  color: #6b7686;
}
.dialer-input input {
  flex: 1;
  border: 0;
  padding: 14px 0;
  background: none;
  font-size: 18px;
  letter-spacing: 0.04em;
  outline: none;
}
.dialer-erase {
  display: grid;
  place-items: center;
  border: 0;
  background: none;
  color: #6b7686;
  cursor: pointer;
}
.dialer-pad {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.dialer-pad button {
  height: 52px;
  border: 1px solid #e3e7ee;
  border-radius: 14px;
  background: white;
  color: #1f2f45;
  font-size: 20px;
  font-weight: 600;
  cursor: pointer;
}
.dialer-pad button:active {
  background: #eef2f8;
}
.dialer-search,
.dialer-results button,
.row-action button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}
.dialer-results {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.dialer-results li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid #e3e7ee;
  border-radius: 12px;
  background: white;
}
.dialer-results li div {
  display: grid;
  gap: 2px;
  min-width: 0;
}
.dialer-results li span {
  color: #5b6b82;
  font-size: 13px;
}
.dialer-empty {
  display: block !important;
  color: #5b6b82;
}
.dialer-hint {
  margin: 0;
  color: #6b7686;
  font-size: 12px;
}
.calls-history {
  display: grid;
  gap: 12px;
}
.history-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: 12px;
}
.history-toolbar h3 {
  margin: 0 auto 0 0;
}
.history-toolbar label {
  display: grid;
  gap: 4px;
  font-size: 12px;
  color: #5b6b82;
}
.call-state {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 99px;
  background: #f1f3f6;
  color: #3d4b60;
  font-size: 12px;
  font-weight: 600;
}
.call-state.accepted {
  background: #e3f4ea;
  color: #23784a;
}
.call-state.rejected,
.call-state.blocked {
  background: #fde9e5;
  color: #8a281d;
}
.call-state.dispatching {
  background: #e7f0fd;
  color: #1f5fa8;
}
.row-action {
  text-align: right;
}
.calls-empty {
  color: #6b7686;
  text-align: center;
}
.history-pages {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #5b6b82;
  font-size: 12px;
}
.history-pages span {
  margin-right: auto;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
@media (max-width: 700px) {
  .dialer {
    max-width: none;
  }
}

.calls {
  padding: 28px;
  gap: 22px;
  color: #243147;
}
.calls-heading,
.calls-topline {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.calls-heading h1 {
  margin: 8px 0;
  font-size: 30px;
  letter-spacing: -1px;
  color: #19253a;
}
.calls-heading h1 span {
  color: #8264df;
}
.calls-heading p,
.dialer-heading p,
.contact-results header p {
  margin: 0;
  color: #718096;
  font-size: 14px;
}
.calls-eyebrow {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #8877ad;
}
.calls-heading button {
  display: flex;
  align-items: center;
  gap: 8px;
  border-radius: 12px;
  background: white;
}
.calls-tabs {
  background: #eae8f3;
  border-radius: 14px;
  padding: 5px;
}
.calls-tabs button {
  padding: 11px 20px;
  border-radius: 11px;
}
.phone-status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #65728a;
}
.phone-status i {
  width: 7px;
  height: 7px;
  background: #d99a47;
  border-radius: 50%;
}
.phone-status i.ready {
  background: #3aab86;
}
.calls-notice {
  border: 0;
  background: #f0edf9;
  color: #625580;
  padding: 13px 18px;
  font-size: 12px;
}
.compose-layout {
  display: grid;
  grid-template-columns: minmax(300px, 390px) minmax(0, 1fr);
  gap: 22px;
  align-items: stretch;
}
.dialer {
  max-width: none;
  padding: 24px;
  background: white;
  border: 1px solid #e9e8f0;
  border-radius: 24px;
  gap: 18px;
  box-shadow: 0 8px 30px #24314704;
}
.dialer-heading,
.contact-results header {
  display: flex;
  align-items: center;
  gap: 12px;
}
.dialer-heading h2,
.contact-results h2 {
  font-size: 17px;
  margin: 0 0 5px;
  letter-spacing: -0.3px;
}
.dialer-heading p {
  font-size: 12px;
}
.dialer-symbol,
.results-icon {
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  flex-shrink: 0;
  background: #e5f5ef;
  color: #3a9375;
  border-radius: 16px;
}
.calls .dialer-input {
  border: 1px solid #e8e7f0;
  background: #f8f8fc;
  padding: 0 12px;
  min-width: 0;
}
.calls .dialer-input input {
  border: 0;
  box-shadow: none;
  min-width: 0;
  width: 100%;
  font-size: 14px;
  letter-spacing: 0;
  background: transparent;
  padding: 16px 0;
}
.dialer-input:focus-within {
  outline: 2px solid #b7a3e8;
  outline-offset: 2px;
}
.dialer-pad {
  gap: 10px;
}
.dialer-pad button {
  border: 0;
  background: #f5f5fa;
  height: 58px;
  border-radius: 16px;
  font-size: 23px;
  transition:
    background 0.15s,
    transform 0.15s;
}
.dialer-pad button:hover {
  background: #ece7fa;
  transform: translateY(-2px);
}
.calls .dialer-search {
  background: #7658cc;
  color: white;
  border: 0;
  border-radius: 14px;
  min-height: 46px;
  font-size: 13px;
}
.calls button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.calls button:focus-visible {
  outline: 3px solid #b8a4ed;
  outline-offset: 3px;
}
.contact-results {
  padding: 26px;
  background: #fff;
  border: 1px solid #e9e8f0;
  border-radius: 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  min-width: 0;
}
.results-icon {
  background: #eeebfa;
  color: #8665cd;
}
.contact-placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
  padding: 30px 12px;
  background: radial-gradient(ellipse at center, #f3eefc, transparent 70%);
}
.placeholder-orbit {
  width: 112px;
  height: 112px;
  display: grid;
  place-items: center;
  border: 14px solid #f3eefb;
  background: #e9e1f8;
  border-radius: 36px;
  color: #8a70b7;
  transform: rotate(-7deg);
  margin-bottom: 16px;
}
.contact-placeholder h3 {
  font-size: 19px;
  margin: 10px 0;
}
.contact-placeholder p {
  max-width: 360px;
  font-size: 14px;
  color: #788397;
  line-height: 1.8;
}
.contact-steps {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  align-items: center;
  gap: 12px;
  color: #8f7aa9;
  font-size: 11px;
  margin-top: 20px;
}
.dialer-results li {
  padding: 18px;
  border-radius: 16px;
  border-color: #eae8f1;
  background: #faf9fd;
}
.dialer-results li strong {
  font-size: 14px;
  overflow-wrap: anywhere;
}
.dialer-results button {
  border-radius: 12px;
}
.dialer-hint {
  line-height: 1.7;
}
.calls-history {
  background: white;
  border: 1px solid #e9e8f0;
  padding: 24px;
  border-radius: 24px;
  gap: 22px;
}
.history-toolbar h3 {
  font-size: 20px;
}
.calls .history-toolbar select {
  background: #f8f7fc;
  border-color: #e9e6f1;
  border-radius: 12px;
  min-width: 175px;
}
.calls-empty {
  height: 210px;
}
.calls-empty svg {
  display: block;
  margin: 0 auto 16px;
  color: #a995ca;
}
.calls .table-scroll {
  border-radius: 16px;
}
.calls table th {
  background: #f6f4fb;
}
.calls table td {
  padding: 18px 14px;
}
@media (max-width: 950px) {
  .compose-layout {
    grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
  }
  .contact-steps {
    gap: 6px;
  }
  .contact-results {
    padding: 20px;
  }
}
@media (max-width: 760px) {
  .calls {
    padding: 18px;
  }
  .calls-heading h1 {
    font-size: 26px;
  }
  .compose-layout {
    grid-template-columns: 1fr;
  }
  .contact-results {
    min-height: 300px;
  }
  .calls-history {
    padding: 16px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .dialer-pad button {
    transition: none;
  }
}
</style>
