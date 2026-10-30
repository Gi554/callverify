<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue';
import CallAction from './CallAction.vue';
import PhoneHistory from './PhoneHistory.vue';
import AssuranceContactFollowups from './AssuranceContactFollowups.vue';
import AssuranceQualification from './AssuranceQualification.vue';
import {
  UserRound,
  History,
  CalendarDays,
  Phone,
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  LoaderCircle,
  StickyNote,
} from 'lucide-vue-next';
import AssuranceAppointments from './AssuranceAppointments.vue';
import AssuranceTransmission from './AssuranceTransmission.vue';
import AssuranceAgreements from './AssuranceAgreements.vue';
import AssuranceContactInteractions from './AssuranceContactInteractions.vue';
import AssuranceContactNotes from './AssuranceContactNotes.vue';
import AssuranceContactDocuments from './AssuranceContactDocuments.vue';
import AssuranceCustomValues from './AssuranceCustomValues.vue';
import AssuranceSharedFields from './AssuranceSharedFields.vue';
const props = defineProps<{
  contact: any;
  role: string;
  portal: (path: string, body?: any) => Promise<any>;
  request: (path: string, body?: any, method?: string) => Promise<any>;
  workflow?: 'edit' | 'call';
  // Call session: the call starts by itself and closing the file moves on to the next prospect.
  autoCall?: boolean;
}>();
const emit = defineEmits<{
  close: [];
  changed: [];
  busy: [value: boolean];
  summary: [value: any];
}>();
const detailTab = ref(props.workflow ? 'appointments' : 'notes'),
  callBusy = ref(false),
  bookingBusy = ref(false);
const current = ref({ ...props.contact }),
  draft = ref({ name: props.contact.name, phone: props.contact.phone, email: props.contact.email });
const base = ref({ ...draft.value }),
  token = ref(''),
  expires = ref(''),
  locked = ref(false),
  mine = ref(false),
  busy = ref(false),
  saving = ref(false),
  error = ref(''),
  message = ref(''),
  reason = ref('');
const history = ref<any[]>([]),
  historyPage = ref(1),
  historyCount = ref(0),
  showHistory = ref(false);
const canWrite = computed(() => ['setter', 'administrator'].includes(props.role));
const pipeline = ref<any>(null),
  nextStatus = ref(current.value.status),
  statusReason = ref('');
async function loadPipeline() {
  try {
    pipeline.value = await props.request('pipeline/');
  } catch (e: any) {
    fail(e);
  }
}
async function changeStatus() {
  if (saveTimer) clearTimeout(saveTimer);
  if (!(await persist())) return;
  busy.value = true;
  error.value = '';
  try {
    current.value = await props.request(endpoint + 'commercial-status/', {
      token: token.value,
      revision: current.value.revision,
      pipeline_revision: pipeline.value.revision,
      status: nextStatus.value,
      reason: statusReason.value,
    });
    statusReason.value = '';
    message.value = 'Statut commercial enregistré.';
    emit('changed');
    emit('summary', current.value);
  } catch (e: any) {
    fail(e);
  } finally {
    busy.value = false;
  }
}
const dirty = computed(() =>
  Object.keys(draft.value).some(
    (key) =>
      draft.value[key as keyof typeof draft.value] !== base.value[key as keyof typeof base.value],
  ),
);
const flowTab = ref(props.workflow === 'call' ? 'exchange' : 'contact'),
  flowBody = ref<HTMLElement | null>(null),
  closePrompt = ref(false);
const qualification = ref<InstanceType<typeof AssuranceQualification> | null>(null),
  qualificationBusy = ref(false),
  qualificationDirty = ref(false);
const transmissionDirty = ref(false);
const followupBusy = ref(false),
  followupDirty = ref(false),
  followups = ref<InstanceType<typeof AssuranceContactFollowups> | null>(null);
const fieldsDirty = ref(false),
  noteDirty = ref(false),
  documentDirty = ref(false),
  fieldsBusy = ref(false),
  noteBusy = ref(false),
  documentBusy = ref(false);
const blocked = computed(
  () =>
    busy.value ||
    saving.value ||
    callBusy.value ||
    bookingBusy.value ||
    fieldsBusy.value ||
    noteBusy.value ||
    documentBusy.value ||
    followupBusy.value ||
    qualificationBusy.value,
);
const pendingDrafts = computed(
  () =>
    (!token.value && dirty.value) ||
    qualificationDirty.value ||
    transmissionDirty.value ||
    followupDirty.value ||
    fieldsDirty.value ||
    noteDirty.value ||
    documentDirty.value ||
    nextStatus.value !== current.value.status ||
    !!statusReason.value.trim(),
);
watch(blocked, (value) => emit('busy', value), { immediate: true });
let discarding = false;
async function changeFlow(tab: string) {
  if (blocked.value) return;
  if (saveTimer) clearTimeout(saveTimer);
  if (!(await persist())) return;
  if (tab === 'booking') {
    try {
      await qualification.value?.ensureSaved();
      await nextTick();
    } catch (e: any) {
      fail(e);
      return;
    }
  }
  flowTab.value = tab;
  closePrompt.value = false;
  if (flowBody.value) flowBody.value.scrollTop = 0;
}
async function discardAndClose() {
  discarding = true;
  if (!token.value) draft.value = { ...base.value };
  await close();
  discarding = false;
}
const endpoint = `contacts/${props.contact.id}/`;
let lastActivity = Date.now(),
  saveTimer: ReturnType<typeof setTimeout> | undefined,
  pulseTimer: ReturnType<typeof setInterval> | undefined,
  disposed = false,
  pendingSave: Promise<boolean> | null = null;
