<script setup lang="ts">
import { ref, watch } from 'vue'
const props = defineProps<{
  rows: any[]
  portal: (path: string, body?: any) => Promise<any>
  request: (path: string, body?: any) => Promise<any>
}>()
const emit = defineEmits<{ changed: [] }>()
const open = ref(false),
  ids = ref<number[]>([]),
  setters = ref<number[]>([]),
  names = ref<Record<number, string>>({}),
  reason = ref(''),
  people = ref<any[]>([]),
  page = ref(1),
  count = ref(0),
  search = ref(''),
  busy = ref(false),
  error = ref(''),
  message = ref(''),
  plan = ref<any>(null),
  requestId = ref(crypto.randomUUID())
watch(
  () => props.rows,
  () => {
    ids.value = []
    plan.value = null
    requestId.value = crypto.randomUUID()
  },
)
watch(
  [ids, setters, reason],
  () => {
    plan.value = null
    requestId.value = crypto.randomUUID()
  },
  { deep: true, flush: 'sync' },
)
async function run(action: () => Promise<void>) {
  busy.value = true
  error.value = ''
  try {
    await action()
  } catch (e: any) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
async function directory() {
  const data = await props.portal(
    `isolation/setters/?page=${page.value}&search=${encodeURIComponent(search.value)}`,
  )
  people.value = data.results
  count.value = data.count
  for (const person of people.value) names.value[person.id] = person.name
}
function label(id: number) {
  const row = props.rows.find((row) => row.id === id)
  return row?.name || row?.raw_phone || `Prospect ${id}`
}
async function preview() {
  await run(async () => {
    message.value = ''
    plan.value = await props.request('work-queue/distribution-preview/', {
      setter_ids: setters.value,
      items: props.rows
        .filter((row) => ids.value.includes(row.id))
        .map((row) => ({ id: row.id, revision: row.revision })),
    })
  })
}
async function confirm() {
  await run(async () => {
    const items = await Promise.all(
      plan.value.items.map(async (item: any) => ({
        id: item.id,
        revision: item.revision,
        proof: (
          await props.portal('isolation/setters/', {
            prospect_id: item.id,
            setter_id: item.setter_id,
          })
        ).proof,
      })),
    )
    const result = await props.request('work-queue/distribute/', {
      request_id: requestId.value,
      reason: reason.value,
      setter_ids: setters.value,
      items,
    })
    message.value = `${result.count} prospect(s) réparti(s).`
    plan.value = null
    emit('changed')
  })
}
</script>
<!-- prettier-ignore -->
<template><section><button class="secondary" :disabled="busy" @click="run(async()=>{open=!open;if(open)await directory()})">{{open?'Fermer la répartition':'Répartir entre plusieurs setters'}}</button><section v-if="open"><h4>Répartition des prospects sans responsable</h4><p>25 prospects maximum de la page courante. Répartition à tour de rôle par identifiants croissants : l’écart entre les nombres attribués dans ce lot est au plus un. La charge existante et les lots précédents ne sont pas pris en compte. Aucune réattribution.</p><p v-if="error" role="alert">{{error}}</p><p v-if="message" role="status">{{message}}</p><button class="secondary" :disabled="busy" @click="ids=rows.filter(row=>!row.assigned_setter).map(row=>row.id)">Sélectionner les non affectés de cette page</button><button class="secondary" :disabled="busy" @click="ids=[]">Désélectionner</button><label v-for="row in rows" :key="row.id"><input v-model="ids" type="checkbox" :value="row.id" :disabled="busy||!!row.assigned_setter">{{row.name||row.raw_phone}} · {{row.assigned_setter?'Déjà affecté':'Sans responsable'}}</label><form @submit.prevent="run(async()=>{page=1;await directory()})"><label>Rechercher un setter actif<input v-model="search" :disabled="busy"></label><button class="secondary" :disabled="busy">Rechercher</button></form><label v-for="person in people" :key="person.id"><input v-model="setters" type="checkbox" :value="person.id" :disabled="busy||(!setters.includes(person.id)&&setters.length>=25)">{{person.name}}</label><p>{{setters.length}} setter(s) choisi(s), conservés entre les pages : {{setters.map(id=>names[id]||id).join(', ')}}</p><button class="secondary" :disabled="busy" @click="setters=[]">Vider les setters choisis</button><p>{{count}} setter(s) · page {{page}}</p><button class="secondary" :disabled="busy||page===1" @click="run(async()=>{page--;await directory()})">Précédent</button><button class="secondary" :disabled="busy||page*25>=count" @click="run(async()=>{page++;await directory()})">Suivant</button><label>Motif obligatoire<textarea v-model="reason" maxlength="1000" required :disabled="busy"></textarea></label><button class="secondary" :disabled="busy||!ids.length||!setters.length||!reason.trim()" @click="preview">Prévisualiser sans enregistrer</button><section v-if="plan"><h4>Répartition proposée</h4><p v-for="item in plan.items" :key="item.id">{{label(item.id)}} → {{names[item.setter_id]||item.setter_id}}</p><p v-for="item in plan.counts" :key="item.setter_id">{{names[item.setter_id]||item.setter_id}} : {{item.count}} prospect(s)</p><p>La prévisualisation ne réserve rien. Les accès centraux et versions seront contrôlés à la confirmation. Tout le lot est enregistré ou refusé.</p><button class="primary" :disabled="busy||!reason.trim()" @click="confirm">Confirmer cette répartition</button></section><button class="secondary" :disabled="busy" @click="emit('changed')">Recharger les prospects</button></section></section></template>
