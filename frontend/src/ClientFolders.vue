<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, nextTick, ref } from 'vue';
import {
  FolderOpen,
  Search,
  ArrowLeft,
  ArrowUpRight,
  Users,
  CalendarCheck,
  RefreshCw,
  Phone,
  ListChecks,
} from 'lucide-vue-next';
import SidePanel from './SidePanel.vue';
import ClientCallHistory from './ClientCallHistory.vue';
import ProspectExport from './ProspectExport.vue';
import AssuranceContactEditor from './AssuranceContactEditor.vue';
import AssuranceAppointments from './AssuranceAppointments.vue';
import IsolationProspectActivity from './IsolationProspectActivity.vue';
import IsolationVisits from './IsolationVisits.vue';
import { actorNames } from './actor-names';
const props = defineProps<{
  workspace: 'assurance' | 'isolation';
  request: (path: string, body?: any, method?: string) => Promise<any>;
  portal: (path: string, body?: any) => Promise<any>;
}>();
const exporting = ref(false),
  exportChoice = ref('section');
const applied = ref({ section: 'prospects', search: '', status: '' });
const exportSection = computed(() =>
  exportChoice.value === 'summary' ? 'summary' : section.value,
);
const exportFilters = computed(() =>
  exportSection.value === 'summary'
    ? { section: 'summary' }
    : {
        section: applied.value.section,
        search: applied.value.search,
        ...(['prospects', 'appointments'].includes(applied.value.section)
          ? { status: applied.value.status }
          : {}),
      },
);
const folders = ref<any[]>([]),
  selected = ref<any>(null),
  metrics = ref<any>(null);
const rows = ref<any[]>([]),
  page = ref(1),
  count = ref(0),
  search = ref('');
const section = ref('prospects'),
  status = ref(''),
  busy = ref(false),
  error = ref('');
const names = ref<Record<number, string>>({});
const heading = ref<HTMLElement | null>(null);
let directory = { search: '', page: 1 };
async function revealHeading() {
  await nextTick();
  heading.value?.scrollIntoView?.({ block: 'start' });
  heading.value?.focus?.({ preventScroll: true });
}
const callContact = ref<any>(null);
const appointment = ref<any>(null),
  appointmentBusy = ref(false),
  appointmentDirty = ref(false);
function openAppointment(row: any) {
  if (busy.value || exporting.value || appointment.value) return;
  appointmentDirty.value = false;
  appointment.value = row;
}
function closeAppointment() {
  if (appointmentBusy.value) return;
  if (
    appointmentDirty.value &&
    !window.confirm('Quitter sans enregistrer les modifications du rendez-vous ?')
  )
    return;
  appointment.value = null;
  appointmentDirty.value = false;
  void load();
}
const prospect = ref<any>(null),
  panelBusy = ref(false),
  visitProspect = ref<number | undefined>();
