<script setup lang="ts">
import { ref, onMounted } from 'vue'
import AssuranceAgreementDocuments from './AssuranceAgreementDocuments.vue'
const props = defineProps<{
  contactId: number
  contactRevision: number
  leaseToken: string
  blocked: boolean
  request: (path: string, body?: any, method?: string) => Promise<any>
}>()
const emit = defineEmits<{ saved: [revision: number] }>()
const rows = ref<any[]>([]),
  page = ref(1),
  count = ref(0),
  busy = ref(false),
  error = ref(''),
  message = ref(''),
  editing = ref<any>(null),
  events = ref<any[]>([]),
  historyFor = ref<number | null>(null),
  historyPage = ref(1),
  historyCount = ref(0)
const form = ref({
  kind: 'mandate',
  reference: '',
  status: 'draft',
  starts_on: '',
  ends_on: '',
  reason: '',
})
const documentFor = ref<number | null>(null)
let requestId = crypto.randomUUID()
const base = () => `contacts/${props.contactId}/agreements/`
const labels: Record<string, string> = {
  draft: 'Brouillon',
  tracking: 'En suivi',
  archived: 'Archivé',
}
function changed() {
  requestId = crypto.randomUUID()
}
function reset() {
  editing.value = null
  form.value = {
    kind: 'mandate',
    reference: '',
    status: 'draft',
    starts_on: '',
    ends_on: '',
    reason: '',
  }
  changed()
}
async function load() {
  busy.value = true
  error.value = ''
  try {
    const result = await props.request(base() + `?page=${page.value}`)
    rows.value = result.results
    count.value = result.count
  } catch (e: any) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
function edit(row: any) {
  editing.value = row
  form.value = {
    kind: row.kind,
    reference: row.reference,
    status: row.status,
    starts_on: row.starts_on || '',
    ends_on: row.ends_on || '',
    reason: '',
  }
  changed()
}
async function save() {
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    const common = {
      token: props.leaseToken,
      contact_revision: props.contactRevision,
      reference: form.value.reference,
      status: form.value.status,
      starts_on: form.value.starts_on || null,
      ends_on: form.value.ends_on || null,
      reason: form.value.reason,
    }
    const result = await props.request(
      editing.value ? base() + `${editing.value.id}/edit/` : base(),
      editing.value
        ? { ...common, revision: editing.value.revision }
        : { ...common, kind: form.value.kind, request_id: requestId },
    )
    emit('saved', result.contact_revision)
    message.value = result.replayed
      ? 'Création déjà enregistrée ; état actuel chargé.'
      : 'Suivi administratif enregistré.'
    reset()
    await load()
    events.value = []
    historyFor.value = null
  } catch (e: any) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
async function history(row: any, resetPage = true) {
  busy.value = true
  error.value = ''
  if (resetPage) historyPage.value = 1
  events.value = []
  historyFor.value = row.id
  try {
    const result = await props.request(base() + `${row.id}/history/?page=${historyPage.value}`)
    events.value = result.results
    historyCount.value = result.count
  } catch (e: any) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
onMounted(load)
</script>
<!-- prettier-ignore -->
<template><section><h3>Mandats et contrats — registre administratif</h3><p>Réservé à l’administration. Brouillon, En suivi et Archivé décrivent le suivi interne : aucune signature, validité juridique ou modification du statut commercial ou des accès conseiller n’est déduite.</p><p v-if="error" role="alert">{{error}}</p><p v-if="message" role="status">{{message}}</p><form @submit.prevent="save"><fieldset :disabled="busy||blocked||!leaseToken"><legend>{{editing?'Modifier la référence '+editing.reference:'Ajouter un suivi'}}</legend><label>Type<select v-model="form.kind" :disabled="!!editing" @change="changed"><option value="mandate">Mandat</option><option value="contract">Contrat</option></select></label><label>Référence<input v-model="form.reference" maxlength="100" required @input="changed"></label><label>État de suivi<select v-model="form.status" @change="changed"><option v-for="(label,key) in labels" :key="key" :value="key">{{label}}</option></select></label><label>Date de début (facultative)<input v-model="form.starts_on" type="date" @input="changed"></label><label>Date de fin (facultative)<input v-model="form.ends_on" type="date" @input="changed"></label><label>Motif<textarea v-model="form.reason" maxlength="1000" required @input="changed"></textarea></label><button class="secondary">Enregistrer le suivi</button></fieldset></form><p v-if="!leaseToken">Prenez en charge la fiche pour créer ou modifier un suivi.</p><button v-if="editing" class="secondary" :disabled="busy" @click="reset">Annuler la modification</button><article v-for="row in rows" :key="row.id"><strong>{{row.kind==='mandate'?'Mandat':'Contrat'}} · {{row.reference}}</strong><p>{{labels[row.status]}} · {{row.starts_on||'Début non renseigné'}} → {{row.ends_on||'Fin non renseignée'}} · version {{row.revision}}</p><button class="secondary" :disabled="busy||blocked" @click="edit(row)">Modifier</button><button class="secondary" :disabled="busy" @click="history(row)">Historique</button><button class="secondary" :disabled="busy" @click="documentFor=documentFor===row.id?null:row.id">Pièces liées</button></article><AssuranceAgreementDocuments v-if="documentFor!==null" :key="documentFor" :contact-id="contactId" :agreement-id="documentFor" :contact-revision="contactRevision" :lease-token="leaseToken" :blocked="blocked||busy" :request="request" @saved="emit('saved',$event);load();events=[];historyFor=null"/><p v-if="!rows.length">Aucun suivi enregistré.</p><button class="secondary" :disabled="busy||page===1" @click="page--;load()">Précédent</button> Page {{page}} <button class="secondary" :disabled="busy||page*25>=count" @click="page++;load()">Suivant</button><button class="secondary" :disabled="busy" @click="load">Actualiser</button><section v-if="historyFor!==null"><h4>Historique du suivi {{historyFor}}</h4><article v-for="event in events" :key="event.id"><p>{{new Date(event.created_at).toLocaleString('fr-FR')}} · administrateur {{event.actor_id}} · {{event.reason}}</p><pre>{{JSON.stringify({avant:event.before,après:event.after},null,2)}}</pre></article><button class="secondary" :disabled="busy||historyPage===1" @click="historyPage--;history({id:historyFor},false)">Précédent</button> Page {{historyPage}} <button class="secondary" :disabled="busy||historyPage*25>=historyCount" @click="historyPage++;history({id:historyFor},false)">Suivant</button></section><p>Pièces liées disponibles via le bouton de chaque suivi. Signature et cycle contractuel définitif restent à cadrer.</p></section></template>
