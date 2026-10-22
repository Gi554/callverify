<script setup lang="ts">
import { ref } from 'vue';
const props = defineProps<{
  visit: any;
  request: (path: string, body?: any, method?: string) => Promise<any>;
}>();
const emit = defineEmits<{ saved: []; cancel: [] }>();
const performed = ref('yes'),
  outcome = ref('completed'),
  note = ref(''),
  busy = ref(false),
  error = ref('');
async function save() {
  busy.value = true;
  error.value = '';
  try {
    await props.request(`visits/${props.visit.id}/result/`, {
      revision: props.visit.revision,
      performed: performed.value === 'yes',
      outcome: outcome.value,
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
        >La visite a-t-elle eu lieu ?<select
          v-model="performed"
          @change="outcome = performed === 'no' ? 'not_performed' : 'completed'"
        >
          <option value="yes">Oui, effectuée</option>
          <option value="no">Non, non effectuée</option>
        </select></label
      ><label
        >Résultat<select v-model="outcome">
          <option v-if="performed === 'no'" value="not_performed">Non effectuée</option>
          <template v-else
            ><option value="completed">Effectuée, sans qualification supplémentaire</option>
            <option value="follow_up">Suivi nécessaire</option>
            <option value="interested">Intéressé</option>
            <option value="not_interested">Non intéressé</option></template
          >
        </select></label
      ><label
        >Compte rendu ou motif obligatoire<textarea
          v-model="note"
          required
          maxlength="3000"
        ></textarea></label
      ><button class="primary">Enregistrer le résultat</button
      ><button type="button" class="secondary" @click="emit('cancel')">Annuler la saisie</button>
    </fieldset>
  </form>
</template>
