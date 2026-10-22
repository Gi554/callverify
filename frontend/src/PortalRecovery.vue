<script setup lang="ts">
import { ref } from 'vue';
const props = defineProps<{
  uid: string;
  token: string;
  request: (path: string, body?: any, method?: string) => Promise<any>;
}>();
const emit = defineEmits<{ close: [] }>();
const email = ref(''),
  password = ref(''),
  confirmation = ref(''),
  busy = ref(false),
  error = ref(''),
  message = ref(''),
  done = ref(false);
async function submit() {
  busy.value = true;
  error.value = '';
  message.value = '';
  try {
    if (props.token) {
      await props.request('password/reset/confirm/', {
        uid: props.uid,
        token: props.token,
        password: password.value,
        confirmation: confirmation.value,
      });
      password.value = '';
      confirmation.value = '';
      done.value = true;
      message.value = 'Mot de passe réinitialisé. Reconnectez-vous avec le nouveau mot de passe.';
    } else {
      const data = await props.request('password/reset/request/', { email: email.value });
      message.value = data.detail;
    }
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <section class="amx-login">
    <h1>{{ token ? 'Nouveau mot de passe' : 'Mot de passe oublié' }}</h1>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <form v-if="!done" @submit.prevent="submit">
      <template v-if="token"
        ><label
          >Nouveau mot de passe<input
            v-model="password"
            type="password"
            autocomplete="new-password"
            required
            minlength="12"
            maxlength="256"
            :disabled="busy" /></label
        ><label
          >Confirmation<input
            v-model="confirmation"
            type="password"
            autocomplete="new-password"
            required
            minlength="12"
            maxlength="256"
            :disabled="busy" /></label></template
      ><label v-else
        >Adresse e-mail de votre compte<input
          v-model="email"
          type="email"
          autocomplete="email"
          required
          maxlength="254"
          :disabled="busy" /></label
      ><button class="primary" :disabled="busy">
        {{ token ? 'Réinitialiser le mot de passe' : 'Demander le lien' }}
      </button>
    </form>
    <button class="secondary" :disabled="busy" @click="emit('close')">Retour à la connexion</button>
  </section>
</template>
