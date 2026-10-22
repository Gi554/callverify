<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Download, FileUp, Plus, RefreshCw, Search, ShieldCheck, Table2 } from 'lucide-vue-next'

const props = defineProps<{
  request: (path: string, body?: any, method?: string) => Promise<any>
}>()
const tab = ref<'lists' | 'import' | 'results' | 'exports'>('lists'),
  loading = ref(false),
  error = ref('')
const campaigns = ref<any[]>([]),
  imports = ref<any[]>([]),
  results = ref<any[]>([]),
  exportsList = ref<any[]>([])
const selected = ref(''),
  search = ref(''),
  file = ref<File | null>(null),
  preview = ref<any>(null)
const draft = ref({ name: '', purpose: '', source: '', budget: 0 }),
  mapping = ref({ phone: '', name: '', reference: '' })
const lineLabel = (value: string) =>
  (
    ({ reachable: 'Joignable', unreachable: 'Non joignable', unknown: 'Indéterminée' }) as Record<
      string,
      string
    >
  )[value] || 'Indéterminée'
function message(value: any) {
  return value?.message || String(value || 'Une erreur est survenue')
}
async function run(work: () => Promise<void>) {
  loading.value = true
  error.value = ''
  try {
    await work()
  } catch (err: any) {
    error.value = message(err)
  } finally {
    loading.value = false
  }
}
async function load() {
  await run(async () => {
    const [campaignData, importData, resultData, exportData] = await Promise.all([
      props.request('qualification/'),
      props.request('qualification/imports/'),
      props.request('qualification/results/'),
      props.request('qualification/exports/'),
    ])
    campaigns.value = campaignData.results || campaignData
    imports.value = importData.results || importData
    results.value = resultData.results || resultData
    exportsList.value = exportData.results || exportData
    if (!selected.value && campaigns.value[0]) selected.value = String(campaigns.value[0].id)
  })
}
async function createCampaign() {
  await run(async () => {
    await props.request('qualification/', draft.value)
    draft.value = { name: '', purpose: '', source: '', budget: 0 }
    await load()
  })
}
async function upload() {
  await run(async () => {
    if (!selected.value || !file.value)
      throw new Error('Choisissez une liste et un fichier CSV ou XLSX')
    const body = new FormData()
    body.append('campaign', selected.value)
    body.append('file', file.value)
    preview.value = await props.request('qualification/imports/', body)
    const headers = preview.value.headers || []
    mapping.value = {
      phone: headers.find((value: string) => /phone|tel|num/i.test(value)) || headers[0] || '',
      name: headers.find((value: string) => /name|nom/i.test(value)) || '',
      reference: '',
    }
  })
}
async function confirm() {
  await run(async () => {
    if (!preview.value) throw new Error('Importez un fichier avant de confirmer')
    const payload: any = { phone: mapping.value.phone }
    if (mapping.value.name) payload.name = mapping.value.name
    if (mapping.value.reference) payload.reference = mapping.value.reference
    await props.request(`qualification/imports/${preview.value.id}/confirm/`, { mapping: payload })
    preview.value = null
    file.value = null
    tab.value = 'lists'
    await load()
  })
}
async function lookup(id: number) {
  await run(async () => {
    await props.request(`qualification/${id}/lookup/`, {})
    await load()
  })
}
async function exportResults() {
  await run(async () => {
    if (!selected.value) throw new Error('Choisissez une liste')
    await props.request('qualification/exports/', {
      campaign: Number(selected.value),
      format: 'xlsx',
    })
    tab.value = 'exports'
    await load()
  })
}
async function download(job: any) {
  await run(async () => {
    const blob = await props.request(`qualification/exports/${job.id}/download/`)
    const url = URL.createObjectURL(blob),
      link = document.createElement('a')
    link.href = url
    link.download = `qualification-isolation-${job.id}.${job.format}`
    document.body.appendChild(link)
    link.click()
    link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  })
}
function chooseFile(event: Event) {
  file.value = (event.target as HTMLInputElement).files?.[0] || null
}
onMounted(load)
</script>
<!-- prettier-ignore -->
<template>
 <section class="qualification">
  <header class="qualification-tabs"><button v-for="item in [{id:'lists',label:'Listes'},{id:'import',label:'Importer'},{id:'results',label:'Résultats'},{id:'exports',label:'Exports'}]" :key="item.id" :class="{active:tab===item.id}" @click="tab=item.id as any">{{item.label}}</button></header>
  <p class="qualification-intro"><ShieldCheck :size="16"/> Processus Isolation : importez, contrôlez avec Lookup, puis exploitez ou exportez les résultats. Aucun appel n’est lancé depuis cet écran.</p>
  <p v-if="error" class="error" role="alert">{{error}}</p>
  <div class="qualification-toolbar"><label class="search"><Search :size="16"/><input v-model="search" placeholder="Rechercher une liste…"></label><button class="secondary" :disabled="loading" @click="load"><RefreshCw :size="16" :class="{spin:loading}"/>Actualiser</button><button v-if="tab==='results'" class="primary" :disabled="loading||!selected" @click="exportResults"><Download :size="16"/>Exporter Excel</button></div>

  <template v-if="tab==='lists'">
   <form class="new-campaign" @submit.prevent="createCampaign"><label>Nom de la liste<input v-model.trim="draft.name" required maxlength="200" placeholder="Ex. Leads Québec – novembre"></label><label>Source<input v-model.trim="draft.source" maxlength="250" placeholder="Ex. Salon, formulaire, fichier client"></label><label>Budget Lookup (CAD)<input v-model.number="draft.budget" type="number" min="0" step="0.0001"></label><button class="primary" :disabled="loading"><Plus :size="16"/>Créer la liste</button></form>
   <div class="qualification-table"><table><thead><tr><th>Liste</th><th>Import / vérification</th><th>État</th><th>Budget</th><th></th></tr></thead><tbody><tr v-for="campaign in campaigns.filter(row=>row.name.toLowerCase().includes(search.toLowerCase()))" :key="campaign.id"><td><strong>{{campaign.name}}</strong><small>{{campaign.source||'Source non renseignée'}}</small></td><td><strong>{{campaign.progress.checked}} / {{campaign.progress.total}}</strong><small>{{campaign.progress.pending}} en attente · {{campaign.progress.errors}} erreur(s)</small><span class="progress"><i :style="{width:campaign.progress.percent+'%'}"></i></span></td><td><span :class="['crm-badge',campaign.status==='completed'?'positive':campaign.status==='active'?'warning':'neutral']">{{campaign.status==='draft'?'À préparer':campaign.status==='active'?'En cours':campaign.status==='completed'?'Terminé':campaign.status}}</span></td><td>{{campaign.spent}} / {{campaign.budget}}</td><td class="actions"><button class="text-button" :disabled="loading||!campaign.progress.total" @click="lookup(campaign.id)">Lancer Lookup</button><button class="text-button" @click="selected=String(campaign.id);tab='import'">Importer</button></td></tr><tr v-if="!campaigns.length"><td colspan="5">Créez une première liste pour démarrer le parcours de qualification.</td></tr></tbody></table></div>
  </template>

  <form v-else-if="tab==='import'" class="import-panel" @submit.prevent="preview?confirm():upload()"><h3><FileUp :size="20"/>Importer une liste dans Isolation</h3><p>Le fichier est aperçu avant tout traitement. Le contrôle Lookup ne démarrera qu’après votre action sur la liste.</p><label>Liste cible<select v-model="selected" required><option value="" disabled>Choisir une liste</option><option v-for="campaign in campaigns" :key="campaign.id" :value="String(campaign.id)">{{campaign.name}}</option></select></label><label v-if="!preview">Fichier CSV ou XLSX<input type="file" accept=".csv,.xlsx" required @change="chooseFile"></label><template v-else><p><strong>{{preview.rows}}</strong> ligne(s) détectée(s). Vérifiez les colonnes avant confirmation.</p><div class="mapping"><label>Numéro<select v-model="mapping.phone" required><option v-for="header in preview.headers" :key="header">{{header}}</option></select></label><label>Nom<select v-model="mapping.name"><option value="">— Aucun —</option><option v-for="header in preview.headers" :key="header">{{header}}</option></select></label><label>Référence<select v-model="mapping.reference"><option value="">— Aucune —</option><option v-for="header in preview.headers" :key="header">{{header}}</option></select></label></div><div class="preview"><Table2 :size="16"/><span v-for="row in preview.preview.slice(0,3)" :key="JSON.stringify(row)">{{row[mapping.phone]}}</span></div></template><button class="primary" :disabled="loading">{{preview?'Confirmer l’import':'Apercevoir le fichier'}}</button></form>

  <div v-else-if="tab==='results'" class="qualification-table"><table><thead><tr><th>Contact</th><th>Numéro</th><th>Validité</th><th>État de la ligne</th><th>Liste</th></tr></thead><tbody><tr v-for="row in results" :key="row.id"><td><strong>{{row.name||'Sans nom'}}</strong><small>{{row.reference||'—'}}</small></td><td>{{row.e164||row.raw_phone}}</td><td><span :class="['crm-badge',row.validity==='valid'?'positive':'negative']">{{row.validity==='valid'?'Format valide':'Format invalide'}}</span></td><td><span :class="['crm-badge',row.line_status==='reachable'?'positive':row.line_status==='unreachable'?'negative':'warning']">{{lineLabel(row.line_status)}}</span></td><td>{{row.campaign}}</td></tr><tr v-if="!results.length"><td colspan="5">Aucun résultat dans les listes Isolation.</td></tr></tbody></table></div>

  <div v-else class="qualification-table"><table><thead><tr><th>Liste</th><th>Format</th><th>État</th><th>Disponibilité</th><th></th></tr></thead><tbody><tr v-for="job in exportsList" :key="job.id"><td>{{job.campaign}}</td><td>{{job.format.toUpperCase()}}</td><td><span class="crm-badge neutral">{{job.status}}</span></td><td>{{job.expires_at?new Date(job.expires_at).toLocaleString('fr-FR'):'—'}}</td><td><button v-if="job.status==='completed'" class="text-button" :disabled="loading" @click="download(job)">Télécharger</button></td></tr><tr v-if="!exportsList.length"><td colspan="5">Aucun export demandé.</td></tr></tbody></table></div>
 </section>
