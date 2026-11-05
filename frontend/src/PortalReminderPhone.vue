<script setup lang="ts">
// Mobile number the Isolation client chooses for its reminder SMS. Empty until it is set.
import { ref, onMounted } from 'vue';
const props = defineProps<{
  request: (path: string, body?: any, method?: string) => Promise<any>;
}>();
const available = ref(false),
  mobile = ref(''),
  busy = ref(false),
  error = ref(''),
  message = ref('');
async function load() {
  try {
    const data = await props.request('reminder-phone/');
    available.value = data.available === true;
    mobile.value = data.mobile || '';
  } catch {
    available.value = false;
  }
}
async function save() {
  busy.value = true;
  error.value = '';
  message.value = '';
  try {
    const data = await props.request('reminder-phone/', { mobile: mobile.value }, 'PUT');
    mobile.value = data.mobile || '';
    message.value = mobile.value
      ? 'Numéro enregistré. Vous recevrez le rappel par SMS sur ce numéro.'
      : 'Numéro retiré. Aucun SMS de rappel ne sera envoyé.';
  } catch (e: any) {
    error.value = e.message || 'Numéro non enregistré.';
  } finally {
    busy.value = false;
  }
}
onMounted(load);
</script>
<template>
  <section v-if="available" class="reminder-phone">
    <h3>Numéro mobile pour les rappels</h3>
    <p>
      Si un rendez-vous n’est toujours pas mis à jour 24 h après la visite, un SMS de rappel est
      envoyé à ce numéro. Laissez le champ vide pour ne recevoir aucun SMS.
    </p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <form @submit.prevent="save">
      <fieldset :disabled="busy">
        <label
          >Numéro mobile<input
            v-model="mobile"
            type="tel"
            inputmode="tel"
            autocomplete="tel"
            maxlength="40"
            placeholder="514 555 0123" /></label
        ><button class="primary">Enregistrer le numéro</button>
      </fieldset>
    </form>
  </section>
</template>
