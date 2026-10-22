<script setup lang="ts">
import { ref, watch } from 'vue';
import { bookingInterval } from './booking-time';
const props = defineProps<{
  prospect: any;
  request: (path: string, body?: any) => Promise<any>;
  blocked?: boolean;
}>();
const emit = defineEmits<{
  saved: [];
  book: [];
  busy: [value: boolean];
  dirty: [value: boolean];
}>();
const result = ref(''),
  note = ref(''),
  local = ref(''),
  zone = ref('America/Toronto'),
  appointment = ref(''),
  visits = ref<any[]>([]),
  page = ref(1),
  count = ref(0),
  busy = ref(false),
  error = ref(''),
  message = ref('');
const labels: Record<string, string> = {
  appointment_booked: 'Rendez-vous pris',
  voicemail: 'Répondeur',
  invalid_number: 'Numéro invalide déclaré',
  disconnected: 'Appel coupé',
  not_interested: 'Pas intéressé',
  callback: 'A demandé à être rappelé',
  unreachable: 'Injoignable',
};
let requestId = crypto.randomUUID();
function changed() {
  requestId = crypto.randomUUID();
  emit('dirty', !!result.value || !!note.value);
}
watch(busy, (value) => emit('busy', value), { flush: 'sync' });
async function loadVisits() {
  busy.value = true;
  error.value = '';
  try {
    const data = await props.request(
      `visits/?prospect_id=${props.prospect.id}&status=scheduled&page=${page.value}`,
    );
    visits.value = data.results;
    count.value = data.count;
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
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
    if (result.value === 'appointment_booked') body.appointment_id = Number(appointment.value);
    await props.request(`work-queue/${props.prospect.id}/call-result/`, body);
    result.value = '';
    note.value = '';
    local.value = '';
    appointment.value = '';
    changed();
    message.value = 'Résultat déclaré enregistré. Aucun appel déclenché.';
    emit('saved');
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <section>
    <h3>Résultat d’appel déclaré</h3>
    <p>Cette saisie ne lance aucun appel et ne modifie pas les résultats Lookup.</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <form @submit.prevent="save" @input="changed" @change="changed">
      <fieldset :disabled="busy || blocked">
        <label
          >Résultat<select
            v-model="result"
            required
            @change="
              page = 1;
              appointment = '';
              result === 'appointment_booked' && loadVisits();
            "
          >
            <option value="">Choisir un résultat</option>
            <option v-for="(label, key) in labels" :key="key" :value="key">{{ label }}</option>
          </select></label
        ><template v-if="result === 'callback'"
          ><label
            >Date et heure du rappel<input v-model="local" type="datetime-local" required /></label
          ><label
            >Heure locale<select v-model="zone">
              <option value="America/Toronto">Toronto / Montréal</option>
              <option value="America/Vancouver">Vancouver</option>
              <option value="America/Halifax">Halifax</option>
            </select></label
          ></template
        ><template v-if="result === 'appointment_booked'"
          ><p>Enregistrez d’abord le C2 et le rendez-vous, puis liez la réservation ici.</p>
          <button type="button" class="secondary" @click="emit('book')">
            Préparer le C2 et réserver</button
          ><button type="button" class="secondary" @click="loadVisits">
            Actualiser les réservations</button
          ><label
            >Rendez-vous existant<select v-model="appointment" required>
              <option value="">Choisir la réservation</option>
              <option v-for="row in visits" :key="row.id" :value="String(row.id)">
                RDV {{ row.id }} ·
                {{
                  new Intl.DateTimeFormat('fr-FR', {
                    timeZone: row.timezone,
                    dateStyle: 'medium',
                    timeStyle: 'short',
                  }).format(new Date(row.starts_at))
                }}
                · {{ row.timezone }}
              </option>
            </select></label
          ><small>{{ count }} réservation(s) · page {{ page }}</small
          ><button
            type="button"
            class="secondary"
            :disabled="page === 1"
            @click="
              page--;
              loadVisits();
            "
          >
            Précédent</button
          ><button
            type="button"
            class="secondary"
            :disabled="page * 25 >= count"
            @click="
              page++;
              loadVisits();
            "
          >
            Suivant
          </button></template
        ><label>Note facultative<textarea v-model="note" maxlength="3000"></textarea></label
        ><button class="primary">Enregistrer le résultat déclaré</button>
      </fieldset>
    </form>
  </section>
</template>