</template>
<style scoped>
.qualification {
  min-height: 520px;
}
.qualification-tabs {
  display: flex;
  gap: 24px;
  border-bottom: 1px solid #dce4ee;
  padding: 0 20px;
}
.qualification-tabs button {
  background: transparent;
  border: 0;
  padding: 15px 1px 12px;
  color: #64748b;
  font-weight: 650;
  cursor: pointer;
}
.qualification-tabs button.active {
  color: #1676d2;
  border-bottom: 3px solid #1685e5;
}
.qualification-intro {
  display: flex;
  gap: 8px;
  align-items: center;
  background: #eff6ff;
  color: #37536f;
  padding: 12px 20px;
  margin: 0;
  font-size: 13px;
}
.qualification-toolbar {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 18px 20px;
  border-bottom: 1px solid #edf1f6;
}
.search {
  display: flex;
  align-items: center;
  gap: 7px;
  border: 1px solid #d9e1eb;
  border-radius: 5px;
  padding: 0 9px;
  min-width: 250px;
}
.search input {
  border: 0 !important;
  padding: 8px 0 !important;
  outline: 0;
  background: transparent;
}
.new-campaign {
  display: grid;
  grid-template-columns: 1.2fr 1fr 150px auto;
  gap: 12px;
  padding: 18px 20px;
  background: #f7f9fc;
  border-bottom: 1px solid #e2e9f2;
}
.new-campaign label,
.import-panel label,
.mapping label {
  display: grid;
  gap: 6px;
  font-size: 12px;
  font-weight: 650;
  color: #526579;
}
.new-campaign input,
.import-panel input,
.import-panel select {
  border: 1px solid #d5dfeb;
  border-radius: 5px;
  padding: 9px;
  background: white;
}
.qualification-table {
  overflow: auto;
}
.qualification-table table {
  border-collapse: collapse;
  width: 100%;
  min-width: 760px;
}
.qualification-table th {
  text-align: left;
  text-transform: none;
  font-size: 11px;
  font-weight: 650;
  color: #718096;
  background: #f6f9fc;
  padding: 13px 20px;
  border-bottom: 1px solid #dfe7f0;
}
.qualification-table td {
  padding: 14px 20px;
  border-bottom: 1px solid #edf1f5;
  font-size: 13px;
  vertical-align: middle;
}
.qualification-table small {
  display: block;
  color: #8291a3;
  margin-top: 4px;
}
.actions {
  white-space: nowrap;
}
.text-button {
  border: 0;
  background: transparent;
  color: #1474d3;
  padding: 5px;
  cursor: pointer;
  font-weight: 650;
  text-decoration: none;
}
.text-button:disabled {
  color: #9da9b7;
  cursor: not-allowed;
}
.progress {
  display: block;
  width: 150px;
  height: 4px;
  border-radius: 4px;
  background: #e3eaf3;
  margin-top: 7px;
}
.progress i {
  display: block;
  height: 100%;
  background: #2196e5;
  border-radius: 4px;
}
.import-panel {
  max-width: 720px;
  margin: 28px auto;
  padding: 28px;
  border: 1px solid #dce5ef;
  border-radius: 8px;
  display: grid;
  gap: 18px;
}
.import-panel h3 {
  display: flex;
  gap: 9px;
  align-items: center;
  margin: 0;
}
.import-panel p {
  color: #65758a;
  margin: 0;
  font-size: 13px;
}
.mapping {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.preview {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #526579;
  background: #f5f8fc;
  padding: 11px;
  overflow: auto;
  font-size: 12px;
}
.preview span {
  white-space: nowrap;
}
.crm-badge {
  display: inline-flex;
  padding: 4px 8px;
  border-radius: 14px;
  font-size: 11px;
  font-weight: 650;
}
.crm-badge.positive {
  background: #e5f7ed;
  color: #197649;
}
.crm-badge.negative {
  background: #fff0f0;
  color: #bd3f3f;
}
.crm-badge.warning {
  background: #fff5df;
  color: #9c6c16;
}
.crm-badge.neutral {
  background: #edf2f7;
  color: #586a80;
}
@media (max-width: 800px) {
  .new-campaign {
    grid-template-columns: 1fr;
  }
  .qualification-toolbar {
    justify-content: stretch;
    flex-wrap: wrap;
  }
  .search {
    min-width: 0;
    flex: 1;
  }
  .mapping {
    grid-template-columns: 1fr;
  }
  .qualification-tabs {
    overflow: auto;
    white-space: nowrap;
  }
}
</style>
