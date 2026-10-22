<script setup lang="ts">
import { ref, onMounted } from 'vue'
const props = defineProps<{
  contactId: number
  request: (path: string, body?: any, method?: string) => Promise<any>
}>()
const fields = ref<any[]>([]),
  busy = ref(false),
  error = ref('')
async function load() {
  busy.value = true
  error.value = ''
  fields.value = []
  try {
    fields.value = (await props.request(`contacts/${props.contactId}/shared_fields/`)).fields
  } catch (e: any) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
function display(field: any) {
  if (field.value === null || field.value === undefined || field.value === '')
    return 'Non renseigné'
  if (field.type === 'boolean') return field.value ? 'Oui' : 'Non'
  return String(field.value)
}
onMounted(load)
</script>
<!-- prettier-ignore -->
<template><section><h3>Informations métier partagées</h3><p>Lecture seule des champs rendus visibles par l’administration sur ce dossier.</p><p v-if="error" role="alert">{{error}}</p><p v-if="!busy&&!error&&!fields.length">Aucun champ métier partagé actuellement.</p><dl><template v-for="field in fields" :key="field.key"><dt>{{field.label}}</dt><dd style="white-space:pre-wrap;overflow-wrap:anywhere">{{display(field)}}</dd></template></dl><button class="secondary" :disabled="busy" @click="load">Actualiser les informations partagées</button></section></template>