function fail(e: any) {
  if (props.workflow && flowBody.value) flowBody.value.scrollTop = 0;
  error.value = e.message;
  message.value = '';
  if (e.status === 409) {
    token.value = '';
    message.value =
      'Votre verrou ou votre version n’est plus valable. Reprenez la fiche pour la recharger.';
  }
}
async function refreshLock() {
  if (!canWrite.value) return;
  const state = await props.request(endpoint + 'lease/');
  locked.value = state.locked;
  mine.value = state.mine;
  expires.value = state.expires_at || '';
}
async function claim() {
  busy.value = true;
  error.value = '';
  message.value = '';
  try {
    const lease = await props.request(endpoint + 'lease/', {});
    token.value = lease.token;
    expires.value = lease.expires_at;
    lastActivity = Date.now();
    current.value = await props.request(endpoint);
    draft.value = {
      name: current.value.name,
      phone: current.value.phone,
      email: current.value.email,
    };
    base.value = { ...draft.value };
    locked.value = true;
    mine.value = true;
    message.value = 'Fiche prise en charge. Sauvegarde automatique activée.';
  } catch (e: any) {
    fail(e);
  } finally {
    busy.value = false;
  }
}
async function persist(): Promise<boolean> {
  if (pendingSave) return pendingSave;
  if (!dirty.value) return true;
  if (!token.value) {
    error.value = 'Reprenez la fiche avant de modifier.';
    return false;
  }
  const changes = { ...draft.value },
    leaseToken = token.value;
  saving.value = true;
  error.value = '';
  message.value = 'Enregistrement…';
  pendingSave = (async () => {
    try {
      const result = await props.request(
        endpoint,
        { ...changes, revision: current.value.revision, token: leaseToken },
        'PATCH',
      );
      current.value = result;
      base.value = changes;
      message.value = 'Modifications enregistrées.';
      emit('changed');
      emit('summary', current.value);
      return true;
    } catch (e: any) {
      fail(e);
      return false;
    } finally {
      saving.value = false;
      pendingSave = null;
    }
  })();
  const success = await pendingSave;
  if (success && dirty.value && !disposed) schedule();
  return success;
}
function schedule() {
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    void persist();
  }, 1200);
}
function activity() {
  lastActivity = Date.now();
}
function edited() {
  activity();
  schedule();
}
async function prepareCall() {
  if (saveTimer) clearTimeout(saveTimer);
  if (!(await persist()) || !token.value || dirty.value)
    throw new Error('Enregistrez et prenez en charge la fiche avant de continuer.');
}
async function prepareBooking() {
  await prepareCall();
  if (!qualification.value) throw new Error('Chargez la qualification avant de réserver.');
  await qualification.value.ensureSaved();
  await nextTick();
}
function qualificationPayload() {
  if (!qualification.value) throw new Error('Chargez la qualification avant de transmettre.');
  return qualification.value.payload();
}
async function transmitted(row: any) {
  current.value.revision = row.contact_revision;
  qualification.value?.markSaved();
  await followups.value?.booked(row);
  emit('changed');
}
async function callIntent(id: string) {
  if (saveTimer) clearTimeout(saveTimer);
  if (!(await persist()) || !token.value || dirty.value)
    throw new Error('Enregistrez et prenez en charge la fiche avant de continuer.');
  return props.request(endpoint + 'call-intent/', {
    request_id: id,
    token: token.value,
    contact_revision: current.value.revision,
  });
}
async function release() {
  if (saveTimer) clearTimeout(saveTimer);
  if (pendingSave && !(await pendingSave)) return false;
  if (dirty.value && !(await persist())) return false;
  if (!token.value) return true;
  try {
    await props.request(endpoint + 'lease/', { token: token.value }, 'DELETE');
    token.value = '';
    await refreshLock();
    message.value = 'Fiche libérée.';
    return true;
  } catch (e: any) {
    fail(e);
    return false;
  }
}
async function close() {
  if (blocked.value) return;
  if (pendingDrafts.value && !discarding) {
    closePrompt.value = true;
    return;
  }
  busy.value = true;
  if (await release()) emit('close');
  busy.value = false;
}
async function pulse() {
  if (!token.value || busy.value || saving.value) return;
  if (Date.now() >= Date.parse(expires.value)) {
    token.value = '';
    message.value = 'Verrou expiré après inactivité. Reprenez la fiche pour continuer.';
    return;
  }
  if (document.visibilityState !== 'visible' || Date.now() - lastActivity > 120000) return;
  try {
    const lease = await props.request(endpoint + 'lease/', { token: token.value }, 'PATCH');
    expires.value = lease.expires_at;
  } catch (e: any) {
    fail(e);
  }
}
async function unlock() {
  busy.value = true;
  error.value = '';
  try {
    await props.request(endpoint + 'unlock/', { reason: reason.value });
    token.value = '';
    reason.value = '';
    await refreshLock();
    message.value = 'Déverrouillage administrateur enregistré.';
  } catch (e: any) {
    fail(e);
  } finally {
    busy.value = false;
  }
}
async function loadHistory() {
  error.value = '';
  try {
    const result = await props.request(endpoint + 'history/?page=' + historyPage.value);
    history.value = result.results;
    historyCount.value = result.count;
    showHistory.value = true;
  } catch (e: any) {
    fail(e);
  }
}
defineExpose({ close });
onMounted(async () => {
  try {
    await refreshLock();
    if (canWrite.value) await loadPipeline();
    if (props.workflow && canWrite.value) await claim();
  } catch (e: any) {
    fail(e);
  }
  pulseTimer = setInterval(() => {
    void pulse();
  }, 30000);
});
onBeforeUnmount(() => {
  disposed = true;
  if (saveTimer) clearTimeout(saveTimer);
  if (pulseTimer) clearInterval(pulseTimer);
  const activeToken = token.value;
  const finish = pendingSave || Promise.resolve(true);
  void finish
    .then(() => {
      if (activeToken) return props.request(endpoint + 'lease/', { token: activeToken }, 'DELETE');
    })
    .catch(() => {});
});
</script>
<template>
  <section
    v-if="workflow || canWrite"
    class="guided-editor"
    aria-label="Fiche prospect"
    @pointerdown="activity"
    @keydown="activity"
  >
    <nav class="drawer-tabs" aria-label="Rubriques de la fiche">
      <button
        :aria-current="flowTab === 'contact' ? 'page' : undefined"
        :disabled="blocked"
        @click="changeFlow('contact')"
      >
        <UserRound :size="17" />Coordonnées
      </button>
      <button
        :aria-current="flowTab === 'exchange' ? 'page' : undefined"
        :disabled="blocked"
        @click="changeFlow('exchange')"
      >
        <Phone :size="17" />Appels et rappels
      </button>
      <button
        :aria-current="flowTab === 'booking' ? 'page' : undefined"
        :disabled="blocked"
        @click="changeFlow('booking')"
      >
        <CalendarDays :size="17" />Qualification et rendez-vous
      </button>
      <button
        :aria-current="flowTab === 'history' ? 'page' : undefined"
        :disabled="blocked"
        @click="changeFlow('history')"
      >
        <History :size="17" />Historique
      </button>
    </nav>
    <div ref="flowBody" class="drawer-scroll">
      <p v-if="error" role="alert" class="drawer-feedback drawer-error">{{ error }}</p>
      <div v-if="!token" class="drawer-access">
        <p>
          {{
            blocked
              ? 'Ouverture de la fiche…'
              : 'La fiche est en lecture seule. Reprenez-la pour modifier les informations.'
          }}
        </p>
        <button v-if="!busy" class="secondary" :disabled="blocked" @click="claim">
          Reprendre la fiche
        </button>
      </div>
      <div class="drawer-call-card">
        <div class="call-number">
          <span class="call-icon"><Phone :size="19" /></span>
          <div>
            <small>LE PROCHAIN ÉCHANGE COMMENCE ICI</small
            ><strong>{{ current.phone || 'Numéro non renseigné' }}</strong>
          </div>
        </div>
        <CallAction
          v-if="canWrite && token"
          :auto-open="workflow === 'call'"
          :auto-send="autoCall"
          @busy="callBusy = $event"
          workspace="assurance"
          :resource-id="current.id"
          :phone="current.phone"
          :portal="portal"
          :prepare="callIntent"
          :before-open="prepareCall"
          :disabled="!token || busy || saving || bookingBusy"
        />
      </div>
      <div v-if="flowTab === 'history'" class="drawer-view">
        <AssuranceContactInteractions
          :contact-id="current.id"
          :request="request"
          :portal="portal"
        />
        <section v-if="role === 'administrator'" class="sheet-section">
          <h3>Modifications de la fiche</h3>
          <button
            class="secondary"
            :disabled="blocked"
            @click="
              historyPage = 1;
              loadHistory();
            "
          >
            Consulter le journal des modifications</button
          ><template v-if="showHistory"
            ><p v-if="!history.length">Aucune modification enregistrée.</p>
            <article v-for="entry in history" :key="entry.id">
              <strong>{{ entry.action }}</strong>
              <p>
                Compte n° {{ entry.actor_id }} ·
                {{ new Date(entry.created_at).toLocaleString('fr-FR') }}
              </p>
              <details>
                <summary>Détails de la modification</summary>
                <pre style="white-space: pre-wrap; overflow-wrap: anywhere">{{
                  JSON.stringify(entry.metadata, null, 2)
                }}</pre>
              </details>
            </article>
            <div class="history-pages">
              <button
                class="secondary"
                :disabled="blocked || historyPage === 1"
                @click="
                  historyPage--;
                  loadHistory();
                "
              >
                Précédent</button
              ><span>Page {{ historyPage }} · {{ historyCount }} action(s)</span
              ><button
                class="secondary"
                :disabled="blocked || historyPage * 25 >= historyCount"
                @click="
                  historyPage++;
                  loadHistory();
                "
              >
                Suivant
              </button>
            </div></template
          >
        </section>
      </div>
      <div v-show="flowTab === 'exchange'" class="drawer-view">
        <PhoneHistory
          v-if="role === 'setter'"
          workspace="assurance"
          :resource-id="current.id"
          :request="request"
          :portal="portal"
          :blocked="blocked"
        /><AssuranceContactFollowups
          ref="followups"
          :contact-id="current.id"
          :revision="current.revision"
          :token="token"
          :blocked="busy || saving || bookingBusy || callBusy"
          :request="request"
          :prepare="prepareCall"
          @busy="followupBusy = $event"
          @dirty="followupDirty = $event"
          @qualify="changeFlow('booking')"
          @review="flowTab = 'exchange'"
          @saved="emit('changed')"
          @advance="close"
        />
      </div>
      <div v-show="flowTab === 'contact'" class="drawer-view">
        <div class="drawer-section-heading">
          <span class="section-icon blue"><UserRound :size="19" /></span>
          <div>
            <h3>Les coordonnées du prospect</h3>
            <p>Un contact à jour pour un échange plus simple.</p>
          </div>
        </div>
        <form class="drawer-contact-form" @submit.prevent="persist" @input="edited">
          <label
            >Nom du prospect<input
              v-model="draft.name"
              :readonly="!token || busy || bookingBusy"
              maxlength="250"
              placeholder="Nom et prénom"
              autocomplete="off" /></label
          ><label
            >Numéro de téléphone<input
              v-model="draft.phone"
              :readonly="!token || busy || bookingBusy"
              maxlength="250"
              required
              autocomplete="off" /></label
          ><label
            >Adresse e-mail<input
              v-model="draft.email"
              :readonly="!token || busy || bookingBusy"
              maxlength="254"
              placeholder="Non renseignée"
              autocomplete="off"
          /></label>
        </form>
        <div class="drawer-tip">
          <CheckCircle2 :size="17" />
          <p>Les coordonnées s’enregistrent automatiquement pendant votre saisie.</p>
        </div>
      </div>
      <div v-show="flowTab === 'booking'" class="drawer-view">
        <AssuranceQualification
          combined
          ref="qualification"
          :contact-id="current.id"
          :role="role"
          :lease-token="token"
          :contact-revision="current.revision"
          :request="request"
          :prepare="prepareCall"
          :blocked="busy || saving || bookingBusy || callBusy"
          @busy="qualificationBusy = $event"
          @dirty="qualificationDirty = $event"
          @saved="
            current.revision = $event;
            emit('changed');
          "
        />
        <AssuranceTransmission
          :contact-id="current.id"
          :contact-revision="current.revision"
          :lease-token="token"
          :role="role"
          :request="request"
          :portal="portal"
          :blocked="busy || saving || callBusy || qualificationBusy"
          :prepare="prepareBooking"
          :qualification="qualificationPayload"
          @busy="bookingBusy = $event"
          @dirty="transmissionDirty = $event"
          @booked="transmitted"
        />
      </div>
    </div>
    <footer class="drawer-actions">
      <div v-if="closePrompt" class="drawer-unsaved" role="alert">
        <p>
          Des modifications ne sont pas encore enregistrées. Vous pouvez les conserver en gardant
          cette fiche ouverte.
        </p>
        <button class="secondary" @click="closePrompt = false">Rester sur la fiche</button
        ><button class="drawer-discard" :disabled="blocked" @click="discardAndClose">
          Fermer sans ces saisies
        </button>
      </div>
      <div v-else class="drawer-save-state" role="status">
        <LoaderCircle v-if="saving || busy" :size="14" class="save-spinner" /><StickyNote
          v-else-if="pendingDrafts || dirty"
          :size="14"
          class="save-pending"
        /><CheckCircle2 v-else :size="14" /><span>{{
          saving
            ? 'Enregistrement des coordonnées…'
            : busy
              ? 'Chargement…'
              : !token
                ? 'Lecture seule'
                : pendingDrafts
                  ? 'Saisie à enregistrer dans son onglet'
                  : dirty
                    ? 'Modifications en cours…'
                    : 'Coordonnées à jour'
        }}</span>
      </div>
      <div class="drawer-action-row">
        <button
          v-if="flowTab !== 'contact'"
          class="secondary"
          :disabled="blocked"
          @click="changeFlow(flowTab === 'booking' ? 'exchange' : 'contact')"
        >
          <ArrowLeft :size="15" />Retour</button
        ><button v-else class="secondary" :disabled="blocked" @click="close">Fermer</button
        ><button
          v-if="flowTab !== 'booking'"
          class="primary"
          :disabled="blocked"
          @click="changeFlow(flowTab === 'contact' ? 'exchange' : 'booking')"
        >
          {{
            flowTab === 'contact'
              ? 'Résultat et rappel'
              : flowTab === 'exchange'
                ? 'Qualification et rendez-vous'
                : 'Préparer le rendez-vous'
          }}<ArrowRight :size="16" /></button
        ><button v-else class="primary" :disabled="blocked" @click="close">
          {{ autoCall ? 'Terminer · prospect suivant' : 'Terminer' }}<CheckCircle2 :size="16" />
        </button>
      </div>
    </footer>
  </section>
  <section
    v-else
    class="contact-editor"
    aria-label="Fiche contact"
    @pointerdown="activity"
    @keydown="activity"
  >
    <div v-if="closePrompt" class="drawer-unsaved" role="alert">
      <p>Une qualification ou une saisie n’est pas encore enregistrée.</p>
      <button class="secondary" @click="closePrompt = false">Continuer la saisie</button
      ><button class="secondary" @click="discardAndClose">Abandonner et fermer</button>
    </div>
    <header class="record-header">
      <button
        class="secondary"
        :disabled="busy || saving || callBusy || bookingBusy"
        @click="close"
      >
        {{ workflow ? 'Fermer la fiche' : '← Contacts' }}
      </button>
      <div>
        <h3>{{ current.name || 'Contact sans nom' }}</h3>
        <span>{{ current.status_label || current.status }}</span>
      </div>
      <small>Dossier #{{ current.id }}</small>
    </header>
    <p v-if="error" role="alert" class="error record-feedback">{{ error }}</p>
    <p v-if="message" role="status" class="record-feedback">{{ message }}</p>
    <p v-if="workflow === 'call'" class="workflow-intro">
      Préparez et confirmez l’appel, puis complétez la fiche et réservez un rendez-vous avec un
      conseiller. Cette fenêtre reste ouverte pendant votre échange.
    </p>
    <button
      v-if="workflow && !token && canWrite"
      class="secondary workflow-retry"
      :disabled="busy"
      @click="claim"
    >
      Reprendre la fiche pour modifier
    </button>
    <div class="record-columns">
      <aside class="record-information">
        <div class="record-panel-title">Informations du contact</div>
        <div class="record-panel-body">
          <template v-if="canWrite && !workflow"
            ><p>
              {{
                token
                  ? 'Vous avez la prise en charge de cette fiche.'
                  : locked
                    ? mine
                      ? 'Fiche prise en charge dans une autre session de votre compte.'
                      : 'Fiche prise en charge par un autre utilisateur. Lecture seule disponible.'
                    : 'Cette fiche est disponible.'
              }}
            </p>
            <p v-if="expires" class="subtle">
              Expiration du verrou : {{ new Date(expires).toLocaleTimeString('fr-FR') }}.
              Renouvellement pendant votre activité.
            </p>
            <button v-if="!token" class="primary" :disabled="busy" @click="claim">
              Prendre en charge / actualiser</button
            ><button v-else class="secondary" :disabled="busy || saving" @click="release">
              Enregistrer et libérer
            </button></template
          >
          <CallAction
            v-if="canWrite && (!workflow || !!token)"
            :auto-open="workflow === 'call'"
            @busy="callBusy = $event"
            workspace="assurance"
            :resource-id="current.id"
            :phone="current.phone"
            :portal="portal"
            :prepare="callIntent"
            :before-open="prepareCall"
            :disabled="!token || busy || saving"
          />
          <form @submit.prevent="persist" @input="edited">
            <label
              >Nom<input v-model="draft.name" :readonly="!token || busy" maxlength="250" /></label
            ><label
              >Téléphone fourni<input
                v-model="draft.phone"
                :readonly="!token || busy"
                maxlength="250"
                required /></label
            ><label
              >E-mail fourni<input v-model="draft.email" :readonly="!token || busy" maxlength="254"
            /></label>
            <p v-if="!workflow">
              Statut : {{ current.status_label || current.status }} · version {{ current.revision }}
            </p>
            <button v-if="token" class="primary" :disabled="busy || saving || !dirty">
              {{ saving ? 'Enregistrement…' : 'Enregistrer maintenant' }}
            </button>
          </form>
          <button v-if="!token && dirty" class="secondary" @click="emit('close')">
            Fermer sans enregistrer les changements locaux</button
          ><template v-if="role === 'administrator'"
            ><form class="unlock-form" @submit.prevent="unlock">
              <label
                >Motif du déverrouillage forcé<input
                  v-model="reason"
                  maxlength="1000"
                  required /></label
              ><button class="secondary" :disabled="busy || saving || !!token || !reason.trim()">
                Déverrouiller la fiche
              </button>
            </form>
            <button
              class="secondary"
              @click="
                historyPage = 1;
                loadHistory();
              "
            >
              Consulter l’historique administrateur
            </button>
            <div v-if="showHistory">
              <p v-if="!history.length">Aucune modification enregistrée.</p>
              <article v-for="entry in history" :key="entry.id">
                <strong>{{ entry.action }}</strong
                ><small
                  >{{ new Date(entry.created_at).toLocaleString('fr-FR') }} · utilisateur interne
                  {{ entry.actor_id }}</small
                >
                <pre>{{ JSON.stringify(entry.metadata, null, 2) }}</pre>
              </article>
              <div class="history-pages">
                <button
                  class="secondary"
                  :disabled="historyPage === 1"
                  @click="
                    historyPage--;
                    loadHistory();
                  "
                >
                  Précédent</button
                ><span>Page {{ historyPage }}</span
                ><button
                  class="secondary"
                  :disabled="historyPage * 25 >= historyCount"
                  @click="
                    historyPage++;
                    loadHistory();
                  "
                >
                  Suivant
                </button>
              </div>
            </div></template
          >
          <AssuranceQualification
            ref="qualification"
            :contact-id="current.id"
            :role="role"
            :lease-token="token"
            :contact-revision="current.revision"
            :request="request"
            :prepare="prepareCall"
            :blocked="busy || saving || bookingBusy || callBusy"
            @busy="qualificationBusy = $event"
            @dirty="qualificationDirty = $event"
            @saved="
              current.revision = $event;
              emit('changed');
            "
          />
          <AssuranceSharedFields
            v-if="role === 'advisor'"
            :contact-id="current.id"
            :request="request"
          />
          <AssuranceCustomValues
            v-if="canWrite"
            :contact-id="current.id"
            :lease-token="token"
            :blocked="busy || saving"
            :request="request"
            @saved="
              current.revision = $event;
              emit('changed');
            "
          />
          <section v-if="canWrite">
            <h3>Statut commercial : {{ current.status_label || current.status }}</h3>
            <p>
              Le statut ne remplace pas le compte rendu d’un rendez-vous ni l’enregistrement d’un
              contrat.
            </p>
            <form v-if="pipeline" @submit.prevent="changeStatus">
              <label
                >Nouveau statut<select v-model="nextStatus" :disabled="!token || busy || saving">
                  <option
                    v-for="stage in pipeline.stages.filter((s: any) => s.active)"
                    :key="stage.key"
                    :value="stage.key"
                  >
                    {{ stage.label }}
                  </option>
                </select></label
              ><label
                >Motif du changement<textarea
                  v-model="statusReason"
                  maxlength="1000"
                  required
                  :disabled="!token || busy || saving"
                ></textarea></label
              ><button
                class="primary"
                :disabled="!token || busy || saving || nextStatus === current.status"
              >
                Enregistrer le statut
              </button>
            </form>
            <button class="secondary" :disabled="busy || saving" @click="loadPipeline">
              Recharger les statuts disponibles
            </button>
          </section>
        </div>
      </aside>
      <main v-if="!workflow" class="record-timeline">
        <div class="record-panel-title">Activité du dossier</div>
        <div class="record-panel-body">
          <AssuranceContactInteractions
            :contact-id="current.id"
            :request="request"
            :portal="portal"
          /><PhoneHistory
            v-if="role === 'setter'"
            workspace="assurance"
            :resource-id="current.id"
            :request="request"
            :portal="portal"
            :blocked="blocked"
          />
        </div>
      </main>
      <aside class="record-actions">
        <nav class="record-tabs" aria-label="Actions du dossier">
          <button :class="{ active: detailTab === 'notes' }" @click="detailTab = 'notes'">
            Notes</button
          ><button :class="{ active: detailTab === 'documents' }" @click="detailTab = 'documents'">
            Documents</button
          ><button
            :class="{ active: detailTab === 'appointments' }"
            @click="detailTab = 'appointments'"
          >
            RDV</button
          ><button
            v-if="role === 'administrator'"
            :class="{ active: detailTab === 'agreements' }"
            @click="detailTab = 'agreements'"
          >
            Contrats
          </button>
        </nav>
        <div class="record-panel-body">
          <div v-show="detailTab === 'notes'">
            <AssuranceContactNotes
              :contact-id="current.id"
              :lease-token="token"
              :role="role"
              :request="request"
            />
          </div>
          <div v-show="detailTab === 'documents'">
            <AssuranceContactDocuments
              :contact-id="current.id"
              :lease-token="token"
              :role="role"
              :request="request"
            />
          </div>
          <div v-show="detailTab === 'appointments'">
            <AssuranceAppointments
              @busy="bookingBusy = $event"
              :compact="!!workflow"
              :before-book="prepareBooking"
              :contact-revision="current.revision"
              :blocked="busy || saving"
              :contact-id="current.id"
              :lease-token="token"
              :role="role"
              :request="request"
              :portal="portal"
            />
          </div>
          <div v-if="role === 'administrator'" v-show="detailTab === 'agreements'">
            <AssuranceAgreements
              v-if="role === 'administrator'"
              :contact-id="current.id"
              :contact-revision="current.revision"
              :lease-token="token"
              :blocked="busy || saving"
              :request="request"
              @saved="
                current.revision = $event;
                emit('changed');
              "
            />
          </div>
        </div>
      </aside>
    </div>
  </section>
