<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue';
import { bookingInterval } from './booking-time';
import { CALENDLY_ZONE, montrealISO } from './calendly-time';
const props = defineProps<{
  role: string;
  contactId: number;
  contactRevision?: number;
  leaseToken: string;
  blocked?: boolean;
  beforeBook?: () => Promise<void>;
  request: (path: string, body?: any) => Promise<any>;
  portal: (path: string, body?: any) => Promise<any>;
}>();
const emit = defineEmits<{ booked: [row: any]; busy: [value: boolean] }>();
const choices = ref<any[]>([]),
  assignment = ref(''),
  page = ref(1),
  total = ref(0);
const date = ref(montrealISO(Date.now() + 86400000).slice(0, 10));
const slots = ref<string[]>([]),
  selected = ref(''),
  eventType = ref(''),
  duration = ref(30);
const busy = ref(false),
  error = ref(''),
  message = ref(''),
  pending = ref(false),
  submitted = ref<any>(null);
let requestId = crypto.randomUUID();
const show = (value: string) =>
  new Intl.DateTimeFormat('fr-CA', {
    timeZone: CALENDLY_ZONE,
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
async function run(action: () => Promise<void>) {
  if (busy.value) return;
  busy.value = true;
  emit('busy', true);
  error.value = '';
  try {
    await action();
  } catch (e: any) {
    error.value = e.message;
    try {
      const value = await props.request(`calendly/pending/?contact_id=${props.contactId}`);
      pending.value = !!value.request_id;
      if (value.request_id) requestId = value.request_id;
      else submitted.value = null;
    } catch {
      /* Preserve pending intent if the connection itself is unavailable. */
    }
  } finally {
    busy.value = false;
    emit('busy', false);
  }
}
async function loadChoices() {
  const data = await props.request(`assignments/?active=true&page=${page.value}`);
  choices.value = data.results;
  total.value = data.count;
  assignment.value = '';
  slots.value = [];
  selected.value = '';
}
async function loadSlots() {
  slots.value = [];
  selected.value = '';
  message.value = '';
  const first = new Date(bookingInterval(date.value + 'T00:00', CALENDLY_ZONE, 30).starts_at);
  const next = new Date(date.value + 'T12:00:00Z');
  next.setUTCDate(next.getUTCDate() + 1);
  const last = bookingInterval(
    next.toISOString().slice(0, 10) + 'T00:00',
    CALENDLY_ZONE,
    30,
  ).starts_at;
  const query = new URLSearchParams({
    assignment_id: assignment.value,
    contact_id: String(props.contactId),
    start: new Date(Math.max(first.getTime(), Date.now() + 60000)).toISOString(),
    end: last,
  });
  const data = await props.request(`calendly/slots/?${query}`);
  slots.value = data.slots;
  eventType.value = data.uri;
  duration.value = data.duration;
  if (!slots.value.length)
    message.value = 'Aucun créneau Calendly disponible ce jour. Choisissez une autre date.';
}
async function book() {
  await run(async () => {
    let row: any;
    if (pending.value) {
      row = await props.request('calendly/pending/', { request_id: requestId });
    } else {
      if (!submitted.value) {
        const choice = choices.value.find((row) => String(row.id) === assignment.value);
        if (!choice || !selected.value)
          throw new Error('Choisissez un conseiller et un créneau Calendly.');
        await props.beforeBook?.();
        await nextTick();
        const proof = (
          await props.portal('assurance/booking-proof/', {
            advisor_id: choice.advisor.id,
            ...(props.role === 'administrator' ? { setter_id: choice.setter.id } : {}),
          })
        ).proof;
        submitted.value = {
          contact_id: props.contactId,
          contact_revision: props.contactRevision,
          assignment_id: choice.id,
          request_id: requestId,
          token: props.leaseToken,
          proof,
          event_type: eventType.value,
          starts_at: montrealISO(selected.value),
          ends_at: montrealISO(Date.parse(selected.value) + duration.value * 60000),
          timezone: CALENDLY_ZONE,
        };
      }
      pending.value = true;
      const choice = choices.value.find((row) => row.id === submitted.value.assignment_id);
      // Retry the same business request, with fresh authorization; never create a second booking.
      submitted.value.proof = (
        await props.portal('assurance/booking-proof/', {
          advisor_id: choice.advisor.id,
          ...(props.role === 'administrator' ? { setter_id: choice.setter.id } : {}),
        })
      ).proof;
      row = await props.request('calendly/book/', submitted.value);
    }
    if (row.id) {
      pending.value = false;
      submitted.value = null;
      requestId = crypto.randomUUID();
      emit('booked', row);
      message.value = 'Rendez-vous confirmé par Calendly et enregistré dans Orvia.';
      slots.value = [];
      selected.value = '';
    } else if (row.state === 'rejected') {
      pending.value = false;
      submitted.value = null;
      requestId = crypto.randomUUID();
      throw new Error(
        'Calendly a refusé la réservation. Vérifiez le forfait du conseiller et actualisez les créneaux.',
      );
    } else
      message.value =
        'Confirmation Calendly en attente. Ne créez pas une autre demande : utilisez « Vérifier la réservation ».';
  });
}
onMounted(() =>
  run(async () => {
    await loadChoices();
    const value = await props.request(`calendly/pending/?contact_id=${props.contactId}`);
    if (value.request_id) {
      requestId = value.request_id;
      pending.value = true;
      message.value =
        'Une réservation est déjà en attente pour ce prospect. Vérifiez son état avant une autre demande.';
    }
  }),
);
</script>
<template>
  <section class="calendly-booking" :aria-busy="busy">
    <h3>Réserver avec Calendly</h3>
    <p>Horaires de Montréal · Les changements d’heure sont pris en compte.</p>
    <p v-if="error" role="alert" class="error">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <form @submit.prevent="book">
      <fieldset :disabled="busy || blocked || pending">
        <label
          >Conseiller<select
            v-model="assignment"
            required
            @change="
              slots = [];
              selected = '';
            "
          >
            <option value="">Choisir un conseiller</option>
            <option v-for="row in choices" :key="row.id" :value="String(row.id)">
              {{ role === 'administrator' ? row.setter.name + ' → ' : '' }}{{ row.advisor.name }}
            </option>
          </select></label
        >
        <div v-if="total > 25" class="actions">
          <button
            type="button"
            :disabled="page === 1"
            @click="
              page--;
              run(loadChoices);
            "
          >
            Précédent
          </button>
          <span>Page {{ page }}</span
          ><button
            type="button"
            :disabled="page * 25 >= total"
            @click="
              page++;
              run(loadChoices);
            "
          >
            Suivant
          </button>
        </div>
        <label
          >Date au Québec<input
            v-model="date"
            type="date"
            required
            @change="
              slots = [];
              selected = '';
            "
        /></label>
        <button type="button" :disabled="!assignment || !date" @click="run(loadSlots)">
          Consulter les créneaux Calendly
        </button>
        <label v-if="slots.length"
          >Créneau disponible · {{ duration }} minutes<select v-model="selected" required>
            <option value="">Choisir un créneau</option>
            <option v-for="slot in slots" :key="slot" :value="slot">
              {{ show(slot) }} · {{ montrealISO(slot).slice(-6) }}
            </option>
          </select></label
        >
      </fieldset>
      <button type="submit" :disabled="busy || blocked || (!pending && !selected)">
        {{ pending ? 'Vérifier la réservation' : 'Confirmer sur Calendly' }}
      </button>
    </form>
    <p class="note">
      Le nom et le courriel du prospect sont transmis à Calendly pour sa confirmation. Sa
      qualification reste accessible au conseiller dans Orvia. La réservation directe nécessite un
      forfait Calendly compatible.
    </p>
  </section>
</template>
<style scoped>
.calendly-booking {
  padding: 20px;
  border: 1px solid #dce5f5;
  border-radius: 16px;
  background: #f5f8ff;
}
fieldset {
  border: 0;
  padding: 0;
  margin: 0 0 16px;
  display: grid;
  gap: 14px;
}
label {
  display: grid;
  gap: 7px;
}
select,
input {
  min-height: 42px;
  width: 100%;
}
.actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.note {
  font-size: 12px;
  line-height: 1.6;
  color: #526889;
  margin-top: 18px;
}
.error {
  color: #ad3044;
}
</style>
