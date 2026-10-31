<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue';
import { appointmentStatus, appointmentStatusLabels } from './appointment-status';
import AssuranceQualificationSnapshot from './AssuranceQualificationSnapshot.vue';
const props = defineProps<{
  role: string;
  request: (path: string, body?: any, method?: string) => Promise<any>;
  portal: (path: string, body?: any) => Promise<any>;
  contactRevision?: number;
  appointmentId?: number;
  contactId?: number;
  leaseToken?: string;
  compact?: boolean;
  beforeBook?: () => Promise<void>;
  blocked?: boolean;
  historyOnly?: boolean;
}>();
const emit = defineEmits<{ busy: [value: boolean]; updated: [row: any]; booked: [row: any] }>();
const rows = ref<any[]>([]),
  count = ref(0),
  page = ref(1),
  period = ref('upcoming'),
  status = ref(''),
  busy = ref(false),
  error = ref(''),
  message = ref('');
watch(busy, (value) => emit('busy', value), { flush: 'sync' });
const incidents = ref<any[]>([]),
  incidentPage = ref(1),
  incidentCount = ref(0),
  incidentNote = ref('');
let incidentRequestId = crypto.randomUUID();
function resetIncidentId() {
  incidentRequestId = crypto.randomUUID();
}
const reportRow = ref<any>(null),
  performed = ref(''),
  problem = ref(false),
  note = ref(''),
  savedReport = ref<any>(null);
const editing = ref<any>(null),
  reason = ref(''),
  historyRow = ref<any>(null),
  history = ref<any[]>([]),
  historyPage = ref(1),
  historyCount = ref(0);
