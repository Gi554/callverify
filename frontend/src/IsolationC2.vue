<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
const props = defineProps<{
  prospectId: number
  request: (path: string, body?: any) => Promise<any>
  blocked?: boolean
}>()
const emit = defineEmits<{
  saved: [revision: number]
  dirty: [value: boolean]
  busy: [value: boolean]
}>()
const labels: Record<string, string> = {
  full_name: 'Nom et prénom',
  phone: 'Téléphone',
  address: 'Adresse complète',
  city: 'Ville',
  postal_code: 'Code postal',
  attic_accessible: 'Grenier accessible',
  monthly_electricity: 'Électricité mensuelle ($)',
  construction_year: 'Année de construction',
  age: 'Âge du client',
}
const values = ref<any>({}),
  revision = ref(0),
  loaded = ref(false),
  busy = ref(false),
  error = ref(''),
  message = ref(''),
  baseline = ref('')
const dirty = computed(() => loaded.value && JSON.stringify(values.value) !== baseline.value)
watch(dirty, (value) => emit('dirty', value), { flush: 'sync' })
watch(busy, (value) => emit('busy', value), { flush: 'sync' })
async function load() {
  busy.value = true
  error.value = ''
  try {
    const row = await props.request(`work-queue/${props.prospectId}/c2/`)
    values.value = {
      full_name: row.defaults.full_name || '',
      phone: row.defaults.phone || '',
      address: '',
      city: '',
      postal_code: '',
      attic_accessible: null,
      monthly_electricity: null,
      construction_year: null,
      age: null,
      ...row.c2,
    }
    revision.value = row.revision
    baseline.value = JSON.stringify(values.value)
    loaded.value = true
    emit('saved', row.revision)
  } catch (e: any) {
    error.value = e.message
    throw e
  } finally {
    busy.value = false
  }
}
async function ensureSaved() {
  if (!loaded.value) throw new Error('Chargez le formulaire C2 avant de réserver.')
  if (busy.value) throw new Error('Enregistrement C2 en cours.')
  if (!dirty.value) return
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    const row = await props.request(`work-queue/${props.prospectId}/c2/`, {
      revision: revision.value,
      c2: values.value,
    })
    values.value = row.c2
    revision.value = row.revision
    baseline.value = JSON.stringify(values.value)
    emit('saved', row.revision)
    message.value = 'Brouillon C2 enregistré.'
  } catch (e: any) {
    error.value = e.message
    throw e
  } finally {
    busy.value = false
  }
}
async function reload() {
  if (dirty.value && !window.confirm('Recharger et abandonner les modifications C2 ?')) return
  try {
    await load()
  } catch {}
}
async function save() {
  try {
    await ensureSaved()
  } catch {}
}
function unload(event: BeforeUnloadEvent) {
  if (dirty.value) {
    event.preventDefault()
    event.returnValue = ''
  }
}
onMounted(() => {
  window.addEventListener('beforeunload', unload)
  load().catch(() => {})
})
onBeforeUnmount(() => window.removeEventListener('beforeunload', unload))
defineExpose({ ensureSaved, dirty })
</script>
<!-- prettier-ignore -->
<template><section class="c2-form"><header><span>ISOLATION · FORMULAIRE C2</span><h3>Préparer la visite</h3><p>Enregistrez votre brouillon à tout moment. Tous les champs, sauf le coût d’électricité, sont requis pour réserver.</p></header><p v-if="error" role="alert">{{error}}</p><p v-if="message" role="status">{{message}}</p><fieldset v-if="loaded" :disabled="busy||blocked"><div class="c2-grid"><label v-for="key in ['full_name','phone','address','city','postal_code']" :key="key">{{labels[key]}}<input v-model="values[key]" :type="key==='phone'?'tel':'text'" :maxlength="key==='address'?500:key==='phone'?40:key==='city'?150:key==='postal_code'?10:250"></label><label>Grenier accessible<select v-model="values.attic_accessible"><option :value="null">Non renseigné</option><option :value="true">Oui</option><option :value="false">Non</option></select></label><label>Coût mensuel d’électricité ($) · facultatif<input v-model="values.monthly_electricity" type="number" min="0" max="9999999.99" step="0.01" @change="values.monthly_electricity=values.monthly_electricity===''?null:values.monthly_electricity"></label><label>Année de construction<input v-model.number="values.construction_year" type="number" min="1600" :max="new Date().getFullYear()" step="1" @change="values.construction_year=values.construction_year===''?null:values.construction_year"></label><label>Âge du client<input v-model.number="values.age" type="number" min="0" max="120" step="1" @change="values.age=values.age===''?null:values.age"></label></div><button type="button" class="secondary" :disabled="!dirty" @click="save">{{busy?'Enregistrement…':'Enregistrer le brouillon C2'}}</button><small v-if="dirty">Modifications à enregistrer</small><button type="button" class="secondary" @click="reload">Recharger le C2</button></fieldset><button v-else type="button" class="secondary" :disabled="busy" @click="load().catch(()=>{})">Charger le formulaire C2</button></section></template>
<style scoped>
.c2-form {
  padding: 20px;
  border: 1px solid #e5e8f3;
  border-radius: 14px;
  background: #fbfcff;
  margin: 18px 0;
}
.c2-form header > span {
  font-size: 10px;
  color: #7761b4;
  letter-spacing: 1px;
}
.c2-form h3 {
  margin: 8px 0;
}
.c2-form p {
  font-size: 12px;
  line-height: 1.6;
}
.c2-form fieldset {
  border: 0;
  padding: 0;
  margin: 0;
}
.c2-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}
.c2-grid label {
  display: flex;
  flex-direction: column;
  gap: 7px;
  font-size: 12px;
}
.c2-grid input,
.c2-grid select {
  width: 100%;
  box-sizing: border-box;
}
.c2-form small {
  display: block;
  margin-top: 8px;
  color: #7761b4;
}
@media (max-width: 650px) {
  .c2-grid {
    grid-template-columns: 1fr;
  }
}
</style>
