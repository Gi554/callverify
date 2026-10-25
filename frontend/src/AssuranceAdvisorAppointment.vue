<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { CalendarDays, Check, FilePenLine, Phone, Save, UserRound } from 'lucide-vue-next';
import AssuranceQualificationSnapshot from './AssuranceQualificationSnapshot.vue';

const props = defineProps<{
  appointmentId: number;
  request: (path: string, body?: any, method?: string) => Promise<any>;
}>();
const emit = defineEmits<{ busy: [value: boolean]; updated: [row: any] }>();
const tab = ref('result'),
  busy = ref(false),
  error = ref(''),
  success = ref('');
const appointment = ref<any>(null),
  report = ref<any>(null),
  client = ref<any>(null);
const clientError = ref(''),
  fields = ref<any[]>([]),
  clientBase = ref(''),
  resultBase = ref('');
const resultReady = ref(false);
const performed = ref(''),
  sale = ref(''),
  problem = ref(false),
  note = ref(''),
  reason = ref('');
const resultDraft = computed(() =>
  JSON.stringify({
    performed: performed.value,
    sale: sale.value,
    problem: problem.value,
    note: note.value,
  }),
);
const clientDraft = computed(() =>
  client.value
    ? JSON.stringify({
        name: client.value.name,
        phone: client.value.phone,
        email: client.value.email,
        qualification: client.value.qualification,
      })
    : '',
);
const dirty = computed(
  () => resultDraft.value !== resultBase.value || clientDraft.value !== clientBase.value,
);
const canReport = computed(
  () =>
    resultReady.value &&
    appointment.value?.status === 'scheduled' &&
    new Date(appointment.value.ends_at).getTime() <= Date.now(),
);
const base = computed(() => `/appointments/${props.appointmentId}`);
function working(value: boolean) {
  busy.value = value;
  emit('busy', value);
}
function close() {
  return (
    !busy.value &&
    (!dirty.value || window.confirm('Abandonner les modifications non enregistrées ?'))
  );
}
defineExpose({ close });
function setReport(value: any) {
  report.value = value;
  performed.value = value ? String(value.performed) : '';
  sale.value = value?.sale_concluded == null ? '' : String(value.sale_concluded);
  problem.value = value?.problem || false;
  note.value = value?.note || '';
  reason.value = '';
  resultBase.value = resultDraft.value;
}
async function load() {
  working(true);
  error.value = '';
  success.value = '';
  clientError.value = '';
  client.value = null;
  clientBase.value = '';
  resultReady.value = false;
  resultBase.value = resultDraft.value;
  try {
    appointment.value = await props.request(`${base.value}/`);
    setReport((await props.request(`${base.value}/advisor-result/`)).result);
    resultReady.value = true;
    try {
      const data = await props.request(`${base.value}/client-record/`);
      fields.value = data.fields;
      client.value = { ...data, qualification: { ...data.qualification } };
      clientBase.value = clientDraft.value;
    } catch (e: any) {
      clientError.value = e.message;
    }
  } catch (e: any) {
    error.value = e.message;
  } finally {
    working(false);
  }
}
async function reload() {
  if (close()) await load();
}
async function saveResult() {
  if (busy.value || !canReport.value || !performed.value || !sale.value) return;
  working(true);
  error.value = '';
  success.value = '';
  try {
    const data = await props.request(`${base.value}/advisor-result/`, {
      revision: appointment.value.revision,
      performed: performed.value === 'true',
      outcome:
        performed.value === 'true'
          ? 'performed'
          : report.value?.performed === false
            ? report.value.outcome || 'not_performed'
            : 'absent',
      sale_concluded: sale.value === 'true',
      problem: problem.value,
      note: note.value,
      reason: reason.value,
    });
    appointment.value = data.appointment || { ...appointment.value, revision: data.revision };
    setReport(data.result);
    emit('updated', appointment.value);
    success.value = 'Résultat du rendez-vous enregistré.';
  } catch (e: any) {
    error.value = e.message;
  } finally {
    working(false);
  }
}
async function saveClient() {
  if (busy.value) return;
  working(true);
  error.value = '';
  success.value = '';
  try {
    const draft = JSON.parse(clientDraft.value);
    if (draft.qualification.age === '') draft.qualification.age = null;
    const data = await props.request(`${base.value}/client-record/`, {
      ...draft,
      revision: client.value.revision,
    });
    client.value = { ...data, qualification: { ...data.qualification } };
    clientBase.value = clientDraft.value;
    appointment.value = {
      ...appointment.value,
      contact: {
        ...appointment.value.contact,
        name: data.name,
        phone: data.phone,
        email: data.email,
      },
    };
    emit('updated', appointment.value);
    success.value = 'Fiche client mise à jour.';
  } catch (e: any) {
    error.value = e.message;
  } finally {
    working(false);
  }
}
function stamp(value: string) {
  return new Intl.DateTimeFormat('fr-CA', {
    dateStyle: 'long',
    timeStyle: 'short',
    timeZone: appointment.value?.timezone || 'America/Toronto',
  }).format(new Date(value));
}
function toggle(key: string, option: string, checked: boolean) {
  let values = [...(client.value.qualification[key] || [])];
  values = checked
    ? [...values.filter((value) => value !== option), option]
    : values.filter((value) => value !== option);
  if (checked)
    values = option === 'none_known' ? [option] : values.filter((value) => value !== 'none_known');
  client.value.qualification[key] = values;
}
onMounted(load);
</script>

