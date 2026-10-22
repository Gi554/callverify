<script setup lang="ts">
import { ref, onMounted } from 'vue'
const props = defineProps<{
  visit: any
  portal: (path: string, body?: any) => Promise<any>
  request: (path: string, body?: any) => Promise<any>
}>()
const emit = defineEmits<{ saved: []; busy: [value: boolean] }>()
const rows = ref<any[]>([]),
  page = ref(1),
  count = ref(0),
  search = ref(''),
  target = ref(''),
  reason = ref(''),
  busy = ref(false),
  error = ref('')
async function run(action: () => Promise<void>) {
  busy.value = true
  emit('busy', true)
  error.value = ''
  try {
    await action()
  } catch (e: any) {
    error.value = e.message
  } finally {
    busy.value = false
    emit('busy', false)
  }
}
async function load() {
  const data = await props.portal(
    `isolation/closers/?page=${page.value}&search=${encodeURIComponent(search.value)}`,
  )
  rows.value = data.results
  count.value = data.count
}
async function save() {
  let saved = false
  await run(async () => {
    const signed = await props.portal('isolation/closers/', {
      visit_id: props.visit.id,
      closer_id: Number(target.value),
    })
    await props.request(`visits/${props.visit.id}/assign-closer/`, {
      revision: props.visit.revision,
      proof: signed.proof,
      reason: reason.value,
    })
    saved = true
  })
  if (saved) emit('saved')
}
onMounted(() => run(load))
</script>
<!-- prettier-ignore -->
<template><section><h4>Attribuer la visite à un closer</h4><p v-if="error" role="alert">{{error}}</p><form @submit.prevent="run(async()=>{page=1;await load()})"><label>Rechercher un closer actif<input v-model="search"></label><button class="secondary" :disabled="busy">Rechercher</button></form><form @submit.prevent="save"><fieldset :disabled="busy"><label>Closer<select v-model="target" required><option value="">Choisir un closer</option><option v-for="row in rows" :key="row.id" :value="String(row.id)">{{row.name}}</option></select></label><small>{{count}} closer(s) · page {{page}}</small><button type="button" class="secondary" :disabled="page===1" @click="run(async()=>{page--;await load()})">Précédent</button><button type="button" class="secondary" :disabled="page*25>=count" @click="run(async()=>{page++;await load()})">Suivant</button><label>Motif d’attribution ou de réattribution<textarea v-model="reason" required maxlength="1000"></textarea></label><button class="primary">Confirmer l’attribution</button></fieldset></form></section></template>
