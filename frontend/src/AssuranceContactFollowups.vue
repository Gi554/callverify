<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import { bookingInterval } from './booking-time';
import { Phone, Plus, CheckCircle2 } from 'lucide-vue-next';
const props = defineProps<{
  contactId: number;
  revision: number;
  token: string;
  blocked?: boolean;
  request: (path: string, body?: any, method?: string) => Promise<any>;
  prepare: () => Promise<void>;
}>();
const emit = defineEmits<{
  busy: [value: boolean];
  dirty: [value: boolean];
  saved: [];
  qualify: [];
  review: [];
}>();
const result = ref(''),
  note = ref(''),
  due = ref(''),
  manual = ref(false),
  taskNote = ref(''),
  taskDue = ref(''),
  priority = ref('normal'),
  busy = ref(false),
  error = ref(''),
  message = ref(''),
  outcomes = ref<any[]>([]),
  tasks = ref<any[]>([]),
  outcomeCount = ref(0),
  taskCount = ref(0),
  outcomePage = ref(1),
  taskPage = ref(1),
  pendingAppointment = ref<number | null>(null);
const labels: Record<string, string> = {
  appointment_booked: 'Rendez-vous pris',
  voicemail: 'Répondeur',
  invalid_number: 'Numéro invalide',
  disconnected: 'Appel coupé',
  not_interested: 'Pas intéressé',
  callback: 'A demandé à être rappelé',
  unreachable: 'Injoignable',
};
let outcomeId = crypto.randomUUID(),
  taskId = crypto.randomUUID();