const editor = ref<InstanceType<typeof AssuranceContactEditor> | null>(null);
const activity = ref<InstanceType<typeof IsolationProspectActivity> | null>(null);
const visits = ref<InstanceType<typeof IsolationVisits> | null>(null);
const labels: Record<string, string> = {
  scheduled: 'Planifié',
  rescheduled: 'Reprogrammé',
  performed: 'Rendez-vous tenu',
  absent: 'Absent',
  not_performed: 'Non tenu · autre motif',
  report_due: 'Compte rendu attendu',
  cancelled: 'Annulé',
  to_contact: 'À contacter',
  in_progress: 'En cours',
  callback: 'À rappeler',
  interested: 'Intéressé',
  not_interested: 'Pas intéressé',
  unreachable: 'Injoignable',
  appointment_booked: 'Rendez-vous pris',
  voicemail: 'Répondeur',
  invalid_number: 'Numéro invalide',
  disconnected: 'Appel coupé',
  open: 'À faire',
  overdue: 'En retard',
  closed: 'Terminé',
  booked: 'RDV réservé',
};
const appointmentStates = [
  'scheduled',
  'rescheduled',
  'performed',
  'absent',
  'not_performed',
  'report_due',
  'cancelled',
];
const tabs = [
  { id: 'prospects', label: 'Prospects', icon: Users },
  { id: 'appointments', label: 'Rendez-vous', icon: CalendarCheck },
  { id: 'calls', label: 'Résultats d’appel', icon: Phone },
  { id: 'tasks', label: 'Tâches et rappels', icon: ListChecks },
];
const remaining = computed(() =>
  selected.value?.quota == null || !metrics.value
    ? null
    : Math.max(0, selected.value.quota - (metrics.value.statuses.performed || 0)),
);
function date(value: string, zone = 'America/Toronto') {
  return new Intl.DateTimeFormat('fr-CA', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: zone,
  }).format(new Date(value));
}
async function load() {
  if (exporting.value) return;
  const version = ++generation;
  busy.value = true;
  error.value = '';
  rows.value = [];
  metrics.value = null;
  try {
    const query = new URLSearchParams({ page: String(page.value), search: search.value });
    if (!selected.value) {
      folders.value = [];
      const data = await props.portal(`${props.workspace}/client-folders/?${query}`);
      if (version !== generation) return;
      count.value = data.count;
      directory = { search: query.get('search') || '', page: Number(query.get('page')) };
      // Keep accounts visible if business statistics are temporarily unavailable; never invent zeros.
      folders.value = data.results;
      if (data.results.length) {
        const statistics = await props.request(
          `client-folders/?ids=${data.results.map((row: any) => row.id).join(',')}`,
        );
        if (version !== generation) return;
        folders.value = data.results.map((row: any) => ({
          ...row,
          metrics: statistics.results.find((value: any) => value.id === row.id),
        }));
      }
    } else {
      query.set('section', section.value);
      if (['appointments', 'prospects'].includes(section.value) && status.value)
        query.set('status', status.value);
      const data = await props.request(`client-folders/${selected.value.id}/?${query}`);
      if (version !== generation) return;
      rows.value = data.results;
      count.value = data.count;
      metrics.value = data.summary;
      applied.value = {
        section: query.get('section') || 'prospects',
        search: query.get('search') || '',
        status: query.get('status') || '',
      };
      const actors = await actorNames(
        props.portal,
        props.workspace,
        data.results.flatMap((row: any) => [row.actor_id || row.booked_by_id, row.report_by_id]),
      );
      if (version === generation) names.value = actors;
    }
  } catch (e: any) {
    if (version === generation) error.value = e.message || 'Chargement impossible. Réessayez.';
  } finally {
    if (version === generation) busy.value = false;
  }
}
function reset() {
  if (exporting.value) return;
  page.value = 1;
  void load();
}
function open(row: any) {
  selected.value = row;
  search.value = '';
  section.value = 'prospects';
  status.value = '';
  reset();
  void revealHeading();
}
function back() {
  selected.value = null;
  search.value = directory.search;
  page.value = directory.page;
  void load();
  void revealHeading();
}
function tab(id: string) {
  section.value = id;
  search.value = '';
  status.value = '';
  reset();
}
async function openProspect(id: number) {
  busy.value = true;
  error.value = '';
  try {
    prospect.value = await props.request(
      `${props.workspace === 'assurance' ? 'contacts' : 'work-queue'}/${id}/`,
    );
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
function closeProspect() {
  if (panelBusy.value) return;
  if (props.workspace === 'assurance') editor.value?.close();
  else activity.value?.close();
}
function closed() {
  prospect.value = null;
  void load();
}
let generation = 0;
onBeforeUnmount(() => {
  generation++;
});
onMounted(load);
</script>

<template>
  <section class="client-folders" :aria-busy="busy">
    <header class="folder-heading">
      <div>
        <button v-if="selected" class="folder-back" :disabled="busy || exporting" @click="back">
          <ArrowLeft :size="16" />Tous les dossiers
        </button>
        <span v-else class="folder-eyebrow"
          >VOTRE ESPACE CLIENTS · {{ workspace === 'assurance' ? 'ASSURANCE' : 'ISOLATION' }}</span
        >
        <h1 ref="heading" tabindex="-1" class="folder-title">
          {{ selected ? selected.name : 'Dossiers clients' }}<span>.</span>
        </h1>
        <p>
          {{
            selected
              ? 'Le suivi complet du client, du premier contact au rendez-vous.'
              : 'Un client, un dossier. Retrouvez les prospects confiés et le travail de votre équipe.'
          }}
        </p>
      </div>
      <button class="folder-refresh" :disabled="busy || exporting" @click="load">
        <RefreshCw :size="16" />Actualiser
      </button>
    </header>
    <p v-if="error" class="folder-error" role="alert">
      {{ error }} <button :disabled="busy || exporting" @click="load">Réessayer</button>
    </p>
    <p v-if="busy" role="status">Chargement des dossiers…</p>
    <template v-if="!selected">
      <div class="folder-intro">
        <FolderOpen :size="32" />
        <div>
          <strong>Tout le suivi, au même endroit</strong>
          <p>
            Ouvrez un dossier pour consulter les statuts, les agents responsables et les fiches
            détaillées.
          </p>
        </div>
      </div>
      <form class="folder-search" @submit.prevent="reset">
        <Search :size="18" /><input
          v-model="search"
          placeholder="Rechercher un client…"
          aria-label="Rechercher un client"
        /><button :disabled="busy || exporting">Rechercher</button
        ><span>{{ count }} dossier(s)</span>
      </form>
      <div class="folder-grid">
        <button
          v-for="(folder, index) in folders"
          :key="folder.id"
          class="client-folder"
          :class="`folder-tone-${index % 3}`"
          :disabled="busy || exporting"
          @click="open(folder)"
        >
          <span class="folder-topline"
            ><FolderOpen :size="30" /><span>{{
              folder.active ? 'Client actif' : 'Compte inactif'
            }}</span
            ><ArrowUpRight :size="21"
          /></span>
          <strong class="folder-name">{{ folder.name }}</strong>
          <span class="folder-meta">{{
            workspace === 'assurance' ? 'Conseiller · Assurance' : 'Client unique · Isolation'
          }}</span>
          <span v-if="folder.metrics" class="folder-totals"
            ><span
              ><b>{{ folder.metrics.prospects }}</b> prospects</span
            ><span
              ><b>{{ folder.metrics.statuses.performed || 0 }}</b> RDV tenus</span
            ><span
              ><b>{{ folder.metrics.sales }}</b> ventes</span
            ></span
          >
          <span v-else class="folder-meta">Statistiques indisponibles</span>
          <span class="folder-open">Ouvrir le dossier <ArrowUpRight :size="16" /></span>
        </button>
      </div>
      <p v-if="!busy && !error && !folders.length" class="folder-empty">
        {{
          search
            ? 'Aucun client ne correspond à cette recherche.'
            : 'Aucun compte client dans cet espace. Ajoutez-le dans Utilisateurs et accès.'
        }}
      </p>
    </template>
    <template v-else>
      <div v-if="metrics" class="folder-metrics">
        <div class="metric-blue">
          <Users :size="20" /><span>Prospects confiés</span><strong>{{ metrics.prospects }}</strong
          ><small>Fiches distinctes, historique inclus</small>
        </div>
        <div class="metric-purple">
          <CalendarCheck :size="20" /><span>Rendez-vous attribués</span
          ><strong>{{ metrics.appointments }}</strong
          ><small>Annulations incluses dans le total</small>
        </div>
        <div class="metric-mint">
          <CalendarCheck :size="20" /><span>Rendez-vous tenus</span
          ><strong>{{ metrics.statuses.performed || 0 }}</strong
          ><small>{{ metrics.sales }} vente(s) ou contrat(s) conclu(s)</small>
        </div>
        <div class="metric-peach">
          <ListChecks :size="20" /><span>{{
            workspace === 'assurance' ? 'Restant sur l’objectif' : 'Suivis ouverts'
          }}</span
          ><strong>{{ workspace === 'assurance' ? (remaining ?? '—') : metrics.open_tasks }}</strong
          ><small>{{
            workspace === 'assurance'
              ? selected.quota == null
                ? 'Objectif non défini'
                : `Objectif : ${selected.quota} · Présences seules décomptées`
              : `${metrics.overdue_tasks} suivi(s) en retard`
          }}</small>
        </div>
      </div>
      <h2 v-if="metrics" class="status-group-title">Résultats des rendez-vous</h2>
      <div
        v-if="metrics"
        class="folder-statuses"
        role="group"
        aria-label="Filtrer les rendez-vous par résultat"
      >
        <button
          v-for="state in appointmentStates.filter(
            (key) => workspace === 'assurance' || !['absent', 'rescheduled'].includes(key),
          )"
          :key="state"
          :disabled="busy || exporting"
          :class="['status-pill', state]"
          :aria-pressed="section === 'appointments' && status === state"
          @click="
            section = 'appointments';
            status = state;
            search = '';
            reset();
          "
        >
          {{ labels[state] }} <b>{{ metrics.statuses[state] || 0 }}</b>
        </button>
      </div>
      <p class="folder-rule">
        {{
          workspace === 'assurance'
            ? 'Le décompte repose uniquement sur les présences confirmées, toutes périodes confondues. Une absence ou une annulation ne diminue pas l’objectif.'
            : 'Les visites non tenues restent distinctes des comptes rendus manquants. Aucun compte rendu manquant n’est compté comme une absence.'
        }}
      </p>
      <h2 v-if="metrics && section === 'prospects'" class="status-group-title">
        Étapes commerciales des prospects
      </h2>
      <div
        v-if="metrics && section === 'prospects'"
        class="folder-statuses"
        role="group"
        aria-label="Filtrer les prospects par étape commerciale"
      >
        <button
          v-for="stage in metrics.prospect_statuses"
          :key="stage.status"
          :disabled="busy || exporting"
          class="status-pill"
          :aria-pressed="status === stage.status"
          @click="
            status = stage.status;
            reset();
          "
        >
          {{ stage.label }} <b>{{ stage.total }}</b></button
        ><button
          v-if="status"
          class="status-pill"
          :disabled="busy || exporting"
          @click="
            status = '';
            reset();
          "
        >
          Tous les statuts
        </button>
      </div>
      <p class="folder-rule">
        Les fiches restent accessibles après un changement d’affectation. Les appels et tâches
        reprennent leur historique complet ; les rendez-vous sont limités à ce client.
      </p>
      <nav class="folder-tabs" aria-label="Contenu du dossier">
        <button
          v-for="item in tabs"
          :key="item.id"
          :disabled="busy || exporting"
          :aria-current="section === item.id ? 'page' : undefined"
          @click="tab(item.id)"
        >
          <component :is="item.icon" :size="17" />{{ item.label
          }}<span v-if="metrics">{{
            item.id === 'prospects'
              ? metrics.prospects
              : item.id === 'appointments'
                ? metrics.appointments
                : item.id === 'calls'
                  ? metrics.call_results
                  : metrics.tasks
          }}</span>
        </button>
      </nav>
      <div class="folder-export">
        <label
          >Contenu à exporter<select v-model="exportChoice" :disabled="busy || exporting">
            <option value="section">Cet onglet · tous les résultats filtrés</option>
            <option value="summary">Synthèse générale · indicateurs métier</option>
          </select></label
        >
        <ProspectExport
          :request="request"
          :path="`client-folders/${selected.id}/export/`"
          :filters="exportFilters"
          :filename="`dossier-${workspace}-${selected.id}-${exportSection}`"
          label="Télécharger"
          :blocked="busy || exporting || !!error || !metrics"
          @busy="exporting = $event"
        />
        <small>{{
          exportChoice === 'summary'
            ? 'Indicateurs de tout le dossier, hors objectif administratif et quota restant.'
            : 'Toutes les pages correspondant à la dernière liste chargée. Les modifications de recherche doivent être appliquées avant un nouvel export.'
        }}</small>
      </div>
      <form class="folder-search" @submit.prevent="reset">
        <Search :size="18" /><input
          v-model="search"
          placeholder="Rechercher un prospect dans ce dossier…"
          aria-label="Rechercher un prospect dans le dossier"
        /><label v-if="section === 'appointments'"
          >Statut<select v-model="status" :disabled="busy || exporting" @change="reset">
            <option value="">Tous les statuts</option>
            <option v-for="state in appointmentStates" :key="state" :value="state">
              {{ labels[state] }}
            </option>
          </select></label
        ><button :disabled="busy || exporting">Rechercher</button>
      </form>
      <p v-if="section === 'calls'" class="folder-rule">
        Résultats saisis par les agents sur les fiches de ce dossier. Ce total ne représente pas le
        nombre d’appels téléphoniques effectivement connectés.
      </p>
      <p v-if="section === 'tasks' && metrics" class="folder-rule">
        {{ metrics.open_tasks }} tâche(s) ouverte(s), dont {{ metrics.overdue_tasks }} en retard. La
        liste inclut aussi les tâches terminées.
      </p>
      <div class="folder-table">
        <table>
          <thead>
            <tr>
              <th>Prospect</th>
              <th>
                {{
                  section === 'prospects'
                    ? 'Téléphone'
                    : section === 'tasks'
                      ? 'Échéance · Montréal'
                      : 'Date'
                }}
              </th>
              <th>Statut</th>
              <th v-if="section !== 'prospects'">
                {{ section === 'appointments' ? 'Setter / réservation' : 'Agent responsable' }}
              </th>
              <th v-if="section !== 'prospects'">Notes</th>
              <th>Dossier</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="row.id">
              <td>
                <strong>{{ row.name || 'Sans nom' }}</strong
                ><small v-if="row.closer_name">Closer : {{ row.closer_name }}</small>
              </td>
              <td>
                {{
                  section === 'prospects'
                    ? row.phone
                    : date(row.starts_at || row.due_at || row.created_at, row.timezone)
                }}
              </td>
              <td>
                <span :class="['status-pill', row.status]">{{
                  section === 'prospects'
                    ? metrics?.prospect_statuses.find((stage: any) => stage.status === row.status)
                        ?.label || row.status
                    : labels[row.status] || row.status
                }}</span>
              </td>
              <td v-if="section !== 'prospects'">
                <span v-if="section === 'appointments'"
                  >{{ row.setter_name || `Compte #${row.setter_id}`
                  }}<small
                    >Réservé par
                    {{ names[row.booked_by_id] || `compte #${row.booked_by_id}` }}</small
                  ></span
                ><span v-else>{{
                  names[row.actor_id] ||
                  (row.actor_id ? `Compte #${row.actor_id}` : 'Non renseigné')
                }}</span>
              </td>
              <td v-if="section !== 'prospects'" class="folder-note">
                {{ row.note || '—'
                }}<small v-if="row.resolution">Résolution : {{ row.resolution }}</small>
                <small v-if="row.reported_at"
                  >Compte rendu par
                  {{
                    names[row.report_by_id] ||
                    (row.report_by_id ? `compte #${row.report_by_id}` : 'Auteur non renseigné')
                  }}
                  · {{ date(row.reported_at, row.timezone) }}</small
                >
              </td>
              <td>
                <button
                  v-if="section === 'appointments'"
                  class="folder-link"
                  :disabled="busy || exporting"
                  @click="openAppointment(row)"
                >
                  Voir le rendez-vous <CalendarCheck :size="14" />
                </button>
                <button
                  :class="section === 'appointments' ? 'folder-call-link' : 'folder-link'"
                  :disabled="busy || exporting"
                  @click="openProspect(row.contact_id || row.id)"
                >
                  Ouvrir la fiche <ArrowUpRight :size="14" /></button
                ><button
                  class="folder-call-link"
                  :disabled="busy || exporting"
                  @click="callContact = { id: row.contact_id || row.id, name: row.name }"
                >
                  Appels CRM
                </button>
              </td>
            </tr>
            <tr v-if="!busy && !error && !rows.length">
              <td :colspan="section === 'prospects' ? 4 : 6" class="folder-empty">
                Aucun élément pour ces critères.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
    <footer class="folder-pagination">
      <span>{{ count }} {{ selected ? 'résultat(s)' : 'dossier(s)' }} · page {{ page }}</span
      ><button
        :disabled="busy || exporting || page === 1"
        @click="
          page--;
          load();
        "
      >
        Précédent</button
      ><button
        :disabled="busy || exporting || page * (selected ? 25 : 12) >= count"
        @click="
          page++;
          load();
        "
      >
        Suivant
      </button>
    </footer>
    <SidePanel
      :open="!!appointment"
      :title="appointment ? `Rendez-vous · ${appointment.name || 'Sans nom'}` : 'Rendez-vous'"
      eyebrow="DOSSIER CLIENT · RENDEZ-VOUS"
      :close-disabled="appointmentBusy"
      @request-close="closeAppointment"
    >
      <div @input="appointmentDirty = true" @change="appointmentDirty = true">
        <AssuranceAppointments
          v-if="appointment && workspace === 'assurance'"
          :key="appointment.id"
          :appointment-id="appointment.id"
          role="administrator"
          :request="request"
          :portal="portal"
          @busy="appointmentBusy = $event"
          @updated="appointmentDirty = false"
        />
        <IsolationVisits
          v-else-if="appointment"
          :key="appointment.id"
          :visit-id="appointment.id"
          role="administrator"
          :request="request"
          :portal="portal"
          @busy="appointmentBusy = $event"
          @updated="appointmentDirty = false"
          @close="closeAppointment"
        />
      </div>
    </SidePanel>
    <SidePanel
      :open="!!callContact"
      :title="callContact?.name || 'Appels CRM'"
      eyebrow="HISTORIQUE DES AGENTS"
      @request-close="callContact = null"
      ><ClientCallHistory
        v-if="callContact"
        :key="callContact.id"
        :contact-id="callContact.id"
        :workspace="workspace"
        :portal="portal"
    /></SidePanel>
    <SidePanel
      :open="!!prospect"
      :scrollable="workspace !== 'assurance'"
      :title="prospect?.name || 'Fiche prospect'"
      eyebrow="DOSSIER CLIENT · ADMINISTRATION"
      :close-disabled="panelBusy"
      @request-close="closeProspect"
    >
      <AssuranceContactEditor
        v-if="prospect && workspace === 'assurance'"
        ref="editor"
        :key="prospect.id"
        :contact="prospect"
        role="administrator"
        workflow="edit"
        :request="request"
        :portal="portal"
        @busy="panelBusy = $event"
        @close="closed"
      />
      <IsolationProspectActivity
        v-else-if="prospect"
        ref="activity"
        :key="prospect.id"
        :prospect-id="prospect.id"
        role="administrator"
        :request="request"
        :portal="portal"
        @busy="panelBusy = $event"
        @close="closed"
        @book="visitProspect = prospect.id"
      />
    </SidePanel>
    <SidePanel
      :open="visitProspect != null"
      title="Visites et formulaire C2"
      :close-disabled="panelBusy"
      @request-close="visits?.close()"
      ><IsolationVisits
        v-if="visitProspect != null"
        ref="visits"
        :prospect-id="visitProspect"
        role="administrator"
        :request="request"
        :portal="portal"
        @busy="panelBusy = $event"
        @close="
          visitProspect = undefined;
          load();
        "
    /></SidePanel>
  </section>
</template>

<style scoped>
.folder-title {
  scroll-margin-top: 100px;
}
.folder-title:focus {
  outline: none;
}
.status-group-title {
  font-size: 13px;
  font-weight: 650;
  color: #536079;
  margin: 22px 0 8px;
}
.status-group-title + .folder-statuses {
  margin-top: 0;
}
.status-pill[aria-pressed='true'] {
  box-shadow: 0 0 0 2px #7563db;
}
.client-folders {
  padding: 28px;
  background: #f6f7fc;
  min-height: 70vh;
  color: #25334b;
  font-family: inherit;
}
.folder-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 28px;
}
.folder-heading h1 {
  font-size: 30px;
  letter-spacing: -1px;
  margin: 10px 0;
}
.folder-heading h1 span {
  color: #7264d8;
}
.folder-heading p,
.folder-intro p {
  margin: 8px 0;
  color: #63708a;
  font-size: 14px;
}
.folder-eyebrow {
  font-size: 11px;
  letter-spacing: 2px;
  color: #7063bc;
  font-weight: 700;
}
.client-folders button {
  cursor: pointer;
  font: inherit;
}
.client-folders button:disabled {
  opacity: 0.55;
  cursor: default;
}
.client-folders button:focus-visible,
.client-folders input:focus-visible,
.client-folders select:focus-visible {
  outline: 3px solid #ada4f1;
  outline-offset: 3px;
}
.folder-refresh,
.folder-back {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid #e0e4ef;
  border-radius: 10px;
  background: white;
  padding: 10px 14px;
  color: #4a5370;
}
.folder-back {
  padding: 6px 0;
  border: 0;
  background: transparent;
}
.folder-intro {
  display: flex;
  align-items: center;
  gap: 18px;
  background: linear-gradient(110deg, #e6e4fa, #e7f2fc);
  padding: 24px;
  border-radius: 18px;
  margin-bottom: 22px;
  color: #5d52b7;
}
.folder-intro strong {
  font-size: 18px;
  color: #353659;
}
.folder-search {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  background: #fff;
  border: 1px solid #e7e9f2;
  border-radius: 13px;
  padding: 12px 16px;
  margin: 20px 0 30px;
}
.folder-search input {
  flex: 1;
  min-width: 160px;
  border: 0 !important;
  margin: 0 !important;
  padding: 8px !important;
  background: transparent;
}
.folder-search > button {
  border: 0;
  background: #6758d0;
  color: #fff;
  border-radius: 9px;
  padding: 10px 18px;
}
.folder-search > span {
  color: #6c7790;
  font-size: 12px;
}
.folder-search label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  margin: 0;
}
.folder-search select {
  width: auto;
  margin: 0;
  padding: 8px;
  border: 1px solid #dfe3ee;
  border-radius: 8px;
}
.folder-export {
  display: flex;
  align-items: end;
  gap: 16px;
  flex-wrap: wrap;
  margin: 20px 0;
  padding: 16px;
  background: #fff;
  border: 1px solid #e5e4f5;
  border-radius: 12px;
}
.folder-export > label {
  display: grid;
  gap: 7px;
  font-size: 12px;
  flex: 1;
  min-width: 220px;
}
.folder-export select {
  margin: 0;
  border: 1px solid #dce0ed;
  border-radius: 8px;
  padding: 9px;
}
.folder-export > small {
  width: 100%;
  color: #68748c;
  font-size: 11px;
}
.folder-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 40px 24px;
  padding-top: 20px;
}
.client-folder {
  position: relative;
  text-align: left;
  border: 1px solid #e1def7;
  border-radius: 0 18px 18px 18px;
  padding: 24px;
  background: #eeeafb;
  color: #443b84;
  box-shadow: 0 9px 24px #39316b0a;
  transition:
    transform 0.18s,
    box-shadow 0.18s;
}
.client-folder:before {
  content: '';
  position: absolute;
  left: -1px;
  top: -18px;
  width: 38%;
  height: 19px;
  background: inherit;
  border: 1px solid #e1def7;
  border-bottom: 0;
  border-radius: 13px 18px 0 0;
}
.client-folder:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 24px #57508a18;
}
.folder-tone-1 {
  background: #e8f1fd;
  color: #315b91;
  border-color: #dce7f7;
}
.folder-tone-2 {
  background: #e8f5f0;
  color: #2c6b5d;
  border-color: #d8ebe3;
}
.folder-topline {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 11px;
}
.folder-topline svg:last-child {
  margin-left: auto;
}
.folder-name {
  display: block;
  font-size: 20px;
  line-height: 1.3;
  overflow-wrap: anywhere;
  margin: 22px 0 6px;
}
.folder-meta {
  display: block;
  font-size: 12px;
  opacity: 0.8;
}
.folder-totals {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  border-top: 1px solid #ffffffb3;
  margin-top: 22px;
  padding-top: 18px;
  font-size: 12px;
}
.folder-totals b {
  font-size: 22px;
  display: block;
  margin-bottom: 4px;
}
.folder-open {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 24px;
  font-size: 13px;
  font-weight: 600;
}
.folder-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}
.folder-metrics > div {
  padding: 20px;
  border-radius: 17px;
  display: grid;
  gap: 8px;
}
.folder-metrics strong {
  font-size: 32px;
}
.folder-metrics span {
  font-size: 13px;
}
.folder-metrics small {
  font-size: 11px;
  color: #53627b;
}
.metric-blue {
  background: #dceaff;
}
.metric-purple {
  background: #e8e1fb;
}
.metric-mint {
  background: #dff3eb;
}
.metric-peach {
  background: #fcecd9;
}
.folder-statuses {
  display: flex;
  gap: 9px;
  flex-wrap: wrap;
  margin: 22px 0 12px;
}
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 7px 11px;
  background: #edf0f7;
  color: #536079;
  border: 0;
  border-radius: 8px;
  font-size: 12px;
  white-space: nowrap;
}
.performed,
.closed {
  background: #e0f3e9;
  color: #237357;
}
.absent,
.overdue {
  background: #ffebe8;
  color: #a34538;
}
.report_due,
.not_performed {
  background: #fff0d9;
  color: #946211;
}
.scheduled,
.rescheduled {
  background: #e5edff;
  color: #365ab0;
}
.folder-rule {
  font-size: 12px;
  color: #64718a;
  line-height: 1.7;
}
.folder-tabs {
  display: flex;
  gap: 9px;
  border-bottom: 1px solid #e2e5f0;
  margin-top: 28px;
  overflow-x: auto;
}
.folder-tabs button {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 16px;
  border: 0;
  border-bottom: 3px solid transparent;
  background: transparent;
  color: #67738c;
  white-space: nowrap;
}
.folder-tabs button[aria-current] {
  color: #5f4ec5;
  border-bottom-color: #7563db;
}
.folder-tabs span {
  font-size: 11px;
  background: #ebe8f8;
  border-radius: 6px;
  padding: 3px 6px;
}
.folder-table {
  background: white;
  border: 1px solid #e4e7f1;
  border-radius: 14px;
  overflow: auto;
}
.folder-table table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.folder-table th {
  background: #f1f2f9;
  text-align: left;
  padding: 15px;
  color: #69758c;
  font-weight: 500;
  white-space: nowrap;
}
.folder-table td {
  padding: 16px;
  border-bottom: 1px solid #edf0f6;
}
.folder-table td strong {
  font-weight: 600;
}
.folder-table small {
  display: block;
  margin-top: 5px;
  color: #78839a;
  font-size: 11px;
}
.folder-note {
  max-width: 330px;
  min-width: 160px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.folder-call-link {
  display: block;
  margin-top: 8px;
  border: 0;
  background: transparent;
  color: #5b4cba;
  font-size: 12px;
  padding: 4px 0;
}
.folder-link {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: 0;
  background: #eeebfc;
  color: #5b4cba;
  padding: 9px 12px;
  border-radius: 8px;
  white-space: nowrap;
}
.folder-pagination {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
  margin: 24px 0;
  font-size: 12px;
}
.folder-pagination > span {
  margin-right: auto;
  color: #6b7890;
}
.folder-pagination button {
  background: white;
  border: 1px solid #e1e5f0;
  border-radius: 8px;
  padding: 9px 13px;
  color: #4a5874;
}
.folder-empty {
  padding: 40px !important;
  text-align: center;
  color: #707e96;
}
.folder-error {
  background: #fff0ec;
  border-radius: 10px;
  padding: 14px;
  color: #a04538;
}
@media (min-width: 1700px) {
  .folder-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
@media (max-width: 1100px) {
  .folder-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .folder-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 650px) {
  .client-folders {
    padding: 18px;
  }
  .folder-grid,
  .folder-metrics {
    grid-template-columns: 1fr;
  }
  .folder-heading {
    align-items: flex-start;
  }
  .folder-heading h1 {
    font-size: 25px;
  }
  .folder-refresh {
    font-size: 0;
    padding: 10px;
  }
  .folder-search {
    gap: 6px;
  }
  .folder-tabs button {
    padding: 12px 8px;
  }
}
</style>
