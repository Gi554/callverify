<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue';
import { actorNames } from './actor-names';
const names = ref<Record<number, string>>({});
import IsolationCallResult from './IsolationCallResult.vue';
import IsolationFollowUps from './IsolationFollowUps.vue';
import IsolationC2 from './IsolationC2.vue';
import CallAction from './CallAction.vue';
import type { FollowUpReference } from './follow-up';
const tab = ref('call');
const callBusy = ref(false),
  taskBusy = ref(false),
  c2Busy = ref(false),
  callDirty = ref(false),
  taskDirty = ref(false),
  c2Dirty = ref(false);
const props = defineProps<{
  prospectId: number;
  role: string;
  portal: (path: string, body?: any) => Promise<any>;
  request: (path: string, body?: any, method?: string) => Promise<any>;
  // Call session: closing the file moves on to the next prospect.
  session?: boolean;
  followUp?: FollowUpReference;
  taskReadOnly?: boolean;
}>();
const emit = defineEmits<{
  saved: [];
  close: [];
  book: [];
  taskCompleted: [];
  busy: [value: boolean];
}>();
const prospect = ref<any>(null),
  rows = ref<any[]>([]),
  page = ref(1),
  count = ref(0),
  busy = ref(false),
  error = ref(''),
  kind = ref('note'),
  body = ref(''),
  status = ref('in_progress'),
  callback = ref('');
