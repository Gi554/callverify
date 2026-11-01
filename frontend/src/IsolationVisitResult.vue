<script setup lang="ts">
import { ref } from 'vue';
import { bookingInterval } from './booking-time';
const props = defineProps<{
  visit: any;
  request: (path: string, body?: any, method?: string) => Promise<any>;
}>();
const emit = defineEmits<{ saved: []; cancel: [] }>();
const performed = ref(props.visit.result ? (props.visit.result.performed ? 'yes' : 'no') : ''),
  closed = ref(
    props.visit.result?.closed === null || props.visit.result?.closed === undefined
      ? ''
      : props.visit.result.closed
        ? 'yes'
        : 'no',
  ),
  note = ref(props.visit.result?.note || ''),
  reason = ref(''),
  busy = ref(false),
  error = ref('');
const followUpOwner = ref(props.visit.result?.follow_up_owner || ''),
  unqualified = ref(props.visit.result?.outcome === 'unqualified'),
  absenceReason = ref(props.visit.result?.absence_reason || ''),
  followUpAt = ref(local(props.visit.result?.follow_up_at));
function local(value?: string) {
  if (!value) return '';
  const p = Object.fromEntries(
    new Intl.DateTimeFormat('en-CA', {
      timeZone: 'America/Toronto',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
    })
      .formatToParts(new Date(value))
      .map((part) => [part.type, part.value]),
  );
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}
async function save() {
  if (unqualified.value && !absenceReason.value.trim()) return;
  if (
    !unqualified.value &&
    (!performed.value || !closed.value || (closed.value === 'yes' && performed.value !== 'yes'))
  )
    return;
  if (
    !unqualified.value &&
    performed.value === 'no' &&
    (!followUpOwner.value || !absenceReason.value.trim())
  )
    return;
  busy.value = true;
  error.value = '';
  try {
    await props.request(`visits/${props.visit.id}/result/`, {
      revision: props.visit.revision,
      performed: !unqualified.value && performed.value === 'yes',
      closed: !unqualified.value && closed.value === 'yes',
      outcome: unqualified.value
        ? 'unqualified'
        : performed.value === 'no'
          ? 'not_performed'
          : closed.value === 'yes'
            ? 'closed'
            : 'completed',
      note: note.value,
      ...(unqualified.value ? { absence_reason: absenceReason.value } : {}),
      ...(!unqualified.value && performed.value === 'no'
        ? {
            follow_up_owner: followUpOwner.value,
            absence_reason: absenceReason.value,
            follow_up_at: followUpAt.value
              ? followUpAt.value === local(props.visit.result?.follow_up_at)
                ? props.visit.result.follow_up_at
                : bookingInterval(followUpAt.value, 'America/Toronto', 30).starts_at
              : null,
          }
        : {}),
      ...(props.visit.result ? { reason: reason.value } : {}),
    });
    emit('saved');
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <form @submit.prevent="save">
    <h4>Résultat de la visite · {{ visit.prospect.name || visit.prospect.phone }}</h4>
    <p>
      Le résultat est conservé dans l’historique. Une absence de réponse ne sera jamais enregistrée
      comme une visite non effectuée.
    </p>
    <p v-if="error" role="alert">{{ error }}</p>
    <fieldset :disabled="busy">
      <label
        ><input v-model="unqualified" type="checkbox" />Rendez-vous non qualifié — non validé</label
      >
      <label v-if="unqualified"
        >Motif de non-qualification<textarea
          v-model="absenceReason"
          required
          maxlength="1000"
        ></textarea>
      </label>
      <label v-if="!unqualified"
        >Le prospect s’est-il présenté au rendez-vous ?<select
          v-model="performed"
          required
          @change="closed = performed === 'no' ? 'no' : ''"
        >
          <option value="">Choisir</option>
          <option value="yes">Oui</option>
          <option value="no">Non</option>
        </select></label
      >
      <label v-if="!unqualified && performed === 'yes'"
        >Le rendez-vous a-t-il été closé (vente réalisée) ?<select v-model="closed" required>
          <option value="">Choisir</option>
          <option value="yes" :disabled="performed !== 'yes'">Oui</option>
          <option value="no">Non</option>
        </select></label
      >
      <template v-if="!unqualified && performed === 'no'">
        <label
          >Motif de non-présentation<textarea
            v-model="absenceReason"
            required
            maxlength="1000"
          ></textarea>
        </label>
        <label
          >Qui effectue le suivi ?<select v-model="followUpOwner" required>
            <option value="">Choisir</option>
            <option value="setter">Demander au setter de rappeler</option>
            <option value="client">À recontacter par moi-même</option>
          </select></label
        >
        <label
          >Date de rappel · Québec · facultative<input v-model="followUpAt" type="datetime-local"
        /></label>
        <p v-if="followUpOwner === 'client'">
          Cette relance sera conservée dans votre espace. Aucune tâche ne sera créée chez le setter.
        </p>
      </template>
      <label>Notes · facultatives<textarea v-model="note" maxlength="3000"></textarea></label>
      <label v-if="visit.result"
        >Motif de la mise à jour<textarea v-model="reason" required maxlength="1000"></textarea>
      </label>
      <button
        class="primary"
        :disabled="
          (!unqualified &&
            (!performed ||
              !closed ||
              (!!visit.result && !reason.trim()) ||
              (performed === 'no' && (!followUpOwner || !absenceReason.trim())))) ||
          (unqualified && !absenceReason.trim()) ||
          (!!visit.result && !reason.trim())
        "
      >
        Enregistrer le résultat
      </button>
      <button type="button" class="secondary" @click="emit('cancel')">Annuler la saisie</button>
    </fieldset>
  </form>
</template>
