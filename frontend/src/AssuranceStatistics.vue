<script setup lang="ts">
import { ref, onMounted } from 'vue'
const props = defineProps<{
  role: string
  request: (path: string, body?: any, method?: string) => Promise<any>
}>()
const today = new Date(),
  from = ref(new Date(today.getTime() - 29 * 86400000).toISOString().slice(0, 10)),
  to = ref(today.toISOString().slice(0, 10)),
  page = ref(1),
  result = ref<any>(null),
  busy = ref(false),
  error = ref('')
const labels: Record<string, string> = {
  appointments: 'Rendez-vous',
  cancelled: 'Annulés',
  upcoming: 'À venir',
  reported: 'Comptes rendus',
  performed: 'Effectués (Oui)',
  not_performed: 'Non effectués (tous motifs)',
  absent: 'Absences déclarées',
  other_not_performed: 'Non effectués (autre motif)',
  reports_due: 'Comptes rendus manquants',
  problem_reports: 'Comptes rendus avec problème',
  incidents: 'Signalements ultérieurs',
  open_tasks: 'Tâches ouvertes',
  overdue_tasks: 'Tâches en retard',
  closed_tasks: 'Tâches clôturées',
  performed_rate: 'Taux effectué parmi les comptes rendus (%)',
}
async function load() {
  busy.value = true
  error.value = ''
  try {
    result.value = await props.request(
      `statistics/?from=${from.value}&to=${to.value}&page=${page.value}`,
    )
  } catch (e: any) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
async function download(kind: string) {
  busy.value = true
  error.value = ''
  try {
    const blob = await props.request(`statistics/?from=${from.value}&to=${to.value}&export=${kind}`)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `statistiques-assurance-${from.value}-${to.value}.${kind}`
    link.click()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
onMounted(load)
</script>
<!-- prettier-ignore -->
<template><section><h3>Statistiques opérationnelles Assurance</h3><p>{{role==='administrator'?'Vue globale et détail par setter.':'Vos rendez-vous et votre suivi uniquement.'}}</p><p v-if="error" role="alert">{{error}}</p><form @submit.prevent="page=1;load()"><label>Du (UTC)<input v-model="from" type="date" required></label><label>Au inclus (UTC)<input v-model="to" type="date" required></label><button class="primary" :disabled="busy">Calculer</button></form><button class="secondary" :disabled="busy" @click="download('xlsx')">Télécharger Excel</button><button class="secondary" :disabled="busy" @click="download('csv')">Télécharger CSV</button><p>Les exports utilisent les dates saisies ci-dessus et incluent tout le périmètre autorisé, au-delà de la page affichée.</p><template v-if="result"><p>{{result.definition}}</p><small>État calculé le {{new Date(result.as_of).toLocaleString('fr-FR')}}. Une reprogrammation peut déplacer un rendez-vous dans une autre période.</small><dl><template v-for="(label,key) in labels" :key="key"><dt>{{label}}</dt><dd>{{result.totals[key]===null?'Non calculable':result.totals[key]}}</dd></template></dl><div v-if="result.setters" class="table-scroll"><table><thead><tr><th>Setter</th><th>RDV</th><th>Oui</th><th>Non effectués</th><th>Absents</th><th>Autre motif</th><th>Compte rendu manquant</th><th>Tâches ouvertes</th><th>En retard</th><th>Taux effectué</th></tr></thead><tbody><tr v-for="row in result.setters.results" :key="row.setter_id"><td>{{row.setter_name}} ({{row.setter_id}})</td><td>{{row.appointments}}</td><td>{{row.performed}}</td><td>{{row.not_performed}}</td><td>{{row.absent}}</td><td>{{row.other_not_performed}}</td><td>{{row.reports_due}}</td><td>{{row.open_tasks}}</td><td>{{row.overdue_tasks}}</td><td>{{row.performed_rate===null?'—':row.performed_rate+' %'}}</td></tr></tbody></table><p>{{result.setters.count}} setter(s) · page {{page}}</p><button class="secondary" :disabled="busy||!result.setters.previous" @click="page--;load()">Précédent</button><button class="secondary" :disabled="busy||!result.setters.next" @click="page++;load()">Suivant</button></div><p>Les appels Phonetico, contrats et conversions commerciales ne sont pas encore comptabilisés.</p></template></section></template>
<style scoped>
dl {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) 1fr;
  gap: 12px;
  margin: 24px 0;
}
dd {
  margin: 0;
}
form {
  display: flex;
  gap: 12px;
  align-items: end;
  flex-wrap: wrap;
  margin: 20px 0;
}
</style>
