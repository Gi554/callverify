<script setup lang="ts">
import { ref } from 'vue';
const props = defineProps<{
  visit: any;
  request: (path: string, body?: any, method?: string) => Promise<any>;
}>();
const emit = defineEmits<{ saved: []; cancel: [] }>();
const performed = ref(''),
  closed = ref(''),
  note = ref(''),
  busy = ref(false),
  error = ref('');
async function save() {
  if (!performed.value || !closed.value || (closed.value === 'yes' && performed.value !== 'yes'))
    return;
  busy.value = true;
  error.value = '';
  try {
    await props.request(`visits/${props.visit.id}/result/`, {
      revision: props.visit.revision,
      performed: performed.value === 'yes',
      closed: closed.value === 'yes',
      outcome:
        performed.value === 'no'
          ? 'not_performed'
          : closed.value === 'yes'
            ? 'closed'
            : 'completed',
      note: note.value,
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
        >Le rendez-vous a-t-il été tenu ?<select
          v-model="performed"
          required
          @change="performed === 'no' && (closed = 'no')"
        >
          <option value="">Choisir</option>
          <option value="yes">Oui</option>
          <option value="no">Non</option>
        </select></label
      >
      <label
        >Le rendez-vous a-t-il été closé ?<select v-model="closed" required>
          <option value="">Choisir</option>
          <option value="yes" :disabled="performed !== 'yes'">Oui</option>
          <option value="no">Non</option>
        </select></label
      >
      <label>Notes · facultatives<textarea v-model="note" maxlength="3000"></textarea></label>
      <button class="primary" :disabled="!performed || !closed">Enregistrer le résultat</button>
      <button type="button" class="secondary" @click="emit('cancel')">Annuler la saisie</button>
    </fieldset>
  </form>
</template>