const dirty = computed(
  () =>
    !!result.value ||
    !!note.value.trim() ||
    !!due.value ||
    (manual.value && (!!taskNote.value.trim() || !!taskDue.value)),
);
watch(dirty, (value) => emit('dirty', value), { immediate: true });
watch(busy, (value) => emit('busy', value), { flush: 'sync' });
function changed() {
  outcomeId = crypto.randomUUID();
  message.value = '';
  pendingAppointment.value = null;
  if (result.value === 'appointment_booked') emit('qualify');
}
function outcomeEdited() {
  outcomeId = crypto.randomUUID();
}
function taskChanged() {
  taskId = crypto.randomUUID();
  message.value = '';
}
function date(value: string) {
  return new Intl.DateTimeFormat('fr-FR', {
    timeZone: 'America/Toronto',
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}
async function load() {
  const [calls, followups] = await Promise.all([
    props.request(`contacts/${props.contactId}/call-outcomes/?page=${outcomePage.value}`),
    props.request(`contacts/${props.contactId}/follow-ups/?page=${taskPage.value}`),
  ]);
  outcomes.value = calls.results;
  outcomeCount.value = calls.count;
  tasks.value = followups.results;
  taskCount.value = followups.count;
}
async function run(action: () => Promise<void>) {
  if (busy.value) return;
  busy.value = true;
  error.value = '';
  try {
    await action();
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function record(appointmentId?: number) {
  await run(async () => {
    await props.prepare();
    const body: any = {
      token: props.token,
      contact_revision: props.revision,
      request_id: outcomeId,
      result: result.value,
      note: note.value,
    };
    if (result.value === 'callback')
      body.due_at = bookingInterval(due.value, 'America/Toronto', 30).starts_at;
    if (result.value === 'appointment_booked')
      body.appointment_id = appointmentId || pendingAppointment.value;
    await props.request(`contacts/${props.contactId}/call-outcomes/`, body);
    result.value = '';
    note.value = '';
    due.value = '';
    pendingAppointment.value = null;
    outcomeId = crypto.randomUUID();
    outcomePage.value = 1;
    taskPage.value = 1;
    message.value = 'Résultat enregistré dans l’historique du contact.';
    emit('saved');
    await load();
  });
}
async function booked(row: any) {
  if (result.value !== 'appointment_booked') return;
  pendingAppointment.value = row.id;
  await record(row.id);
  if (result.value === 'appointment_booked') emit('review');
}
async function createTask() {
  await run(async () => {
    await props.prepare();
    await props.request(`contacts/${props.contactId}/follow-ups/`, {
      token: props.token,
      contact_revision: props.revision,
      request_id: taskId,
      due_at: bookingInterval(taskDue.value, 'America/Toronto', 30).starts_at,
      reason: taskNote.value,
      priority: priority.value,
    });
    manual.value = false;
    taskNote.value = '';
    taskDue.value = '';
    taskId = crypto.randomUUID();
    taskPage.value = 1;
    message.value = 'Rappel enregistré dans vos tâches.';
    emit('saved');
    await load();
  });
}
async function refresh() {
  await run(load);
}
defineExpose({ booked });
onMounted(refresh);
</script>
<template>
  <section class="contact-followups">
    <header>
      <span class="outcome-symbol"><Phone :size="19" /></span>
      <div>
        <h3>Résultat de l’échange</h3>
        <p>Ce que vous avez constaté pendant votre appel.</p>
      </div>
    </header>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="message" role="status" class="outcome-success">
      <CheckCircle2 :size="15" />{{ message }}
    </p>
    <form @submit.prevent="record()">
      <fieldset :disabled="busy || blocked || !token">
        <label
          >Résultat de l’appel<select v-model="result" required @change="changed">
            <option value="">Choisir le résultat</option>
            <option v-for="(label, key) in labels" :key="key" :value="key">{{ label }}</option>
          </select></label
        ><label
          >Note complémentaire<textarea
            v-model="note"
            maxlength="3000"
            placeholder="Quelques mots pour garder le contexte…"
            @input="outcomeEdited"
          ></textarea></label
        ><label v-if="result === 'callback'"
          >Date et heure du rappel · Montréal<input
            v-model="due"
            type="datetime-local"
            required
            @input="outcomeEdited"
        /></label>
        <p v-if="result === 'appointment_booked'" class="outcome-hint">
          Complétez la qualification, puis réservez dans l’onglet Rendez-vous. Le résultat sera
          enregistré après la réservation.
        </p>
        <button
          v-if="result !== 'appointment_booked' || pendingAppointment"
          class="primary"
          :disabled="!result"
        >
          {{
            result === 'callback' ? 'Enregistrer et créer le rappel' : 'Enregistrer le résultat'
          }}</button
        ><button v-else type="button" class="secondary" @click="emit('qualify')">
          Compléter la qualification
        </button>
      </fieldset>
    </form>
    <button
      class="secondary manual-task-toggle"
      :disabled="busy || blocked || !token"
      @click="manual = !manual"
    >
      <Plus :size="15" />Créer un rappel manuellement
    </button>
    <form v-if="manual" @submit.prevent="createTask" @input="taskChanged" @change="taskChanged">
      <fieldset :disabled="busy || blocked || !token">
        <h3>Un rappel pour ce contact</h3>
        <label
          >Date et heure · Montréal<input v-model="taskDue" type="datetime-local" required /></label
        ><label
          >Note du rappel<textarea
            v-model="taskNote"
            required
            maxlength="3000"
            placeholder="Que faudra-t-il faire ?"
          ></textarea></label
        ><label
          >Priorité<select v-model="priority">
            <option value="low">Basse</option>
            <option value="normal">Normale</option>
            <option value="high">Haute</option>
            <option value="urgent">Urgente</option>
          </select></label
        ><button class="primary">Créer le rappel</button>
      </fieldset>
    </form>
    <details>
      <summary>Résultats d’appels et rappels du contact</summary>
      <p>
        Déclarations du setter. « Numéro invalide » ne modifie pas le résultat technique Lookup.
      </p>
      <button class="secondary" :disabled="busy" @click="refresh">Actualiser</button>
      <h4>Résultats d’appels</h4>
      <div v-for="row in outcomes" :key="row.id" class="outcome-entry">
        <strong>{{ row.label }}</strong
        ><time>{{ date(row.created_at) }} · Montréal</time>
        <p>{{ row.note }}</p>
        <small v-if="row.task_id">Rappel #{{ row.task_id }}</small
        ><small v-if="row.appointment_id">Rendez-vous #{{ row.appointment_id }}</small>
      </div>
      <p v-if="!outcomes.length">Aucun résultat enregistré.</p>
      <div class="outcome-pages">
        <button
          class="secondary"
          :disabled="busy || outcomePage === 1"
          @click="
            outcomePage--;
            refresh();
          "
        >
          Précédent</button
        ><span>{{ outcomeCount }} résultat(s) · page {{ outcomePage }}</span
        ><button
          class="secondary"
          :disabled="busy || outcomePage * 25 >= outcomeCount"
          @click="
            outcomePage++;
            refresh();
          "
        >
          Suivant
        </button>
      </div>
      <h4>Rappels et suivis</h4>
      <div v-for="row in tasks" :key="row.id" class="outcome-entry">
        <strong>{{ row.closed_at ? 'Terminé' : row.overdue ? 'En retard' : 'À venir' }}</strong
        ><time>{{ date(row.due_at) }} · Montréal</time>
        <p>{{ row.reason }}</p>
        <p v-if="row.closed_at">Résolution : {{ row.resolution }}</p>
      </div>
      <p v-if="!tasks.length">Aucun rappel enregistré.</p>
      <div class="outcome-pages">
        <button
          class="secondary"
          :disabled="busy || taskPage === 1"
          @click="
            taskPage--;
            refresh();
          "
        >
          Précédent</button
        ><span>{{ taskCount }} suivi(s) · page {{ taskPage }}</span
        ><button
          class="secondary"
          :disabled="busy || taskPage * 25 >= taskCount"
          @click="
            taskPage++;
            refresh();
          "
        >
          Suivant
        </button>
      </div>
    </details>
  </section>
</template>
<style scoped>
.contact-followups {
  margin: 20px 0;
  padding: 20px;
  background: #fff;
  border: 1px solid #e3eaf5;
  border-radius: 15px;
  color: #667d98;
}
.contact-followups > header {
  display: flex;
  gap: 12px;
  align-items: center;
}
.outcome-symbol {
  display: grid;
  place-items: center;
  background: #edf5f1;
  color: #64a28d;
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border-radius: 12px;
}
.contact-followups h3 {
  font-size: 15px !important;
  margin: 0 0 6px;
  color: #567391;
}
.contact-followups header p {
  font-size: 11px;
  margin: 0;
  color: #8b9bb0;
}
.contact-followups form {
  margin: 20px 0 !important;
}
.contact-followups fieldset {
  display: grid !important;
  gap: 15px;
  border: 0;
  padding: 0;
  margin: 0;
  min-width: 0;
}
.contact-followups label {
  display: grid;
  gap: 8px;
  font-size: 12px;
}
.contact-followups input,
.contact-followups select,
.contact-followups textarea {
  width: 100%;
  box-sizing: border-box;
}
.contact-followups .outcome-hint {
  font-size: 12px;
  background: #f2edfb;
  color: #8c76ac;
  padding: 14px;
  border-radius: 10px;
  line-height: 1.8;
}
.manual-task-toggle {
  width: 100%;
}
.outcome-success {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #edf7f0;
  color: #78a08b;
  padding: 13px;
  border-radius: 9px;
  font-size: 12px;
}
.outcome-entry {
  padding: 14px 0;
  border-bottom: 1px solid #e9eef5;
  font-size: 12px;
}
.outcome-entry time {
  display: block;
  font-size: 10px;
  color: #94a4b9;
  margin-top: 7px;
}
.outcome-entry p {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.8;
}
.outcome-pages {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 10px;
  margin: 12px 0;
}
.outcome-pages button {
  font-size: 10px !important;
}
.contact-followups details {
  margin-top: 20px;
  font-size: 12px;
  line-height: 1.8;
}
</style>