<template>
  <section class="advisor-detail" :aria-busy="busy">
    <div v-if="appointment" class="advisor-summary">
      <span class="summary-icon"><CalendarDays :size="24" /></span>
      <div>
        <strong>{{ stamp(appointment.starts_at) }}</strong>
        <small>{{ appointment.timezone }} · {{ appointment.advisor.name }}</small>
        <span><Phone :size="13" /> {{ appointment.contact.phone }}</span>
      </div>
    </div>
    <nav aria-label="Dossier du rendez-vous" class="advisor-tabs">
      <button :class="{ active: tab === 'result' }" @click="tab = 'result'">
        <Check :size="16" />Résultat
      </button>
      <button :class="{ active: tab === 'client' }" @click="tab = 'client'">
        <UserRound :size="16" />Fiche client
      </button>
      <button :class="{ active: tab === 'snapshot' }" @click="tab = 'snapshot'">
        <FilePenLine :size="16" />Qualification reçue
      </button>
    </nav>
    <div v-if="appointment?.calendar === 'calendly'" class="advisor-info">
      <p v-if="appointment.calendly?.conflict || appointment.calendly?.needs_review" role="alert">
        Une mise à jour Calendly nécessite une vérification avec l’administration.
      </p>
      <a
        v-if="appointment.calendly?.reschedule_url && appointment.status === 'scheduled'"
        :href="appointment.calendly.reschedule_url"
        target="_blank"
        rel="noopener noreferrer"
        >Reporter sur Calendly</a
      >
      <span> · </span
      ><a
        v-if="appointment.calendly?.cancel_url && appointment.status === 'scheduled'"
        :href="appointment.calendly.cancel_url"
        target="_blank"
        rel="noopener noreferrer"
        >Annuler sur Calendly</a
      >
    </div>
    <p v-if="error" role="alert" class="advisor-error">
      {{ error }} <button :disabled="busy" @click="reload">Recharger le dossier</button>
    </p>
    <p v-if="success" role="status" class="advisor-success">{{ success }}</p>
    <p v-if="busy && !appointment" role="status">Chargement du rendez-vous…</p>
    <div v-if="appointment" v-show="tab === 'result'">
      <header class="advisor-section-title">
        <h3>Comment s’est passé le rendez-vous ?</h3>
        <p>Deux réponses pour suivre la présence et la conclusion commerciale.</p>
      </header>
      <p v-if="!canReport" class="advisor-info">
        {{
          appointment.status === 'cancelled'
            ? 'Ce rendez-vous est annulé.'
            : 'Le résultat pourra être renseigné après la fin du rendez-vous.'
        }}
      </p>
      <form @submit.prevent="saveResult">
        <fieldset :disabled="busy || !canReport" class="advisor-result-form">
          <fieldset class="answer-group">
            <legend>Le client s’est-il présenté ?</legend>
            <label :class="{ chosen: performed === 'true' }"
              ><input
                v-model="performed"
                type="radio"
                value="true"
                name="attendance"
                required
              />Oui, rendez-vous tenu</label
            >
            <label :class="{ chosen: performed === 'false' }"
              ><input
                v-model="performed"
                type="radio"
                value="false"
                name="attendance"
                required
              />Non, client absent</label
            >
          </fieldset>
          <fieldset class="answer-group">
            <legend>Une vente ou un contrat a-t-il été conclu ?</legend>
            <label :class="{ chosen: sale === 'true' }"
              ><input v-model="sale" type="radio" value="true" name="sale" required />Oui</label
            >
            <label :class="{ chosen: sale === 'false' }"
              ><input v-model="sale" type="radio" value="false" name="sale" required />Non</label
            >
            <small v-if="report && report.sale_concluded == null"
              >Vente non renseignée dans l’ancien compte rendu.</small
            >
          </fieldset>
          <label class="advisor-field"
            >Note du rendez-vous<textarea
              v-model="note"
              rows="4"
              maxlength="3000"
              :required="performed === 'false' || problem"
              placeholder="Besoins évoqués, décision du client, suite à donner…"
            ></textarea
            ><small>Motif requis en cas d’absence ou de suivi nécessaire.</small></label
          >
          <label class="advisor-check"
            ><input v-model="problem" type="checkbox" />Un suivi par le setter est nécessaire</label
          >
          <label v-if="report" class="advisor-field"
            >Motif de la correction<input
              v-model="reason"
              maxlength="1000"
              required
              placeholder="Pourquoi modifier le résultat précédent ?"
          /></label>
          <p class="advisor-info">
            La vente déclarée ne crée pas automatiquement un contrat. Une correction conserve une
            trace ; une tâche de suivi déjà ouverte reste à traiter.
          </p>
          <button
            class="advisor-save"
            type="submit"
            :disabled="
              !performed ||
              !sale ||
              (sale === 'true' && performed !== 'true') ||
              resultDraft === resultBase
            "
          >
            <Save :size="16" />{{
              report ? 'Enregistrer la correction' : 'Enregistrer le résultat'
            }}
          </button>
          <p v-if="sale === 'true' && performed !== 'true'" class="advisor-error">
            Une vente exige un rendez-vous tenu.
          </p>
        </fieldset>
      </form>
    </div>
    <div v-show="tab === 'client'">
      <header class="advisor-section-title">
        <h3>Les informations du client</h3>
        <p>
          Modifiez la fiche attribuée. La qualification reçue lors de la réservation reste
          conservée.
        </p>
      </header>
      <p v-if="clientError" role="alert" class="advisor-error">{{ clientError }}</p>
      <form v-if="client" @submit.prevent="saveClient">
        <fieldset :disabled="busy" class="advisor-client-form">
          <label class="advisor-field wide"
            >Nom et prénom<input v-model="client.name" required maxlength="250"
          /></label>
          <label class="advisor-field"
            >Téléphone<input v-model="client.phone" required maxlength="250"
          /></label>
          <label class="advisor-field"
            >Courriel<input v-model="client.email" maxlength="254"
          /></label>
          <template v-for="field in fields" :key="field.key">
            <label
              v-if="field.type !== 'multiple'"
              class="advisor-field"
              :class="{ wide: field.type === 'text' }"
              >{{ field.label }}
              <input
                v-if="field.type === 'number'"
                v-model="client.qualification[field.key]"
                type="number"
                :min="field.min"
                :max="field.max"
              />
              <select
                v-else-if="field.type === 'boolean'"
                v-model="client.qualification[field.key]"
              >
                <option :value="null">Non renseigné</option>
                <option :value="true">Oui</option>
                <option :value="false">Non</option>
              </select>
              <select v-else-if="field.type === 'choice'" v-model="client.qualification[field.key]">
                <option value="">Non renseigné</option>
                <option v-for="(label, value) in field.choices" :key="value" :value="value">
                  {{ label }}
                </option>
              </select>
              <textarea
                v-else
                v-model="client.qualification[field.key]"
                rows="3"
                maxlength="3000"
              ></textarea>
            </label>
            <fieldset v-else class="advisor-insurances wide">
              <legend>{{ field.label }}</legend>
              <label v-for="(label, value) in field.choices" :key="value" class="advisor-check"
                ><input
                  type="checkbox"
                  :checked="(client.qualification[field.key] || []).includes(value)"
                  @change="
                    toggle(field.key, String(value), ($event.target as HTMLInputElement).checked)
                  "
                />{{ label }}</label
              >
            </fieldset>
          </template>
          <button class="advisor-save wide" type="submit" :disabled="clientDraft === clientBase">
            <Save :size="16" />Enregistrer la fiche client
          </button>
        </fieldset>
      </form>
    </div>
    <div v-if="appointment" v-show="tab === 'snapshot'">
      <header class="advisor-section-title">
        <h3>Qualification transmise par le setter</h3>
        <p>Copie conservée au moment de la réservation, en lecture seule.</p>
      </header>
      <AssuranceQualificationSnapshot :snapshot="appointment.qualification_snapshot" />
    </div>
  </section>