</template>
<style scoped>
.contact-editor {
  padding: 24px;
  border: 1px solid #dfe2ce;
  border-radius: 16px;
  margin: 24px 0;
  background: #f8f8f0;
}
.contact-editor form {
  display: grid;
  gap: 16px;
  margin: 24px 0;
}
.contact-editor input[readonly] {
  background: #f1f1e9;
  color: #727763;
}
.contact-editor article {
  border-top: 1px solid #ddd;
  padding: 16px 0;
}
.contact-editor small {
  display: block;
  margin-top: 8px;
}
.contact-editor pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 12px;
}
.history-pages {
  display: flex;
  align-items: center;
  gap: 12px;
}
.contact-editor button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.contact-editor {
  padding: 0;
  background: #fff;
  border-radius: 8px;
  margin: 0;
  overflow: hidden;
}
.record-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  border-bottom: 1px solid #e2e5dd;
  background: #fff;
}
.record-header > div {
  flex: 1;
}
.record-header h3 {
  font-size: 16px;
  margin: 0 0 5px;
}
.record-header span {
  font-size: 11px;
  color: #3974b7;
}
.record-header small {
  color: #64748b;
  font-size: 11px;
}
.record-feedback {
  margin: 0;
  padding: 12px 20px;
  background: #f6f7ef;
}
.record-columns {
  display: grid;
  grid-template-columns: minmax(245px, 0.85fr) minmax(300px, 1.15fr) minmax(280px, 1fr);
  align-items: start;
}
.record-information,
.record-timeline,
.record-actions {
  min-width: 0;
  min-height: 65vh;
}
.record-information,
.record-timeline {
  border-right: 1px solid #e3e7dd;
}
.record-panel-title {
  height: 49px;
  display: flex;
  align-items: center;
  padding: 0 18px;
  font-size: 12px;
  font-weight: 650;
  border-bottom: 1px solid #e3e7dd;
}
.record-panel-body {
  padding: 18px;
}
.record-tabs {
  display: flex;
  min-height: 49px;
  border-bottom: 1px solid #e3e7dd;
  overflow: auto;
}
.record-tabs button {
  border: 0;
  border-bottom: 2px solid transparent;
  background: none;
  padding: 14px 12px;
  color: #7c8572;
  font-size: 11px;
  cursor: pointer;
}
.record-tabs button.active {
  color: #2563a6;
  border-bottom-color: #2563a6;
  font-weight: 650;
}
.record-panel-body :deep(h3) {
  font-size: 14px !important;
  margin-top: 0;
}
.record-panel-body :deep(p) {
  font-size: 12px;
  line-height: 1.6;
  color: #64748b;
}
.record-panel-body :deep(form) {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
  margin: 18px 0;
}
.record-panel-body :deep(fieldset) {
  min-width: 0;
  display: grid;
  gap: 10px;
}
.record-panel-body :deep(input),
.record-panel-body :deep(select),
.record-panel-body :deep(textarea) {
  width: 100%;
  font-size: 12px;
  padding: 10px;
  border-radius: 6px;
}
.record-panel-body :deep(button) {
  font-size: 11px;
  padding: 9px 12px;
}
.record-panel-body :deep(article) {
  box-shadow: none;
  border-radius: 6px;
  padding: 12px;
}
.record-panel-body :deep(label) {
  font-size: 11px;
}
.record-panel-body :deep(table) {
  min-width: 560px;
}
.record-panel-body :deep(section) {
  min-width: 0;
}
.record-panel-body :deep(.table-scroll) {
  overflow: auto;
}
@media (max-width: 1150px) {
  .record-columns {
    grid-template-columns: 280px minmax(0, 1fr);
  }
  .record-actions {
    grid-column: 1/-1;
    border-top: 1px solid #e3e7dd;
    min-height: 0;
  }
  .record-timeline {
    border-right: 0;
  }
  .record-information {
    min-height: 0;
  }
}
@media (max-width: 650px) {
  .record-columns {
    display: block;
  }
  .record-information,
  .record-timeline {
    border-right: 0;
    border-bottom: 1px solid #e3e7dd;
    min-height: 0;
  }
  .record-header {
    gap: 10px;
    padding: 12px;
  }
  .record-header small {
    display: none;
  }
}
</style>
<style scoped>
.guided-editor {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  height: 100%;
  color: #30445e;
  font-family: Inter, 'Segoe UI', sans-serif;
}
.drawer-tabs {
  display: flex;
  gap: 5px;
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid #e6edf5;
  flex-shrink: 0;
}
.drawer-tabs button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  flex: 1;
  padding: 11px 7px;
  border: 0;
  border-radius: 9px;
  background: none;
  color: #8b99ae;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.drawer-tabs button[aria-current] {
  color: #547bd1;
  background: #edf3ff;
}
.drawer-tabs button:hover:not(:disabled) {
  background: #f1f5fb;
}
.drawer-tabs button:disabled {
  cursor: wait;
  opacity: 0.6;
}
.drawer-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 22px 24px 28px;
  scrollbar-width: thin;
  scrollbar-color: #c9d4e6 transparent;
}
.drawer-call-card {
  padding: 17px 18px;
  background: linear-gradient(115deg, #eaf7f0, #f4faf7);
  border: 1px solid #dceee4;
  border-radius: 13px;
  margin-bottom: 24px;
}
.call-number {
  display: flex;
  gap: 12px;
  align-items: center;
}
.call-icon {
  width: 37px;
  height: 37px;
  border-radius: 11px;
  background: white;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  color: #67ad8b;
}
.call-number small {
  display: block;
  font-size: 8px !important;
  letter-spacing: 1.3px;
  color: #86a696 !important;
  margin: 0 0 5px;
}
.call-number strong {
  font-size: 16px;
  letter-spacing: 0.2px;
  color: #427660;
  overflow-wrap: anywhere;
}
.drawer-call-card :deep(.call-action) {
  margin: 11px 0 0;
  padding-top: 10px;
  border-top: 1px solid #dbede2;
}
.drawer-call-card :deep(.call-action > button) {
  background: white;
  color: #4d8e70;
  border: 1px solid #c9e3d5;
  border-radius: 7px;
}
.drawer-call-card :deep(.call-action p) {
  font-size: 11px;
  line-height: 1.6;
}
.drawer-call-card :deep(.call-confirm) {
  border: 0;
  padding: 0;
}
.drawer-call-card :deep(.call-action small) {
  font-size: 10px;
  color: #7f988c;
}
.drawer-section-heading {
  display: flex;
  align-items: center;
  gap: 11px;
  margin-bottom: 20px;
}
.section-icon {
  display: grid;
  place-items: center;
  flex-shrink: 0;
  width: 37px;
  height: 37px;
  border-radius: 11px;
}
.section-icon.blue {
  background: #eaf1ff;
  color: #7996d4;
}
.section-icon.lavender {
  background: #f1edfc;
  color: #9a85ca;
}
.guided-editor .drawer-section-heading h3 {
  font-size: 16px;
  margin: 0 0 5px;
  letter-spacing: -0.3px;
  color: #405572;
}
.drawer-section-heading p {
  font-size: 11px;
  color: #94a0b2;
  margin: 0;
  line-height: 1.6;
}
.guided-editor form,
.guided-editor :deep(form) {
  display: grid;
  gap: 15px;
  margin: 18px 0;
}
.guided-editor label,
.guided-editor :deep(label) {
  display: grid;
  gap: 8px;
  font-size: 12px;
  color: #637893;
  font-weight: 550;
  min-width: 0;
}
.guided-editor input,
.guided-editor select,
.guided-editor textarea,
.guided-editor :deep(input:not([type='checkbox']):not([type='file'])),
.guided-editor :deep(select),
.guided-editor :deep(textarea) {
  width: 100%;
  min-width: 0;
  max-width: 100%;
  box-sizing: border-box;
  border: 1px solid #dfe6f1;
  border-radius: 8px;
  background: white;
  padding: 11px 12px;
  font:
    13px Inter,
    'Segoe UI',
    sans-serif;
  color: #3b5270;
  box-shadow: none;
  min-height: 42px;
}
.guided-editor textarea,
.guided-editor :deep(textarea) {
  min-height: 90px;
  resize: vertical;
}
.guided-editor input[readonly] {
  background: #f4f6fa;
}
.guided-editor select {
  cursor: pointer;
}
.guided-editor :deep(button.primary),
.guided-editor :deep(button.secondary),
.guided-editor .primary,
.guided-editor .secondary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 12px;
  padding: 10px 14px;
  border-radius: 8px;
  min-height: 38px;
  width: auto;
  justify-self: start;
  cursor: pointer;
}
.guided-editor .primary,
.guided-editor :deep(.primary) {
  background: #6689db;
  border: 1px solid #6689db;
  color: white;
  box-shadow: none;
}
.guided-editor .primary:hover:not(:disabled),
.guided-editor :deep(.primary:hover:not(:disabled)) {
  background: #5279cd;
}
.guided-editor button:disabled,
.guided-editor :deep(button:disabled) {
  opacity: 0.5;
  cursor: not-allowed;
}
.drawer-contact-form {
  margin-bottom: 20px !important;
}
.drawer-tip {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  background: #eff5ff;
  border-radius: 9px;
  padding: 12px 14px;
  color: #849ec3;
}
.drawer-tip svg {
  flex-shrink: 0;
  margin-top: 2px;
}
.drawer-tip p {
  font-size: 11px;
  line-height: 1.6;
  margin: 0;
}
.drawer-status-card {
  padding: 20px;
  background: white;
  border: 1px solid #e6eaf3;
  border-radius: 12px;
  margin-bottom: 18px;
}
.drawer-status-card .drawer-section-heading {
  margin-bottom: 12px;
}
.drawer-status-card form {
  margin-bottom: 0;
}
.drawer-extra {
  background: white;
  border: 1px solid #e5eaf3;
  border-radius: 12px;
  margin-top: 15px;
  overflow: hidden;
}
.drawer-extra > summary {
  display: flex;
  align-items: center;
  gap: 10px;
  list-style: none;
  padding: 16px 18px;
  font-size: 12px;
  font-weight: 600;
  color: #71819b;
  cursor: pointer;
}
.drawer-extra > summary::-webkit-details-marker {
  display: none;
}
.drawer-extra > summary > svg:first-child {
  color: #a18eca;
}
.drawer-extra > summary > svg:last-child {
  margin-left: auto;
  color: #a1aec1;
}
.drawer-extra[open] > summary > svg:last-child {
  transform: rotate(180deg);
}
.drawer-extra > div {
  padding: 0 18px 18px;
}
.guided-editor :deep(.compact-notes > h3) {
  display: none;
}
.guided-editor :deep(.compact-custom-fields) {
  padding: 19px;
  background: #fff;
  border: 1px solid #e6eaf3;
  border-radius: 12px;
  margin-bottom: 18px;
}
.guided-editor :deep(.compact-custom-fields h3) {
  font-size: 15px;
  margin: 0;
  color: #50637e;
}
.guided-editor :deep(.appointments) {
  border: 0;
  padding: 0;
  margin: 0;
}
.guided-editor :deep(.appointments > h3) {
  font-size: 16px;
  margin: 0 0 8px;
}
.guided-editor :deep(.appointments > p) {
  font-size: 11px;
  line-height: 1.7;
  color: #8d9db2;
}
.guided-editor :deep(.friendly-slot) {
  display: grid !important;
  grid-template-columns: 1fr 1fr;
  gap: 15px !important;
}
.guided-editor :deep(.friendly-slot > label:first-child) {
  grid-column: 1/-1;
}
.guided-editor :deep(.friendly-slot > label) {
  flex: none !important;
}
.guided-editor :deep(.appointment-actions) {
  gap: 8px;
}
.guided-editor :deep(.appointment-actions button) {
  font-size: 10px;
}
.guided-editor :deep(.compact-custom-fields input[type='checkbox']) {
  width: 16px;
}
.drawer-feedback {
  padding: 12px 14px;
  border-radius: 9px;
  font-size: 12px;
  margin: 0 0 18px;
  line-height: 1.6;
}
.drawer-error {
  background: #fff1ef;
  color: #b16d64;
}
.drawer-access {
  padding: 12px 14px;
  background: #fff6e9;
  border-radius: 10px;
  margin-bottom: 18px;
  font-size: 12px;
  color: #ac9269;
}
.drawer-access p {
  margin: 0 0 8px;
}
.drawer-actions {
  flex-shrink: 0;
  padding: 14px 24px 20px;
  background: #fff;
  border-top: 1px solid #e4eaf3;
  box-shadow: 0 -8px 22px #2f4c7b04;
}
.drawer-save-state {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 10px;
  color: #8aa095;
  margin-bottom: 12px;
  min-height: 16px;
}
.drawer-save-state svg {
  color: #8bb89e;
}
.drawer-action-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.drawer-unsaved {
  padding: 12px;
  background: #fff7e9;
  border-radius: 9px;
  margin-bottom: 13px;
  color: #9c8054;
}
.drawer-unsaved p {
  font-size: 11px;
  line-height: 1.6;
  margin: 0 0 9px;
}
.drawer-discard {
  font-size: 11px;
  color: #a66f64;
  border: 0;
  background: none;
  padding: 8px;
  cursor: pointer;
}
.save-spinner {
  animation: drawer-spin 1s linear infinite;
}
.guided-editor button:focus-visible,
.drawer-extra summary:focus-visible {
  outline: 3px solid #b0caf6;
  outline-offset: 3px;
}
@keyframes drawer-spin {
  to {
    transform: rotate(360deg);
  }
}
@media (max-width: 500px) {
  .drawer-tabs {
    padding: 10px;
    gap: 2px;
  }
  .drawer-tabs button {
    font-size: 10px;
    gap: 5px;
    padding: 10px 5px;
  }
  .drawer-tabs svg {
    width: 15px;
  }
  .drawer-scroll {
    padding: 18px 16px;
  }
  .drawer-actions {
    padding: 12px 16px 16px;
  }
  .guided-editor .drawer-action-row button {
    font-size: 11px;
    padding: 10px 12px;
  }
  .drawer-call-card {
    padding: 14px;
  }
  .call-number small {
    font-size: 7px !important;
  }
  .call-number strong {
    font-size: 14px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .save-spinner {
    animation: none;
  }
}
.guided-editor .drawer-call-card {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  min-height: 80px;
  margin-bottom: 22px;
}
.drawer-call-card .call-number {
  flex: 1;
  min-width: 180px;
}
.drawer-call-card :deep(.call-action) {
  margin: 0;
  padding: 0;
  border: 0;
}
.drawer-call-card:has(.call-confirm) :deep(.call-action),
.drawer-call-card:has(.call-action > p) :deep(.call-action),
.drawer-call-card:has(.call-action > small) :deep(.call-action) {
  flex-basis: 100%;
  padding-top: 10px;
  border-top: 1px solid #dbede2;
}
.drawer-status-saved {
  font-size: 11px;
  color: #71a284;
  margin: 0;
}
.guided-editor :deep(.compact-documents > h3) {
  display: none;
}
.drawer-save-state svg.save-pending {
  color: #b29a77;
}
</style>
