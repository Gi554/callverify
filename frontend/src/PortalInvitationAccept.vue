<script setup lang="ts">
import {ref} from 'vue'
const props=defineProps<{id:string;token:string;request:(path:string,body?:any)=>Promise<any>}>()
defineEmits<{close:[]}>()
const password=ref(''),confirmation=ref(''),busy=ref(false),error=ref(''),done=ref(false)
async function accept(){busy.value=true;error.value='';try{await props.request('invitations/accept/',{id:props.id,token:props.token,password:password.value,confirmation:confirmation.value});password.value='';confirmation.value='';done.value=true}catch(e:any){error.value=e.message}finally{busy.value=false}}
</script>
<template><section class="amx-login"><h1>Accepter votre invitation</h1><p v-if="error" role="alert">{{error}}</p><p v-if="done" role="status">Votre compte est prêt. Connectez-vous avec l’identifiant reçu par e-mail.</p><form v-else @submit.prevent="accept"><label>Choisissez votre mot de passe<input v-model="password" type="password" required minlength="12" maxlength="256" autocomplete="new-password"></label><label>Confirmez le mot de passe<input v-model="confirmation" type="password" required minlength="12" maxlength="256" autocomplete="new-password"></label><button class="primary" :disabled="busy">Créer mon accès</button></form><button class="secondary" @click="$emit('close')">Retour à la connexion</button></section></template>