const qualificationRow = ref<any>(null);
const canWrite = computed(
  () => !props.historyOnly && ['setter', 'administrator'].includes(props.role),
);
const historyVisible = ref(true);
function showDate(value: string, rowZone: string) {
  return new Intl.DateTimeFormat('fr-FR', {
    timeZone: rowZone,
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}
async function run(action: () => Promise<void>) {
  if (busy.value) return;
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
async function load() {
  if (props.appointmentId) {
    rows.value = [await props.request(`appointments/${props.appointmentId}/`)];
    savedReport.value = await props.request(`appointments/${props.appointmentId}/report/`);
    count.value = 1;
    emit('updated', rows.value[0]);
    return;
  }
  const result = await props.request(
    `appointments/?page=${page.value}&period=${period.value}&business_status=${status.value}${props.contactId ? '&contact_id=' + props.contactId : ''}`,
  );
  rows.value = result.results;
  count.value = result.count;
}
function edit(row: any) {
  editing.value = row;
  reason.value = '';
}
async function cancel() {
  await run(async () => {
    const row = editing.value;
    await props.request(`appointments/${row.id}/cancel/`, {
      revision: row.revision,
      reason: reason.value,
    });
    editing.value = null;
    await load();
    message.value = 'Rendez-vous annulé. Historique conservé.';
  });
}
async function openReport(row: any) {
  await run(async () => {
    reportRow.value = row;
    performed.value = '';
    problem.value = false;
    note.value = '';
    savedReport.value = await props.request(`appointments/${row.id}/report/`);
    incidentPage.value = 1;
    incidentNote.value = '';
    incidentRequestId = crypto.randomUUID();
    await loadIncidents();
  });
}
async function loadIncidents() {
  const data = await props.request(
    `appointments/${reportRow.value.id}/incidents/?page=${incidentPage.value}`,
  );
  incidents.value = data.results;
  incidentCount.value = data.count;
}
async function signal() {
  await run(async () => {
    await props.request(`appointments/${reportRow.value.id}/incidents/`, {
      request_id: incidentRequestId,
      note: incidentNote.value,
    });
    incidentRequestId = crypto.randomUUID();
    incidentNote.value = '';
    incidentPage.value = 1;
    await loadIncidents();
    message.value = 'Signalement enregistré et suivi transmis.';
  });
}
async function submitReport() {
  await run(async () => {
    await props.request(`appointments/${reportRow.value.id}/report/`, {
      revision: reportRow.value.revision,
      performed: performed.value === 'performed',
      outcome: performed.value,
      problem: problem.value,
      note: note.value,
    });
    reportRow.value = null;
    message.value = 'Compte rendu enregistré.';
    await load();
  });
}
async function loadHistory() {
  const result = await props.request(
    `appointments/${historyRow.value.id}/history/?page=${historyPage.value}`,
  );
  history.value = result.results;
  historyCount.value = result.count;
}
onMounted(() =>
  run(async () => {
    await load();
  }),
);
</script>
<template>
  <section
    class="appointments"
    :class="{
      'compact-booking': compact,
      'appointment-detail-mode': !!appointmentId,
    }"
  >
    <h3 v-if="!appointmentId && (compact || contactId)">
      {{ compact ? 'Réserver un rendez-vous' : 'Rendez-vous du prospect' }}
    </h3>
    <p v-if="!appointmentId && role === 'advisor'" class="subtle">
      Vos rendez-vous. Consultez la qualification transmise, puis renseignez le compte rendu après
      la rencontre.
    </p>
    <p v-else-if="!appointmentId && !historyOnly" class="subtle">
      Pour transmettre une nouvelle rencontre, utilisez « Qualification et rendez-vous » dans la
      fiche du prospect après sa réservation externe.
    </p>
    <p v-if="error" role="alert" class="error">{{ error }}</p>
    <p v-if="message" role="status" class="booking-feedback">{{ message }}</p>
    <button
      v-if="compact && count > 0"
      type="button"
      class="secondary booking-history-toggle"
      @click="historyVisible = !historyVisible"
    >
      {{ historyVisible ? 'Masquer les rendez-vous existants' : 'Voir les rendez-vous existants' }}
      ({{ count }})
    </button>
    <div v-show="!compact || historyVisible">
      <form
        v-if="!appointmentId"
        class="appointment-actions"
        @submit.prevent="
          run(async () => {
            page = 1;
            await load();
          })
        "
      >
        <label
          >Période<select v-model="period">
            <option value="upcoming">À venir</option>
            <option value="past">Passés</option>
            <option value="">Tous</option>
          </select></label
        ><label
          >Statut<select v-model="status">
            <option value="">Tous</option>
            <option v-for="(label, key) in appointmentStatusLabels" :key="key" :value="key">
              {{ label }}
            </option>
          </select></label
        ><button class="secondary" :disabled="busy">Actualiser</button>
      </form>
      <div v-if="appointmentId && rows.length" class="appointment-detail">
        <div class="detail-person">
          <strong>{{ rows[0].contact.name || 'Prospect sans nom' }}</strong
          ><span>{{ rows[0].contact.phone || 'Numéro non renseigné' }}</span>
        </div>
        <dl>
          <div>
            <dt>Conseiller</dt>
            <dd>{{ rows[0].advisor.name }}</dd>
          </div>
          <div>
            <dt>Début</dt>
            <dd>{{ showDate(rows[0].starts_at, rows[0].timezone) }}</dd>
          </div>
          <div>
            <dt>Fin</dt>
            <dd>{{ showDate(rows[0].ends_at, rows[0].timezone) }}</dd>
          </div>
          <div>
            <dt>Fuseau</dt>
            <dd>{{ rows[0].timezone }}</dd>
          </div>
          <div>
            <dt>Statut</dt>
            <dd>
              <span class="appointment-business-status" :class="rows[0].business_status">{{
                appointmentStatus(rows[0])
              }}</span>
            </dd>
          </div>
          <div v-if="rows[0].reschedule_count">
            <dt>Reports</dt>
            <dd>
              {{ rows[0].reschedule_count }} · dernier le
              {{ showDate(rows[0].rescheduled_at, rows[0].timezone) }}
            </dd>
          </div>
        </dl>
        <AssuranceQualificationSnapshot :snapshot="rows[0].qualification_snapshot" />
        <div class="appointment-actions">
          <button
            v-if="
              canWrite &&
              rows[0].status === 'scheduled' &&
              !['performed', 'absent', 'not_performed'].includes(rows[0].business_status)
            "
            class="secondary"
            :disabled="busy"
            @click="edit(rows[0])"
          >
            Reporter ou annuler</button
          ><button
            v-if="
              role === 'advisor' &&
              rows[0].status === 'scheduled' &&
              Date.parse(rows[0].ends_at) <= Date.now()
            "
            class="secondary"
            :disabled="busy"
            @click="openReport(rows[0])"
          >
            Compte rendu</button
          ><button
            v-if="role === 'administrator'"
            class="secondary"
            :disabled="busy"
            @click="
              run(async () => {
                historyRow = rows[0];
                historyPage = 1;
                await loadHistory();
              })
            "
          >
            Historique
          </button>
        </div>
      </div>
      <div v-if="!appointmentId" class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Prospect</th>
              <th v-if="role !== 'advisor'">Conseiller</th>
              <th>Créneau</th>
              <th>Statut</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="row.id">
              <td>
                {{ row.contact.name || 'Sans nom' }}<small>{{ row.contact.phone }}</small>
              </td>
              <td v-if="role !== 'advisor'" data-label="Conseiller">{{ row.advisor.name }}</td>
              <td data-label="Créneau">
                {{ showDate(row.starts_at, row.timezone)
                }}<small
                  >Fin : {{ showDate(row.ends_at, row.timezone) }} · {{ row.timezone }}</small
                >
              </td>
              <td data-label="Statut">
                <span class="appointment-business-status" :class="row.business_status">{{
                  appointmentStatus(row)
                }}</span
                ><small v-if="row.reschedule_count">{{ row.reschedule_count }} report(s)</small>
              </td>
              <td>
                <p v-if="row.calendly?.conflict || row.calendly?.needs_review" role="alert">
                  Mise à jour Calendly à vérifier avec l’administration.
                </p>
                <a
                  v-if="row.calendly?.reschedule_url && row.status === 'scheduled'"
                  :href="row.calendly.reschedule_url"
                  target="_blank"
                  rel="noopener noreferrer"
                  >Reporter sur Calendly</a
                >
                <a
                  v-if="row.calendly?.cancel_url && row.status === 'scheduled'"
                  :href="row.calendly.cancel_url"
                  target="_blank"
                  rel="noopener noreferrer"
                  >Annuler sur Calendly</a
                >
                <button class="secondary" @click="qualificationRow = row">
                  Qualification transmise</button
                ><button
                  v-if="
                    role === 'advisor' &&
                    row.status === 'scheduled' &&
                    Date.parse(row.ends_at) <= Date.now()
                  "
                  class="secondary"
                  :disabled="busy"
                  @click="openReport(row)"
                >
                  Compte rendu</button
                ><button
                  v-if="
                    canWrite &&
                    row.calendar !== 'calendly' &&
                    row.status === 'scheduled' &&
                    !['performed', 'absent', 'not_performed'].includes(row.business_status)
                  "
                  class="secondary"
                  :disabled="busy"
                  @click="edit(row)"
                >
                  Gérer ce rendez-vous</button
                ><button
                  v-if="role === 'administrator'"
                  class="secondary"
                  :disabled="busy"
                  @click="
                    run(async () => {
                      historyRow = row;
                      historyPage = 1;
                      await loadHistory();
                    })
                  "
                >
                  Historique
                </button>
              </td>
            </tr>
            <tr v-if="!rows.length">
              <td colspan="5">
                {{ busy ? 'Chargement…' : 'Aucun rendez-vous dans ce périmètre.' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!appointmentId" class="appointment-actions">
        <span>{{ count }} rendez-vous · page {{ page }}</span
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
      </div>
    </div>
    <section v-if="qualificationRow">
      <AssuranceQualificationSnapshot :snapshot="qualificationRow.qualification_snapshot" /><button
        class="secondary"
        @click="qualificationRow = null"
      >
        Fermer la qualification
      </button>
    </section>
    <section
      v-if="
        appointmentId &&
        savedReport &&
        typeof savedReport.performed === 'boolean' &&
        role !== 'advisor'
      "
    >
      <h4>
        Retour du conseiller ·
        {{
          savedReport.performed ? 'Rendez-vous validé' : savedReport.outcome_label || 'Non honoré'
        }}
      </h4>
      <p style="white-space: pre-wrap">
        {{ savedReport.note || 'Aucune observation complémentaire.' }}
      </p>
    </section>
    <section v-if="editing && canWrite">
      <h4>Gérer le rendez-vous {{ editing.id }}</h4>
      <form @submit.prevent="cancel">
        <p>
          Pour une nouvelle rencontre, réservez dans l’outil externe puis transmettez une nouvelle
          occurrence depuis la fiche prospect.
        </p>
        <p v-if="editing.calendar === 'external_link'">
          Annulez également la réservation dans l’outil externe du conseiller : cette action met à
          jour le suivi dans Orvia.
        </p>
        <label
          >Motif de l’annulation<textarea
            v-model="reason"
            required
            maxlength="1000"
            :disabled="busy"
          ></textarea>
        </label>
        <button class="primary" :disabled="busy || !reason.trim()">Confirmer l’annulation</button>
        <button class="secondary" type="button" :disabled="busy" @click="editing = null">
          Conserver le rendez-vous
        </button>
      </form>
    </section>
    <section v-if="reportRow && role === 'advisor'">
      <h4>Compte rendu · RDV {{ reportRow.id }}</h4>
      <template v-if="savedReport"
        ><p>
          Résultat :
          {{
            savedReport.outcome_label ||
            (savedReport.performed ? 'Rendez-vous fait' : 'Non effectué — autre motif')
          }}
          · Problème : {{ savedReport.problem ? 'Oui' : 'Non' }}
        </p>
        <p>
          Vente ou contrat conclu :
          {{
            savedReport.sale_concluded == null
              ? 'Non renseigné'
              : savedReport.sale_concluded
                ? 'Oui'
                : 'Non'
          }}
        </p>
        <p>{{ savedReport.note }}</p>
        <form @submit.prevent="signal">
          <label
            >Signaler un problème ultérieur<textarea
              v-model="incidentNote"
              required
              maxlength="3000"
              @input="resetIncidentId"
            ></textarea></label
          ><button class="primary" :disabled="busy">Transmettre le signalement</button>
        </form>
        <h4>Signalements conservés</h4>
        <article v-for="incident in incidents" :key="incident.id">
          <p>{{ incident.note }}</p>
          <small>{{ new Date(incident.created_at).toLocaleString('fr-FR') }}</small>
        </article>
        <button
          class="secondary"
          :disabled="busy || incidentPage === 1"
          @click="
            run(async () => {
              incidentPage--;
              await loadIncidents();
            })
          "
        >
          Précédent</button
        ><button
          class="secondary"
          :disabled="busy || incidentPage * 25 >= incidentCount"
          @click="
            run(async () => {
              incidentPage++;
              await loadIncidents();
            })
          "
        >
          Suivant
        </button></template
      >
      <form v-else @submit.prevent="submitReport">
        <label
          >Résultat du rendez-vous<select v-model="performed" required :disabled="busy">
            <option value="">Choisir le résultat</option>
            <option value="performed">Rendez-vous fait</option>
            <option value="absent">Absent</option>
            <option value="not_performed">Non effectué — autre motif</option>
          </select></label
        ><label><input v-model="problem" type="checkbox" />Signaler un problème</label
        ><label
          >Précisions (obligatoires en cas d’absence, de non-réalisation ou de problème)<textarea
            v-model="note"
            maxlength="3000"
            :required="performed !== 'performed' || problem"
          ></textarea></label
        ><button class="primary" :disabled="busy || !performed">Enregistrer le compte rendu</button>
      </form>
      <button class="secondary" @click="reportRow = null">Fermer</button>
    </section>
    <section v-if="role === 'administrator' && historyRow">
      <h4>Historique du rendez-vous {{ historyRow.id }}</h4>
      <button class="secondary" @click="historyRow = null">Fermer l’historique</button>
      <article v-for="entry in history" :key="entry.id">
        <strong>{{ entry.action }}</strong
        ><small
          >{{ new Date(entry.created_at).toLocaleString('fr-FR') }} · utilisateur interne
          {{ entry.actor_id }}</small
        >
        <pre>{{ JSON.stringify(entry.metadata, null, 2) }}</pre>
      </article>
      <div class="appointment-actions">
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
    </section>
  </section>
</template>
<style scoped>
.appointments {
  margin: 24px 0;
  padding-top: 16px;
  border-top: 1px solid #dedfce;
}
.appointments form {
  display: grid;
  gap: 14px;
  margin: 20px 0;
}
.appointments select {
  padding: 12px;
  background: #fff;
  border: 1px solid #dedfce;
  border-radius: 10px;
}
.appointment-actions {
  display: flex !important;
  gap: 12px;
  flex-wrap: wrap;
  align-items: end;
}
.appointments pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 12px;
}
.appointments article {
  border-bottom: 1px solid #dedfce;
  padding: 16px 0;
}
.appointments button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
<style scoped>
.booking-unavailable {
  padding: 22px;
  background: #f4f0fc;
  border: 1px solid #e7dff6;
  border-radius: 12px;
  margin: 22px 0;
  color: #8a77aa;
}
.booking-unavailable strong {
  font-size: 14px;
  color: #8770aa;
}
.booking-unavailable p {
  font-size: 12px;
  line-height: 1.8;
  color: #9c8bb3;
  margin: 10px 0 16px;
}
.booking-history-toggle {
  margin-top: 20px;
}
</style>
<style scoped>
.compact-booking > h3 {
  color: #355274;
  font-size: 17px !important;
}
.compact-booking .friendly-slot {
  border: 0;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 14px;
}
.compact-booking .booking-feedback {
  background: #eaf6ef;
  color: #38835a !important;
  padding: 12px;
  border-radius: 8px;
}
.compact-booking input,
.compact-booking select {
  min-height: 40px;
}
.compact-booking .appointment-actions {
  font-size: 11px;
}
.compact-booking .appointment-actions button {
  font-size: 10px;
}
.compact-booking .table-scroll {
  margin-top: 16px;
}
.compact-booking > form.appointment-actions {
  border-top: 1px solid #edf1f6;
  padding-top: 18px;
}
</style>

<style scoped>
.appointment-detail-mode {
  margin: 0;
  border: 0;
  padding: 0;
}
.detail-person {
  padding: 20px;
  background: #f2edfa;
  border-radius: 15px;
  margin-bottom: 22px;
}
.detail-person strong {
  display: block;
  font-size: 17px;
  color: #79608f;
}
.detail-person span {
  display: block;
  font-size: 12px;
  margin-top: 7px;
  color: #9a86aa;
}
.appointment-detail dl {
  display: grid;
  gap: 0;
  margin: 0 0 20px;
}
.appointment-detail dl > div {
  display: grid;
  grid-template-columns: 110px 1fr;
  gap: 16px;
  padding: 14px 0;
  border-bottom: 1px solid #eae4f0;
}
.appointment-detail dt {
  font-size: 11px;
  color: #a18faa;
}
.appointment-detail dd {
  font-size: 12px;
  color: #786483;
  line-height: 1.7;
  margin: 0;
}
.appointment-detail-mode .appointment-actions button {
  font-size: 11px;
}
.appointment-detail-mode > section {
  border-top: 1px solid #e4dced;
  margin-top: 25px;
  padding-top: 15px;
}
.appointment-detail-mode form {
  font-size: 12px;
}
.appointment-detail-mode form input {
  width: 100%;
  box-sizing: border-box;
}
.appointment-detail-mode h4 {
  font-size: 15px;
  color: #816f94;
}
.appointment-detail-mode .booking-feedback {
  font-size: 12px;
  background: #ecf6f0;
  color: #7a9d8a;
  padding: 14px;
  border-radius: 10px;
}
</style>

<style scoped>
.appointment-business-status {
  display: inline-flex;
  padding: 5px 9px;
  border-radius: 7px;
  background: #edf3fc;
  color: #7893b6;
  font-size: 11px;
  line-height: 1.6;
}
.appointment-business-status.performed {
  background: #eaf6ee;
  color: #79a38c;
}
.appointment-business-status.absent,
.appointment-business-status.not_performed {
  background: #fff0e8;
  color: #bd9681;
}
.appointment-business-status.rescheduled,
.appointment-business-status.report_due {
  background: #f1ebfa;
  color: #a089bc;
}
.appointment-business-status.cancelled {
  background: #f1eff4;
  color: #a39aa9;
}
</style>
