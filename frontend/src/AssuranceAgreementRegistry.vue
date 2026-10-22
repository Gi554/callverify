<script setup lang="ts">
import { ref, onMounted } from 'vue';
import AssuranceContactEditor from './AssuranceContactEditor.vue';
const props = defineProps<{
  request: (path: string, body?: any, method?: string) => Promise<any>;
  portal: (path: string, body?: any) => Promise<any>;
  initialDeadline?: string;
}>();
const emit = defineEmits<{ changed: [] }>();
const rows = ref<any[]>([]),
  page = ref(1),
  count = ref(0),
  busy = ref(false),
  error = ref(''),
  selected = ref<any>(null);
const deadlines = ref<any>(null),
  statistics = ref<any>(null),
  exporting = ref(false);
const filters = ref({
  deadline: props.initialDeadline || '',
  horizon_days: '30',
  search: '',
  kind: '',
  status: '',
  starts_from: '',
  starts_to: '',
  ends_from: '',
  ends_to: '',
});
const deadlineLabels: Record<string, string> = {
  overdue: 'Date de fin dépassée',
  upcoming: 'Échéance proche',
  undated: 'Date de fin manquante',
  later: 'Échéance ultérieure',
  not_tracked: 'Hors suivi',
};
const states: Record<string, string> = {
  draft: 'Brouillon',
  tracking: 'En suivi',
  archived: 'Archivé',
};
let lastRequest = 0;
async function load(reset = false) {
  if (reset) page.value = 1;
  const current = ++lastRequest;
  busy.value = true;
  error.value = '';
  rows.value = [];
  deadlines.value = null;
  statistics.value = null;
  try {
    const query = new URLSearchParams({ page: String(page.value) });
    for (const [key, value] of Object.entries(filters.value)) if (value) query.set(key, value);
    const result = await props.request(`agreement-registry/?${query}`);
    if (current !== lastRequest) return;
    rows.value = result.results;
    count.value = result.count;
    deadlines.value = result.deadlines;
    statistics.value = result.statistics;
  } catch (e: any) {
    if (current === lastRequest) {
      error.value = e.message;
      count.value = 0;
    }
  } finally {
    if (current === lastRequest) busy.value = false;
  }
}
async function open(row: any) {
  busy.value = true;
  error.value = '';
  try {
    selected.value = await props.request(`contacts/${row.contact.id}/`);
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
function clear() {
  filters.value = {
    deadline: '',
    horizon_days: '30',
    search: '',
    kind: '',
    status: '',
    starts_from: '',
    starts_to: '',
    ends_from: '',
    ends_to: '',
  };
  void load(true);
}
async function download() {
  exporting.value = true;
  error.value = '';
  try {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(filters.value)) if (value) query.set(key, value);
    const blob = await props.request(`agreement-registry/export/?${query}`);
    const url = URL.createObjectURL(blob);
    try {
      const link = document.createElement('a');
      link.href = url;
      link.download = 'mandats-contrats.xlsx';
      link.click();
    } finally {
      URL.revokeObjectURL(url);
    }
  } catch (e: any) {
    error.value = e.message;
  } finally {
    exporting.value = false;
  }
}
onMounted(() => load());
</script>
<template>
  <section>
    <h2>Mandats et contrats</h2>
    <p>
      Registre administratif Assurance. Les états de suivi ne constituent pas une signature ni une
      validation juridique.
    </p>
    <p v-if="error" role="alert">{{ error }}</p>
    <AssuranceContactEditor
      v-if="selected"
      :key="selected.id"
      :contact="selected"
      role="administrator"
      :request="request"
      :portal="portal"
      @close="
        selected = null;
        load();
      "
      @changed="
        load();
        emit('changed');
      "
    /><template v-else
      ><form @submit.prevent="load(true)">
        <fieldset :disabled="busy">
          <label
            >Référence ou nom du prospect<input v-model="filters.search" maxlength="250" /></label
          ><label
            >Type<select v-model="filters.kind">
              <option value="">Tous</option>
              <option value="mandate">Mandat</option>
              <option value="contract">Contrat</option>
            </select></label
          ><label
            >État<select v-model="filters.status">
              <option value="">Tous, y compris archivés</option>
              <option v-for="(label, key) in states" :key="key" :value="key">{{ label }}</option>
            </select></label
          ><label
            >Alerte d’échéance<select v-model="filters.deadline">
              <option value="">Toutes</option>
              <option value="upcoming">Échéance proche (En suivi)</option>
              <option value="overdue">Date de fin dépassée (En suivi)</option>
            </select></label
          ><label
            >Horizon<select v-model="filters.horizon_days">
              <option value="7">7 jours</option>
              <option value="30">30 jours</option>
              <option value="90">90 jours</option>
            </select></label
          ><label>Début à partir du<input v-model="filters.starts_from" type="date" /></label
          ><label>Début jusqu’au<input v-model="filters.starts_to" type="date" /></label
          ><label>Fin à partir du<input v-model="filters.ends_from" type="date" /></label
          ><label>Fin jusqu’au<input v-model="filters.ends_to" type="date" /></label>
          <p>
            Bornes incluses. Un filtre de date exclut les suivis dont cette date n’est pas
            renseignée.
          </p>
          <button class="secondary">Rechercher</button
          ><button type="button" class="secondary" @click="clear">Réinitialiser</button>
        </fieldset>
      </form>
      <section v-if="statistics" aria-label="Statistiques administratives">
        <h3>Synthèse des résultats filtrés</h3>
        <p>
          {{ statistics.total }} suivi(s) au {{ statistics.as_of }} (UTC), sur toutes les pages.
          Tous les filtres de la recherche appliquée, y compris l’alerte, sont pris en compte.
        </p>
        <h4>Par type</h4>
        <dl>
          <dt>Mandats</dt>
          <dd>{{ statistics.by_kind.mandate }}</dd>
          <dt>Contrats</dt>
          <dd>{{ statistics.by_kind.contract }}</dd>
        </dl>
        <h4>Par état</h4>
        <dl>
          <template v-for="(label, key) in states" :key="key"
            ><dt>{{ label }}</dt>
            <dd>{{ statistics.by_status[key] }}</dd></template
          >
        </dl>
        <h4>Par échéance · horizon {{ statistics.horizon_days }} jours</h4>
        <dl>
          <template v-for="(label, key) in deadlineLabels" :key="key"
            ><dt>{{ label }}</dt>
            <dd>{{ statistics.by_deadline[key] }}</dd></template
          >
        </dl>
        <p>
          Hors suivi regroupe brouillons et archivés. Les autres catégories concernent uniquement
          les suivis En suivi. Ces nombres ne constituent pas des conversions commerciales ou une
          validation juridique.
        </p>
      </section>
      <p v-if="deadlines" role="status">
        Au {{ deadlines.as_of }} (UTC), parmi les résultats des filtres hors alerte :
        {{ deadlines.overdue }} date(s) dépassée(s), {{ deadlines.upcoming }} échéance(s) dans les
        {{ deadlines.horizon_days }} jours, {{ deadlines.undated }} suivi(s) sans date de fin. Seuls
        les états En suivi sont signalés. Aucune clôture automatique.
      </p>
      <button class="secondary" :disabled="busy || exporting" @click="download">
        {{ exporting ? 'Export en cours…' : 'Télécharger Excel' }}
      </button>
      <p>
        L’export reprend les filtres saisis ci-dessus et tous les résultats correspondants, au-delà
        de la page affichée. Maximum 10 000 suivis ; précisez les filtres au-delà.
      </p>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Référence</th>
              <th>Prospect</th>
              <th>Type</th>
              <th>État</th>
              <th>Début</th>
              <th>Fin</th>
              <th>Échéance</th>
              <th>Pièces liées</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="row.id">
              <td>{{ row.reference }}</td>
              <td>{{ row.contact.name || 'Sans nom' }} · réf. {{ row.contact.id }}</td>
              <td>{{ row.kind === 'mandate' ? 'Mandat' : 'Contrat' }}</td>
              <td>{{ states[row.status] }}</td>
              <td>{{ row.starts_on || 'Non renseigné' }}</td>
              <td>{{ row.ends_on || 'Non renseigné' }}</td>
              <td>
                <span :class="['deadline-badge', row.deadline_state]">{{
                  deadlineLabels[row.deadline_state]
                }}</span
                ><small v-if="row.deadline_state === 'upcoming'">{{
                  row.days_to_end === 0 ? 'Aujourd’hui' : 'Dans ' + row.days_to_end + ' jour(s)'
                }}</small
                ><small v-if="row.deadline_state === 'overdue'"
                  >Depuis {{ -row.days_to_end }} jour(s)</small
                >
              </td>
              <td>{{ row.document_count }}</td>
              <td>
                <button class="secondary" :disabled="busy" @click="open(row)">
                  Ouvrir la fiche
                </button>
              </td>
            </tr>
            <tr v-if="!rows.length">
              <td colspan="9">{{ busy ? 'Chargement…' : 'Aucun suivi correspondant.' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p>
        {{ count }} suivi(s) · page {{ page }} ·
        {{ filters.deadline ? 'ordre des dates de fin' : 'ordre des dernières modifications' }}
      </p>
      <button
        class="secondary"
        :disabled="busy || page === 1"
        @click="
          page--;
          load();
        "
      >
        Précédent</button
      ><button
        class="secondary"
        :disabled="busy || page * 25 >= count"
        @click="
          page++;
          load();
        "
      >
        Suivant</button
      ><button class="secondary" :disabled="busy" @click="load()">Actualiser</button></template
    >
  </section>
</template>

<style scoped>
.deadline-badge {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 6px;
  background: #eef0e8;
  color: #4c5340;
}
.deadline-badge.overdue {
  background: #fde9e5;
  color: #8a281d;
}
.deadline-badge.upcoming {
  background: #fff0d1;
  color: #755019;
}
.deadline-badge.undated {
  background: #ece9fa;
  color: #57448a;
}
small {
  display: block;
  margin-top: 4px;
}
</style>
