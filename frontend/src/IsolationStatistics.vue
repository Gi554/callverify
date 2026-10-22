<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
const props = defineProps<{
  role?: string
  request: (path: string, body?: any, method?: string) => Promise<any>
}>()
const today = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'America/Toronto',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
}).format(new Date())
const mode = ref('week'),
  weekOf = ref(today),
  from = ref(today),
  to = ref(today),
  zone = ref('America/Toronto'),
  group = ref('setter'),
  page = ref(1)
const result = ref<any>(null),
  busy = ref(false),
  error = ref(''),
  applied = ref('')
const canCompare = computed(
  () =>
    ['administrator', 'client'].includes(props.role || '') ||
    !!result.value?.setters ||
    !!result.value?.closers,
)
const groups = computed(() => result.value?.[result.value.group + 's'])
const labels: Record<string, string> = {
  visits: 'Rendez-vous réservés',
  performed: 'Rendez-vous tenus',
  not_performed: 'Non tenus déclarés',
  closed: 'Ventes conclues déclarées',
  performed_rate: 'Présence / résultats renseignés (%)',
  closing_rate: 'Conclusion / rendez-vous tenus (%)',
  results_due: 'Résultats de tenue manquants',
  closure_unknown: 'Tenus : vente non renseignée',
  not_closed: 'Tenus : vente non conclue',
  cancelled: 'Annulés',
  upcoming: 'À venir',
  unassigned_closer: 'Sans closer attribué',
}
const columns = [
  'visits',
  'performed',
  'not_performed',
  'closed',
  'results_due',
  'closure_unknown',
  'performed_rate',
  'closing_rate',
]
function query() {
  return new URLSearchParams({
    ...(mode.value === 'week' ? { week_of: weekOf.value } : { from: from.value, to: to.value }),
    timezone: zone.value,
    group: group.value,
  }).toString()
}
const changed = computed(() => !!result.value && query() !== applied.value)
function number(value: any) {
  return value === null || value === undefined
    ? 'Non calculable'
    : new Intl.NumberFormat('fr-CA', { maximumFractionDigits: 1 }).format(value)
}
async function load(criteria = query(), target = 1) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    result.value = await props.request(`workspace-statistics/?${criteria}&page=${target}`)
    applied.value = criteria
    page.value = target
  } catch (e: any) {
    error.value = e.message
    result.value = null
  } finally {
    busy.value = false
  }
}
async function download(kind: string) {
  if (busy.value || !result.value) return
  busy.value = true
  error.value = ''
  try {
    const blob = await props.request(`workspace-statistics/?${applied.value}&export=${kind}`)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `statistiques-isolation-${result.value.from}-${result.value.to}.${kind}`
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (e: any) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
onMounted(() => load())
</script>
<!-- prettier-ignore -->
<template><section class="isolation-statistics"><header><h3>Performances Isolation</h3><p>Rendez-vous, présence et ventes déclarées dans votre périmètre.</p></header><p v-if="error" role="alert">{{error}}</p><form @submit.prevent="load()"><fieldset :disabled="busy" class="statistics-filters"><label>Période<select v-model="mode"><option value="week">Une semaine</option><option value="custom">Période personnalisée</option></select></label><label v-if="mode==='week'">Un jour de la semaine<input v-model="weekOf" type="date" required></label><template v-else><label>Du<input v-model="from" type="date" required></label><label>Au inclus<input v-model="to" type="date" required></label></template><label>Fuseau<select v-model="zone"><option value="America/Toronto">Toronto / Montréal</option><option value="America/Vancouver">Vancouver</option><option value="America/Halifax">Halifax</option><option value="UTC">UTC</option></select></label><label v-if="canCompare">Comparer par<select v-model="group"><option value="setter">Setter d’origine</option><option value="closer">Closer actuellement attribué</option></select></label><button class="primary">{{busy?'Calcul…':'Calculer'}}</button></fieldset></form><p v-if="changed" role="status">Filtres modifiés : cliquez sur Calculer. Les résultats et téléchargements restent ceux de la période affichée.</p><template v-if="result"><div class="statistics-period"><strong>{{result.from}} → {{result.to}}</strong><span>{{result.timezone}}</span><button class="secondary" :disabled="busy" @click="download('xlsx')">Télécharger Excel</button><button class="secondary" :disabled="busy" @click="download('csv')">Télécharger CSV</button></div><div class="statistics-cards"><article v-for="(label,key) in labels" :key="key"><span>{{label}}</span><strong>{{number(result.totals[key])}}</strong></article></div><p v-if="result.totals.closure_unknown">{{result.totals.closure_unknown}} rendez-vous tenu(s) sans résultat de vente : le taux de conclusion reflète les ventes déclarées à ce jour.</p><details><summary>Comprendre les calculs et les attributions</summary><p>{{result.definition}}</p><small>Calculé le {{new Date(result.as_of).toLocaleString('fr-FR')}}. Aucun appel n’est déclenché par ce rapport.</small></details><template v-if="groups"><h4>{{result.group==='closer'?'Par closer actuellement attribué':'Par setter d’origine'}}</h4><div class="table-scroll"><table><thead><tr><th>{{result.group==='closer'?'Closer':'Setter'}}</th><th v-for="key in columns" :key="key">{{labels[key]}}</th></tr></thead><tbody><tr v-for="row in groups.results" :key="row[result.group+'_id']??'none'"><td>{{row[result.group+'_name']||'Non attribué'}}<small v-if="row[result.group+'_id']">ID {{row[result.group+'_id']}}</small></td><td v-for="key in columns" :key="key">{{number(row[key])}}</td></tr><tr v-if="!groups.results.length"><td :colspan="columns.length+1">Aucun rendez-vous dans cette période.</td></tr></tbody></table></div><p>{{groups.count}} groupe(s) · page {{page}}</p><button class="secondary" :disabled="busy||!groups.previous" @click="load(applied,page-1)">Précédent</button><button class="secondary" :disabled="busy||!groups.next" @click="load(applied,page+1)">Suivant</button></template><p>Les exports contiennent toutes les lignes autorisées du regroupement affiché, au-delà de cette page. Ils ne contiennent ni coordonnées de prospects ni notes.</p></template></section></template>
<style scoped>
.isolation-statistics {
  color: #30425b;
}
.statistics-filters {
  border: 0;
  padding: 0;
  display: flex;
  gap: 14px;
  align-items: end;
  flex-wrap: wrap;
  margin: 20px 0;
}
.statistics-filters label {
  min-width: 160px;
  flex: 1;
}
.statistics-period {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  margin: 20px 0;
}
.statistics-period span {
  color: #7e88a0;
  font-size: 12px;
}
.statistics-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(185px, 1fr));
  gap: 12px;
  margin: 20px 0;
}
.statistics-cards article {
  background: #f5f7fd;
  border: 1px solid #e6eaf5;
  border-radius: 13px;
  padding: 18px;
}
.statistics-cards article:nth-child(3n + 2) {
  background: #f4f1fa;
}
.statistics-cards article:nth-child(3n) {
  background: #eff8f5;
}
.statistics-cards span {
  display: block;
  font-size: 12px;
  line-height: 1.5;
  color: #7b8499;
}
.statistics-cards strong {
  display: block;
  font-size: 26px;
  margin-top: 12px;
}
.isolation-statistics details {
  padding: 16px;
  border: 1px solid #e7eaf2;
  border-radius: 10px;
  margin: 18px 0;
  font-size: 12px;
  line-height: 1.8;
}
.isolation-statistics summary {
  cursor: pointer;
}
.isolation-statistics th {
  min-width: 105px;
}
.isolation-statistics p {
  font-size: 12px;
  line-height: 1.7;
}
</style>
