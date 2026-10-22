<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
const props = defineProps<{
  request: (path: string, body?: any, method?: string) => Promise<any>
  refreshVersion: number
}>()
const emit = defineEmits<{ open: [deadline: string] }>()
const data = ref<any>(null),
  error = ref(''),
  busy = ref(false)
let timer: ReturnType<typeof setInterval> | undefined
async function load() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    data.value = await props.request('agreement-deadlines/')
  } catch (e: any) {
    data.value = null
    error.value = e.message
  } finally {
    busy.value = false
  }
}
watch(
  () => props.refreshVersion,
  () => load(),
)
onMounted(() => {
  void load()
  timer = setInterval(() => {
    if (document.visibilityState === 'visible') void load()
  }, 60000)
})
onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>
<!-- prettier-ignore -->
<template><section><h3>Échéances des mandats et contrats</h3><p v-if="error" role="alert">Échéances indisponibles : {{error}}</p><template v-if="data"><p role="status">{{data.overdue}} suivi(s) avec date de fin dépassée · {{data.upcoming}} échéance(s) dans les 30 jours · {{data.undated}} suivi(s) sans date de fin.</p><button class="secondary" @click="emit('open','overdue')">Voir les dates dépassées</button><button class="secondary" @click="emit('open','upcoming')">Voir les échéances proches</button><p>Situation au {{data.as_of}} (UTC), états En suivi uniquement. Consulter une alerte ne la supprime pas et ne modifie aucun statut.</p></template><button class="secondary" :disabled="busy" @click="load">Actualiser les échéances</button></section></template>
