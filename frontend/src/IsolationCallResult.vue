<script setup lang="ts">
import { ref, watch } from 'vue';
import { bookingInterval } from './booking-time';
const props = defineProps<{
  prospect: any;
  request: (path: string, body?: any) => Promise<any>;
  blocked?: boolean;
}>();
const emit = defineEmits<{
  saved: [result: string];
  book: [];
  busy: [value: boolean];
  dirty: [value: boolean];
}>();
const result = ref(''),
  note = ref(''),
  local = ref(''),
  zone = ref('America/Toronto'),
  busy = ref(false),
  error = ref(''),
  message = ref('');
const labels: Record<string, string> = {
  appointment_booked: 'Rendez-vous pris',
  voicemail: 'Répondeur',
  invalid_number: 'Numéro non attribué',
  disconnected: 'Appel coupé',
  not_interested: 'Pas intéressé',
  callback: 'A demandé à être rappelé',
  other: 'Autre résultat',
};
let requestId = crypto.randomUUID();
function changed() {
  requestId = crypto.randomUUID();
  emit('dirty', !!result.value || !!note.value);
}
watch(busy, (value) => emit('busy', value), { flush: 'sync' });
function chooseResult() {
  if (result.value === 'appointment_booked') {
    // A booking is not a saved call outcome until a visit actually exists.
    result.value = '';
    changed();
    emit('book');
  }
}
async function save() {
  if (busy.value) return;
  busy.value = true;
  error.value = '';
  message.value = '';
  try {
    const body: any = {
      request_id: requestId,
      revision: props.prospect.revision,
      result: result.value,
      note: note.value,
    };
    if (result.value === 'callback')
      body.due_at = bookingInterval(local.value, zone.value, 15).starts_at;
    await props.request(`work-queue/${props.prospect.id}/call-result/`, body);
    const savedResult = result.value;
    result.value = '';
    note.value = '';
    local.value = '';
    changed();
    message.value = 'Résultat déclaré enregistré. Aucun appel déclenché.';
    emit('saved', savedResult);
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <section>
    <h3>Résultat de l’appel</h3>
    <p>Cette saisie ne lance aucun appel et ne modifie pas les résultats Lookup.</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <form @submit.prevent="save" @input="changed" @change="changed">
      <fieldset :disabled="busy || blocked">
        <label
          >Résultat<select v-model="result" required @change="chooseResult">
            <option value="">Choisir un résultat</option>
            <option v-for="(label, key) in labels" :key="key" :value="key">{{ label }}</option>
          </select></label
        ><template v-if="result === 'callback'"
          ><label
            >Date et heure du rappel<input v-model="local" type="datetime-local" required /></label
          ><label
            >Heure locale<select v-model="zone">
              <option value="America/Toronto">Toronto / Montréal</option>
            </select></label
          ></template
        ><label>Note facultative<textarea v-model="note" maxlength="3000"></textarea></label
        ><button class="primary">
          {{
            ['voicemail', 'invalid_number', 'disconnected'].includes(result)
              ? 'Enregistrer et passer au suivant'
              : 'Enregistrer le résultat'
          }}
        </button>
      </fieldset>
    </form>
  </section>
</template>
