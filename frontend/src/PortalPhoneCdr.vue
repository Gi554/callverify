<script setup lang="ts">
import { ref } from 'vue'
const props = defineProps<{
  request: (path: string, body?: any, method?: string) => Promise<any>
}>()
const start = ref(''),
  end = ref(''),
  result = ref<any>(null),
  error = ref(''),
  busy = ref(false)
async function inspect() {
  busy.value = true
  error.value = ''
  result.value = null
  try {
    result.value = await props.request('phone-cdr-schema/', {
      starts_on: start.value,
      ends_on: end.value,
    })
  } catch (e: any) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>
<!-- prettier-ignore -->
<template><section><h3>Journaux NEWT — diagnostic du format</h3><p>Lecture 511 uniquement, aucun appel. Première étape technique : en-têtes et nombre de lignes, sans affichage ni conservation des appels. Le rapprochement avec les setters/dossiers et l’interprétation des résultats ne sont pas encore disponibles. Consultation réservée aux administrateurs des deux espaces, désactivée par défaut côté serveur.</p><form @submit.prevent="inspect"><fieldset :disabled="busy"><label>Du<input v-model="start" type="date" required></label><label>Au<input v-model="end" type="date" required></label><p>Sept dates maximum, sans date future. Les dates correspondent au rapport du PBX ; son fuseau confirmé est America/Toronto (Montréal), avec changement saisonnier.</p><button class="secondary">Inspecter les colonnes du rapport</button></fieldset></form><p v-if="error" role="alert">{{error}}</p><section v-if="result"><p>{{result.row_count}} ligne(s) · {{result.source}} · consulté le {{new Date(result.checked_at).toLocaleString('fr-FR')}}</p><ol><li v-for="(column,index) in result.columns" :key="index">{{column}}</li></ol><p>Empreinte du schéma : {{result.schema_fingerprint}}</p><p>{{result.mapping_confirmed?'Colonnes conformes au format confirmé par Phonetico.':'En-têtes différents du format confirmé : aucune correspondance acceptée.'}} Fuseau : {{result.timezone}}. L’unité de durée n’est pas confirmée ; aucune présence humaine n’est déduite. Un rapport sans ligne n’est pas une preuve d’absence d’appels ou d’activité d’un setter.</p></section></section></template>