</template>

<style scoped>
.advisor-detail {
  color: #24344e;
}
.advisor-detail .advisor-summary {
  display: flex;
  gap: 14px;
  padding: 20px;
  background: linear-gradient(120deg, #eef3ff, #f5f0ff);
  border-radius: 16px;
  margin-bottom: 20px;
}
.advisor-detail .summary-icon {
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  border-radius: 13px;
  background: #fff;
  color: #6552d9;
  flex-shrink: 0;
}
.advisor-detail .advisor-summary strong,
.advisor-detail .advisor-summary small,
.advisor-detail .advisor-summary span:not(.summary-icon) {
  display: block;
}
.advisor-detail .advisor-summary small {
  margin: 5px 0 9px;
  color: #66758e;
}
.advisor-detail .advisor-tabs {
  display: flex;
  gap: 5px;
  border-bottom: 1px solid #e4e9f2;
  margin-bottom: 24px;
  flex-wrap: wrap;
}
.advisor-detail .advisor-tabs button {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 10px;
  border: 0;
  border-radius: 8px 8px 0 0;
  background: transparent;
  color: #66758e;
}
.advisor-detail .advisor-tabs button.active {
  background: #edf3ff;
  color: #155bdb;
  box-shadow: inset 0 -3px #326ef0;
}
.advisor-detail .advisor-section-title h3 {
  margin: 0 0 7px;
  font-size: 18px;
}
.advisor-detail .advisor-section-title p {
  color: #718099;
  line-height: 1.6;
  margin-bottom: 22px;
}
.advisor-detail .advisor-result-form,
.advisor-detail .advisor-client-form {
  padding: 0;
  border: 0;
  min-width: 0;
}
.advisor-detail .advisor-result-form {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0;
}
.advisor-detail .advisor-client-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}
.advisor-detail .wide {
  grid-column: 1/-1;
}
.advisor-detail .answer-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  border: 1px solid #e1e7f1;
  border-radius: 13px;
  padding: 16px;
  margin: 0 0 20px;
}
.advisor-detail .answer-group legend {
  font-weight: 650;
  padding: 0 6px;
}
.advisor-detail .answer-group label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  margin: 0;
  flex: 1;
  min-width: 170px;
  border: 1px solid #e4e9f2;
  border-radius: 9px;
  cursor: pointer;
}
.advisor-detail .answer-group label.chosen {
  border-color: #7966df;
  background: #f1edff;
  color: #5140b2;
}
.advisor-detail .answer-group small {
  display: block;
  padding: 8px;
  color: #8b6526;
}
.advisor-detail .advisor-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 17px;
  font-weight: 550;
}
.advisor-detail .advisor-field input,
.advisor-detail .advisor-field select,
.advisor-detail .advisor-field textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 12px;
  border: 1px solid #dbe2ef;
  border-radius: 9px;
  background: #fff;
  color: #24344e;
  font: inherit;
}
.advisor-detail .advisor-field small {
  font-weight: 400;
  color: #718099;
}
.advisor-detail .advisor-check {
  display: flex;
  align-items: center;
  gap: 9px;
  margin: 12px 0;
}
.advisor-detail .advisor-check input,
.advisor-detail .answer-group input {
  accent-color: #6351cf;
  width: 16px;
  height: 16px;
}
.advisor-detail .advisor-insurances {
  border: 1px solid #e1e7f1;
  border-radius: 12px;
  padding: 16px;
}
.advisor-detail .advisor-info {
  background: #f5f7fc;
  color: #65758e;
  padding: 12px 15px;
  border-radius: 10px;
  line-height: 1.6;
  font-size: 12px;
}
.advisor-detail .advisor-save {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 9px;
  padding: 13px 20px;
  border: 0;
  border-radius: 10px;
  background: #346bea;
  color: #fff;
  font-weight: 650;
  cursor: pointer;
  width: 100%;
  margin-top: 10px;
}
.advisor-detail .advisor-save:disabled {
  opacity: 0.45;
  cursor: default;
}
.advisor-detail .advisor-error,
.advisor-detail .advisor-success {
  padding: 12px;
  border-radius: 9px;
  line-height: 1.6;
}
.advisor-detail .advisor-error {
  color: #a2373c;
  background: #fff0f1;
}
.advisor-detail .advisor-success {
  color: #24775b;
  background: #eaf8f1;
}
@media (max-width: 600px) {
  .advisor-client-form {
    grid-template-columns: 1fr;
  }
}
</style>