const commandBusy = ref(false);
const statuses: Record<string, string> = {
  to_contact: 'À contacter',
  in_progress: 'En cours',
  callback: 'À rappeler',
  interested: 'Intéressé',
  not_interested: 'Non intéressé',
  unreachable: 'Non joint',
};
let requestId = crypto.randomUUID();
function changed() {
  requestId = crypto.randomUUID();
}
async function load() {
  busy.value = true;
  error.value = '';
  try {
    prospect.value = await props.request(`work-queue/${props.prospectId}/`);
    const data = await props.request(
      `work-queue/${props.prospectId}/activities/?page=${page.value}`,
    );
    rows.value = data.results;
    if (props.role === 'administrator')
      names.value = await actorNames(
        props.portal,
        'isolation',
        data.results.map((row: any) => row.author_portal_id),
      );
    count.value = data.count;
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function callSaved(result: string) {
  if (props.followUp) {
    emit('taskCompleted');
    return;
  }
  await load();
  emit('saved');
  if (
    !error.value &&
    ['voicemail', 'invalid_number', 'disconnected', 'not_interested', 'callback', 'other'].includes(
      result,
    )
  ) {
    await nextTick();
    close();
  }
}
async function refreshContact() {
  prospect.value = await props.request(`work-queue/${props.prospectId}/`);
}
async function prepareTaskCall(id: string) {
  await refreshContact();
  return props.request(`work-queue/${props.prospectId}/call-intent/`, {
    revision: prospect.value.revision,
    request_id: id,
  });
}
async function save() {
  if (!prospect.value) return;
  busy.value = true;
  error.value = '';
  try {
    await props.request(`work-queue/${props.prospectId}/activities/`, {
      request_id: requestId,
      revision: prospect.value.revision,
      kind: kind.value,
      body: body.value,
      ...(kind.value === 'qualification'
        ? { status: status.value, callback_at: status.value === 'callback' ? callback.value : null }
        : {}),
    });
    body.value = '';
    callback.value = '';
    changed();
    page.value = 1;
    await load();
    emit('saved');
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
watch(
  [busy, callBusy, taskBusy, c2Busy, commandBusy],
  () =>
    emit(
      'busy',
      busy.value || callBusy.value || taskBusy.value || c2Busy.value || commandBusy.value,
    ),
  { flush: 'sync' },
);
function canClose() {
  if (busy.value || callBusy.value || taskBusy.value || c2Busy.value || commandBusy.value)
    return false;
  return (
    !(body.value || callback.value || callDirty.value || taskDirty.value || c2Dirty.value) ||
    window.confirm('Quitter sans enregistrer les saisies ?')
  );
}
function close() {
  if (canClose()) emit('close');
}
defineExpose({ close, canClose, reload: load });
onMounted(load);
const activityLabels: Record<string, string> = {
  note: 'Note',
  qualification: 'Qualification',
  call_result: 'Résultat d’appel déclaré',
  callback_created: 'Rappel créé',
  callback_updated: 'Rappel modifié',
  callback_closed: 'Rappel terminé',
};
const resultLabels: Record<string, string> = {
  appointment_booked: 'Rendez-vous pris',
  voicemail: 'Répondeur',
  invalid_number: 'Numéro non attribué',
  disconnected: 'Appel coupé',
  not_interested: 'Pas intéressé',
  callback: 'Rappel demandé',
  other: 'Autre résultat',
  unreachable: 'Injoignable',
};
</script>
<template>
  <section class="isolation-prospect-sheet">
    <p v-if="error" role="alert" class="sheet-error">{{ error }}</p>
    <div v-if="prospect" class="sheet-summary">
      <span>{{ prospect.commercial_label }}</span
      ><small>{{
        prospect.callback_at
          ? 'Rappel : ' +
            new Date(prospect.callback_at).toLocaleString('fr-CA', { timeZone: 'America/Toronto' })
          : 'Aucun rappel programmé'
      }}</small>
    </div>
    <div v-if="followUp && prospect" class="sheet-section">
      <strong>{{ prospect.name || 'Prospect sans nom' }}</strong>
      <p>{{ prospect.phone || prospect.raw_phone || 'Numéro non renseigné' }}</p>
      <CallAction
        v-if="!taskReadOnly"
        workspace="isolation"
        :resource-id="prospectId"
        :phone="prospect.phone || prospect.raw_phone"
        label="Appeler le prospect"
        :portal="portal"
        :prepare="prepareTaskCall"
        :before-open="refreshContact"
        :disabled="busy || callBusy || taskBusy || c2Busy"
        @busy="commandBusy = $event"
      />
    </div>
    <nav class="sheet-tabs" aria-label="Rubriques du prospect">
      <button
        v-for="item in [
          { id: 'call', label: 'Résultat d’appel' },
          { id: 'qualification', label: 'Qualification' },
          { id: 'notes', label: 'Notes et statut' },
          { id: 'tasks', label: 'Rappels' },
          { id: 'history', label: 'Historique' },
        ]"
        :key="item.id"
        :class="{ active: tab === item.id }"
        :aria-pressed="tab === item.id"
        @click="tab = item.id"
      >
        {{ item.label }}
      </button>
    </nav>
    <div v-if="!taskReadOnly" v-show="tab === 'call'" class="sheet-section">
      <IsolationCallResult
        v-if="prospect"
        :prospect="prospect"
        :request="request"
        :follow-up="followUp"
        :blocked="busy || taskBusy || commandBusy"
        @busy="callBusy = $event"
        @dirty="callDirty = $event"
        @saved="callSaved"
        @book="(!followUp || canClose()) && emit('book')"
      />
    </div>
    <div class="sheet-section" v-show="tab === 'qualification'">
      <IsolationC2
        :prospect-id="prospectId"
        :request="request"
        :blocked="busy || callBusy || taskBusy || commandBusy || taskReadOnly"
        @busy="c2Busy = $event"
        @dirty="c2Dirty = $event"
        @saved="
          load();
          emit('saved');
        "
      />
    </div>
    <div class="sheet-section" v-show="tab === 'notes'">
      <form
        v-if="prospect && !taskReadOnly"
        @submit.prevent="save"
        @input="changed"
        @change="changed"
      >
        <fieldset :disabled="busy || callBusy || taskBusy">
          <label
            >Action<select v-model="kind">
              <option value="note">Ajouter une note</option>
              <option value="qualification">Renseigner le résultat commercial</option>
            </select></label
          ><template v-if="kind === 'qualification'"
            ><label
              >Résultat<select v-model="status">
                <option v-for="(label, key) in statuses" :key="key" :value="key">
                  {{ label }}
                </option>
              </select></label
            ><label v-if="status === 'callback'"
              >Rappel ISO 8601 avec décalage (ex. 2026-12-01T10:00:00-05:00)<input
                v-model="callback"
                required
            /></label>
            <p>
              Un résultat autre que « À rappeler » retire le rappel courant, dont la date reste
              conservée dans l’historique.
            </p></template
          ><label
            >Note ou justification<textarea
              v-model="body"
              required
              maxlength="3000"
            ></textarea></label
          ><button class="primary">Enregistrer dans l’historique</button>
        </fieldset>
      </form>
      <button class="secondary" :disabled="busy" @click="load">
        Recharger la fiche et sa version
      </button>
    </div>
    <div class="sheet-section" v-show="tab === 'tasks'">
      <IsolationFollowUps
        :prospect-id="prospectId"
        :request="request"
        :blocked="busy || callBusy || commandBusy || taskReadOnly"
        @busy="taskBusy = $event"
        @dirty="taskDirty = $event"
        @saved="
          load();
          emit('saved');
        "
      />
    </div>
    <div class="sheet-section" v-show="tab === 'history'">
      <h4>Historique des observations</h4>
      <article v-for="row in rows" :key="row.id">
        <small
          >{{ new Date(row.created_at).toLocaleString('fr-CA', { timeZone: 'America/Toronto' }) }} ·
          {{ row.author_role }} {{ names[row.author_portal_id] || 'Compte' }} (n°
          {{ row.author_portal_id }}) · {{ activityLabels[row.kind] || row.kind }}</small
        >
        <p style="white-space: pre-wrap">{{ row.body }}</p>
        <p v-if="row.kind === 'call_result'">
          {{ resultLabels[row.changes.result]
          }}<span v-if="row.changes.task_id"> · Rappel {{ row.changes.task_id }}</span
          ><span v-if="row.changes.appointment_id"> · RDV {{ row.changes.appointment_id }}</span>
        </p>
        <p v-if="row.changes.task_id && row.kind !== 'call_result'">
          Rappel {{ row.changes.task_id }} · {{ row.changes.after?.due_at || row.changes.due_at }}
        </p>
        <p v-if="row.kind === 'qualification' && row.changes.after">
          {{ statuses[row.changes.before.status] || row.changes.before.status }} →
          {{ statuses[row.changes.after.status] || row.changes.after.status }} · Rappel :
          {{
            row.changes.after.callback_at
              ? new Date(row.changes.after.callback_at).toLocaleString('fr-CA', {
                  timeZone: 'America/Toronto',
                })
              : 'Aucun'
          }}
        </p>
        <p v-if="row.kind === 'qualification' && row.changes.before?.callback_at">
          Ancien rappel :
          {{
            new Date(row.changes.before.callback_at).toLocaleString('fr-CA', {
              timeZone: 'America/Toronto',
            })
          }}
        </p>
      </article>
      <p>{{ count }} observation(s) · page {{ page }}</p>
      <button
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
    </div>
    <footer v-if="!followUp" class="sheet-footer">
      <button class="secondary" :disabled="busy || callBusy || taskBusy" @click="close">
        {{ session ? 'Terminer · prospect suivant' : 'Fermer la fiche' }}
      </button>
    </footer>
  </section>
</template>
<style scoped>
.isolation-prospect-sheet {
  color: #35425a;
}
.sheet-summary {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 14px;
  background: #f2f5fc;
  border-radius: 12px;
  margin-bottom: 18px;
}
.sheet-summary span {
  color: #6574ac;
  font-size: 12px;
  font-weight: 650;
}
.sheet-summary small {
  color: #8a91a5;
  font-size: 11px;
}
.sheet-tabs {
  display: flex;
  gap: 6px;
  border-bottom: 1px solid #e9ecf4;
  margin-bottom: 20px;
  overflow-x: auto;
}
.sheet-tabs button {
  white-space: nowrap;
  border: 0;
  background: none;
  color: #8590a4;
  font-size: 12px;
  padding: 12px 10px;
  border-bottom: 3px solid transparent;
  cursor: pointer;
}
.sheet-tabs button.active {
  color: #667cd3;
  border-bottom-color: #899ae8;
}
.sheet-section {
  line-height: 1.65;
}
.sheet-section :deep(h3),
.sheet-section :deep(h4) {
  font-size: 15px;
  color: #43516b;
  margin: 16px 0 12px;
}
.sheet-section :deep(p) {
  font-size: 12px;
  color: #7c879a;
}
.sheet-section :deep(form) {
  display: grid;
  gap: 16px;
}
.sheet-section :deep(fieldset) {
  border: 0;
  padding: 0;
  display: grid;
  gap: 16px;
  min-width: 0;
}
.sheet-section :deep(label) {
  display: grid;
  gap: 7px;
  color: #73809a;
  font-size: 12px;
}
.sheet-section :deep(input),
.sheet-section :deep(select),
.sheet-section :deep(textarea) {
  box-sizing: border-box;
  width: 100%;
  border: 1px solid #e0e6f0;
  border-radius: 9px;
  padding: 11px 12px;
  background: white;
  color: #455673;
  font: inherit;
}
.sheet-section :deep(textarea) {
  min-height: 100px;
}
.sheet-section :deep(article) {
  border: 1px solid #e9edf5;
  background: #fbfcff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
}
.sheet-footer {
  border-top: 1px solid #e9edf4;
  margin-top: 24px;
  padding-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.sheet-error {
  color: #b66e6c;
  background: #fff2ef;
  padding: 12px;
  border-radius: 9px;
}
</style>
