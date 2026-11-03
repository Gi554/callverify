<script setup lang="ts">
import { onMounted, ref } from 'vue';

type Attempt = {
  request_id: string;
  destination: string;
  caller_id: string;
  state: string;
  kind: string;
  created_at: string;
};
const props = defineProps<{ request: (path: string, body?: unknown) => Promise<any> }>();
const route = 'isolation/sms/';
const enabled = ref(false);
const callerId = ref('');
const history = ref<Attempt[]>([]);
const destination = ref('');
const message = ref('');
const requestId = ref('');
const current = ref<Attempt | null>(null);
const busy = ref(false);
const error = ref('');
const kinds: Record<string, string> = {
  manual: 'Manuel',
  confirmation: 'Confirmation',
  reminder: 'Rappel',
};
const labels: Record<string, string> = {
  dispatching: 'En cours',
  accepted: 'Accepté par NEWT',
  rejected: 'Refusé par NEWT',
  unknown: 'Envoi incertain',
};
async function refresh() {
  busy.value = true;
  error.value = '';
  try {
    const result = await props.request(route);
    enabled.value = result.enabled;
    callerId.value = result.caller_id;
    history.value = result.results;
    current.value =
      history.value.find((row) => row.request_id === requestId.value) ?? current.value;
  } catch (failure) {
    error.value = (failure as Error).message;
  } finally {
    busy.value = false;
  }
}
async function send() {
  if (busy.value || requestId.value || !enabled.value || !message.value.trim()) return;
  if (!window.confirm('Envoyer ce SMS au ' + destination.value + ' ?')) return;
  requestId.value = crypto.randomUUID();
  busy.value = true;
  error.value = '';
  try {
    const result: Attempt = await props.request(route, {
      request_id: requestId.value,
      destination: destination.value,
      message: message.value,
    });
    current.value = result;
    history.value = [result, ...history.value].slice(0, 25);
    message.value = '';
  } catch {
    error.value = 'Envoi incertain. Actualisez le journal avant toute nouvelle tentative.';
  } finally {
    busy.value = false;
  }
}
function reset() {
  if (
    !current.value ||
    current.value.state === 'unknown' ||
    current.value.state === 'dispatching'
  ) {
    if (!window.confirm('La réception du SMS précédent est incertaine. Commencer un nouveau SMS ?'))
      return;
  }
  requestId.value = '';
  current.value = null;
  message.value = '';
  destination.value = '';
  error.value = '';
}
const format = new Intl.DateTimeFormat('fr-CA', {
  timeZone: 'America/Toronto',
  dateStyle: 'medium',
  timeStyle: 'short',
});
onMounted(refresh);
</script>

<template>
  <section class="card">
    <h2>SMS NEWT</h2>
    <p v-if="!enabled">
      Envoi indisponible. Configurez le numéro expéditeur du PBX et activez NEWT SMS sur le serveur.
    </p>
    <p v-else>Expéditeur PBX {{ callerId }}. Le journal indique la réponse de NEWT.</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="current" role="status">{{ labels[current.state] }}</p>
    <form v-if="enabled && !requestId" @submit.prevent="send">
      <label
        >Destinataire à 10 chiffres
        <input
          v-model="destination"
          type="tel"
          pattern="[2-9][0-9]{2}[2-9][0-9]{6}"
          maxlength="10"
          required
        />
      </label>
      <label
        >Message
        <textarea v-model="message" maxlength="1600" required />
      </label>
      <button class="primary" :disabled="busy">Envoyer le SMS</button>
    </form>
    <button v-if="requestId" type="button" class="secondary" :disabled="busy" @click="reset">
      Nouveau SMS
    </button>
    <button type="button" class="secondary" :disabled="busy" @click="refresh">
      Actualiser le journal
    </button>
    <h3>Derniers envois · heure du Québec</h3>
    <p v-if="!history.length">Aucun envoi enregistré.</p>
    <ul v-else>
      <li v-for="row in history" :key="row.request_id">
        {{ format.format(new Date(row.created_at)) }} · {{ row.destination }} ·
        {{ kinds[row.kind] || kinds.manual }} · {{ labels[row.state] }}
      </li>
    </ul>
  </section>
</template>
