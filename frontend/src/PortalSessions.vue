<script setup lang="ts">
import { ref } from 'vue';
const props = defineProps<{
  request: (path: string, body?: any, method?: string) => Promise<any>;
}>();
const password = ref(''),
  busy = ref(false),
  error = ref(''),
  message = ref('');
async function revoke() {
  busy.value = true;
  error.value = '';
  message.value = '';
  try {
    await props.request('session/revoke-others/', { current_password: password.value });
    message.value =
      'Les autres sessions du portail devront se reconnecter lors de leur prochaine requête. Cette session reste ouverte.';
  } catch (e: any) {
    error.value = e.message;
  } finally {
    password.value = '';
    busy.value = false;
  }
}
</script>
<template>
  <section>
    <h3>Déconnecter mes autres appareils</h3>
    <p>
      Cette action concerne toutes vos autres sessions du portail Orvia, dans les deux espaces.
      Confirmez avec votre mot de passe actuel ; cette session reste ouverte.
    </p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <form @submit.prevent="revoke">
      <fieldset :disabled="busy">
        <label
          >Mot de passe actuel<input
            v-model="password"
            type="password"
            autocomplete="current-password"
            required
            maxlength="256" /></label
        ><button class="secondary">Confirmer la déconnexion des autres sessions</button>
      </fieldset>
    </form>
    <p>
      Les autorisations métier déjà délivrées peuvent rester valides deux minutes. Les requêtes déjà
      en cours et la session de l’application historique ne sont pas interrompues. Si la connexion
      est perdue pendant cette action, reconnectez-vous.
    </p>
  </section>
</template>
