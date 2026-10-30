<script setup lang="ts">
import { computed, onMounted, ref, watch, nextTick } from 'vue';
import { bookingInterval } from './booking-time';
import AssuranceAppointments from './AssuranceAppointments.vue';
const props = defineProps<{
  contactId: number;
  contactRevision: number;
  leaseToken: string;
  role: string;
  blocked?: boolean;
  request: (path: string, body?: any, method?: string) => Promise<any>;
  portal: (path: string, body?: any) => Promise<any>;
  prepare: () => Promise<void>;
  qualification: () => Record<string, any>;
}>();
const emit = defineEmits<{ booked: [row: any]; busy: [value: boolean]; dirty: [value: boolean] }>();
const rows = ref<any[]>([]),
  count = ref(0),
  page = ref(1),
  search = ref(''),
  selected = ref('');
const date = ref(''),
  time = ref(''),
  meeting = ref('video'),
  duration = ref(30),
  confirmed = ref(false);
const busy = ref(false),
  error = ref(''),
  message = ref(''),
  historyVersion = ref(0);
let requestId = crypto.randomUUID();
const advisor = computed(() => rows.value.find((row) => String(row.id) === selected.value));
const draft = computed(() =>
  JSON.stringify([
    selected.value,
    date.value,
    time.value,
    meeting.value,
    duration.value,
    confirmed.value,
  ]),
);
const base = ref(draft.value);
watch(draft, () => {
  requestId = crypto.randomUUID();
  message.value = '';
  emit('dirty', draft.value !== base.value);
});
watch(busy, (value) => emit('busy', value), { flush: 'sync' });
async function load() {
  if (busy.value) return;
  busy.value = true;
  error.value = '';
  try {
    const data = await props.request(
      `assignments/?active=true&page=${page.value}&search=${encodeURIComponent(search.value)}`,
    );
    rows.value = data.results;
    count.value = data.count;
    selected.value = data.count === 1 ? String(data.results[0].id) : '';
    confirmed.value = false;
    await nextTick();
    base.value = draft.value;
    emit('dirty', false);
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function submit() {
  if (busy.value || props.blocked || !props.leaseToken || message.value) return;
  busy.value = true;
  error.value = '';
  message.value = '';
  try {
    const row = advisor.value;
    if (!row?.booking_url || !confirmed.value)
      throw new Error(
        'Réservez dans le lien du conseiller et confirmez la réservation avant l’envoi.',
      );
    await props.prepare();
    await nextTick();
    const proof = (
      await props.portal('assurance/booking-proof/', {
        advisor_id: row.advisor.id,
        ...(props.role === 'administrator' ? { setter_id: row.setter.id } : {}),
      })
    ).proof;
    const saved = await props.request('appointments/transmit/', {
      contact_id: props.contactId,
      contact_revision: props.contactRevision,
      token: props.leaseToken,
      assignment_id: row.id,
      request_id: requestId,
      proof,
      ...bookingInterval(`${date.value}T${time.value}`, 'America/Toronto', duration.value),
      qualification: props.qualification(),
      meeting_type: meeting.value,
      external_confirmed: confirmed.value,
    });
    base.value = draft.value;
    emit('dirty', false);
    emit('booked', saved);
    historyVersion.value++;
    message.value =
      'Rendez-vous et qualification transmis au conseiller. Sa notification est disponible dans Orvia.';
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
onMounted(load);
</script>
<template>
  <section class="transmission">
    <h3>Informations du rendez-vous</h3>
    <p>
      Réservez d’abord dans l’outil du conseiller, puis reportez ici le rendez-vous confirmé.
      Horaires du Québec.
    </p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <form
      @submit.prevent="
        page = 1;
        load();
      "
    >
      <label>Rechercher un conseiller<input v-model="search" :disabled="busy" /></label
      ><button class="secondary" :disabled="busy">Rechercher</button>
    </form>
    <form @submit.prevent="submit">
      <fieldset :disabled="busy || blocked || !leaseToken">
        <label
          >Conseiller destinataire<select v-model="selected" required @change="confirmed = false">
            <option value="">Choisir un conseiller</option>
            <option v-for="row in rows" :key="row.id" :value="String(row.id)">
              {{ row.advisor.name }}{{ role === 'administrator' ? ' · ' + row.setter.name : '' }}
            </option>
          </select></label
        >
        <a
          v-if="advisor?.booking_url"
          :href="advisor.booking_url"
          target="_blank"
          rel="noopener noreferrer"
          >Ouvrir le lien de réservation du conseiller ↗</a
        >
        <p v-else-if="advisor">Ce conseiller n’a pas encore fourni de lien de réservation.</p>
        <label
          >Type de rendez-vous<select v-model="meeting" required>
            <option value="video">Vidéoconférence</option>
            <option value="phone">Appel téléphonique</option>
          </select></label
        >
        <div class="transmission-dates">
          <label>Date<input v-model="date" type="date" required /></label
          ><label>Heure · Québec<input v-model="time" type="time" required /></label
          ><label
            >Durée (minutes)<input
              v-model.number="duration"
              type="number"
              min="5"
              max="480"
              step="5"
              required
          /></label>
        </div>
        <label
          ><input v-model="confirmed" type="checkbox" required /> Le rendez-vous est confirmé dans
          l’outil externe du conseiller.</label
        >
        <button class="primary" :disabled="!advisor?.booking_url || !confirmed || !!message">
          Envoyer le rendez-vous
        </button>
      </fieldset>
    </form>
    <p v-if="!busy && !count">Aucun conseiller actif associé. Contactez l’administration.</p>
    <button
      class="secondary"
      :disabled="busy || page === 1"
      @click="
        page--;
        load();
      "
    >
      Conseillers précédents
    </button>
    <button
      class="secondary"
      :disabled="busy || page * 25 >= count"
      @click="
        page++;
        load();
      "
    >
      Conseillers suivants
    </button>
    <details>
      <summary>Rendez-vous existants du prospect</summary>
      <AssuranceAppointments
        :key="historyVersion"
        history-only
        :role="role"
        :contact-id="contactId"
        :request="request"
        :portal="portal"
      />
    </details>
  </section>
</template>
<style scoped>
.transmission {
  padding: 20px;
  border: 1px solid #dce4f2;
  border-radius: 16px;
  background: #fff;
  margin-top: 16px;
}
.transmission fieldset {
  border: 0;
  padding: 0;
  display: grid;
  gap: 16px;
}
.transmission label {
  display: grid;
  gap: 7px;
}
.transmission-dates {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
.transmission details {
  margin-top: 20px;
}
</style>
