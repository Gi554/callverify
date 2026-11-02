<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed } from 'vue';
import { Search } from 'lucide-vue-next';
import IsolationPageHeader from './IsolationPageHeader.vue';
import ProspectExport from './ProspectExport.vue';
const props = defineProps<{ workspace: string; request: (path: string) => Promise<any> }>();
const emit = defineEmits<{ open: [value: { id: number; mode: 'edit' }] }>();
const form = ref<Record<string, string>>({
  name: '',
  phone: '',
  owner_id: '',
  setter_id: '',
  target_id: '',
  campaign_id: '',
  appointment_id: '',
  contact_status: '',
  appointment_status: '',
  from_date: '',
  to_date: '',
});
const applied = ref<Record<string, string>>({}),
  data = ref<any>(null),
  page = ref(1),
  busy = ref(false),
  exporting = ref(false),
  error = ref('');
let version = 0;
const blocked = computed(() => busy.value || exporting.value);
const label = (list: any[], value: any) =>
  list?.find((item: any) => String(item.id) === String(value))?.name || value || '—';
const date = (value: string) =>
  new Intl.DateTimeFormat('fr-CA', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'America/Toronto',
  }).format(new Date(value));
async function load(reset = false) {
  if (reset) {
    page.value = 1;
    applied.value = Object.fromEntries(Object.entries(form.value).filter(([, value]) => value));
  }
  const current = ++version;
  busy.value = true;
  error.value = '';
  try {
    const result = await props.request(
      'admin-search/?' + new URLSearchParams({ ...applied.value, page: String(page.value) }),
    );
    if (current === version) data.value = result;
  } catch (e: any) {
    if (current === version) {
      data.value = null;
      error.value = e.message || 'Recherche indisponible.';
    }
  } finally {
    if (current === version) busy.value = false;
  }
}
function reset() {
  for (const key in form.value) form.value[key] = '';
  load(true);
}
onMounted(() => load());
onBeforeUnmount(() => version++);
</script>
<template>
  <div class="iso-page admin-search">
    <IsolationPageHeader
      title="Recherche avancée"
      subtitle="Retrouvez une fiche et son rendez-vous avec des critères combinés. Heure du Québec."
      :eyebrow="'ADMINISTRATION · ' + workspace.toUpperCase()"
      :busy="blocked"
      @refresh="load()"
    />
    <form class="iso-panel search-filters" @submit.prevent="load(true)">
      <label
        >Nom du prospect<input
          v-model="form.name"
          maxlength="250"
          :disabled="blocked"
          placeholder="Nom ou prénom" /></label
      ><label
        >Téléphone<input
          v-model="form.phone"
          maxlength="100"
          :disabled="blocked"
          placeholder="Numéro complet ou partiel"
      /></label>
      <label
        >Setter actuel<select v-model="form.owner_id" :disabled="blocked">
          <option value="">Tous</option>
          <option
            v-for="item in data?.options.setters || []"
            :key="item.id"
            :value="String(item.id)"
          >
            {{ item.name }}
          </option>
        </select></label
      >
      <label
        >Setter à la réservation<select v-model="form.setter_id" :disabled="blocked">
          <option value="">Tous</option>
          <option
            v-for="item in data?.options.setters || []"
            :key="item.id"
            :value="String(item.id)"
          >
            {{ item.name }}
          </option>
        </select></label
      >
      <label
        >{{ workspace === 'assurance' ? 'Conseiller du rendez-vous' : 'Client de la visite'
        }}<select v-model="form.target_id" :disabled="blocked">
          <option value="">Tous</option>
          <option
            v-for="item in data?.options.targets || []"
            :key="item.id"
            :value="String(item.id)"
          >
            {{ item.name }}
          </option>
        </select></label
      >
      <label
        >{{ workspace === 'assurance' ? 'Campagne / lot importé' : 'Campagne'
        }}<select v-model="form.campaign_id" :disabled="blocked">
          <option value="">Toutes</option>
          <option
            v-for="item in data?.options.campaigns || []"
            :key="item.id"
            :value="String(item.id)"
          >
            {{ item.name }}
          </option>
        </select></label
      >
      <label
        >Référence du rendez-vous<input
          v-model="form.appointment_id"
          type="number"
          min="1"
          :disabled="blocked"
      /></label>
      <label
        >Statut de la fiche<select v-model="form.contact_status" :disabled="blocked">
          <option value="">Tous</option>
          <option
            v-for="item in data?.options.contact_statuses || []"
            :key="item.id"
            :value="item.id"
          >
            {{ item.name }}
          </option>
        </select></label
      >
      <label
        >Résultat du rendez-vous<select v-model="form.appointment_status" :disabled="blocked">
          <option value="">Tous</option>
          <option
            v-for="item in data?.options.appointment_statuses || []"
            :key="item.id"
            :value="item.id"
          >
            {{ item.name }}
          </option>
        </select></label
      >
      <label
        >Début du rendez-vous : du<input
          v-model="form.from_date"
          type="date"
          :disabled="blocked" /></label
      ><label>Au inclus<input v-model="form.to_date" type="date" :disabled="blocked" /></label>
      <div class="search-actions">
        <button class="primary" :disabled="blocked"><Search :size="16" />Rechercher</button
        ><button type="button" class="secondary" :disabled="blocked" @click="reset">
          Réinitialiser
        </button>
      </div>
    </form>
    <p v-if="error" role="alert" class="error">{{ error }}</p>
    <section v-if="data" class="iso-panel">
      <header class="iso-panel-heading">
        <div>
          <h2>{{ data.count }} fiche(s) trouvée(s)</h2>
          <p>Les exports reprennent la dernière recherche appliquée, sur toutes ses pages.</p>
        </div>
        <ProspectExport
          :request="request"
          path="admin-search/"
          :filters="applied"
          :blocked="busy"
          :filename="'recherche-' + workspace"
          @busy="exporting = $event"
        />
      </header>
      <div class="search-table">
        <table>
          <thead>
            <tr>
              <th>Prospect</th>
              <th>Setter actuel</th>
              <th>Rendez-vous correspondant</th>
              <th>Résultat</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in data.results" :key="row.id">
              <td data-label="Prospect">
                <strong>{{ row.name || 'Fiche #' + row.id }}</strong
                ><small>{{ row.phone }} · #{{ row.id }}</small
                ><small>{{ label(data.options.contact_statuses, row.contact_status) }}</small>
              </td>
              <td data-label="Setter actuel">
                {{ row.owner_name || row.owner_id || 'Non attribué' }}
              </td>
              <td data-label="Rendez-vous">
                <template v-if="row.appointment_id"
                  ><strong>#{{ row.appointment_id }} · {{ date(row.starts_at) }}</strong
                  ><small>Setter : {{ row.setter_name || row.setter_id }}</small
                  ><small
                    >{{ workspace === 'assurance' ? 'Conseiller' : 'Client' }} :
                    {{ row.target_name || row.target_id }}</small
                  ></template
                ><span v-else>Aucun rendez-vous</span>
              </td>
              <td data-label="Résultat">
                {{ label(data.options.appointment_statuses, row.appointment_status) }}
              </td>
              <td data-label="Action">
                <button
                  class="secondary"
                  :disabled="blocked"
                  @click="emit('open', { id: row.id, mode: 'edit' })"
                >
                  Ouvrir la fiche
                </button>
              </td>
            </tr>
            <tr v-if="!data.results.length">
              <td colspan="5">Aucune fiche ne correspond à ces critères.</td>
            </tr>
          </tbody>
        </table>
      </div>
      <footer class="iso-pagination">
        <span>Page {{ page }}</span
        ><button
          class="secondary"
          :disabled="blocked || page === 1"
          @click="
            page--;
            load();
          "
        >
          Précédent</button
        ><button
          class="secondary"
          :disabled="blocked || page * 25 >= data.count"
          @click="
            page++;
            load();
          "
        >
          Suivant
        </button>
      </footer>
      <p class="search-definition">{{ data.definition }}</p>
    </section>
  </div>
</template>
<style scoped>
.search-filters {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}
.search-filters label {
  display: grid;
  gap: 8px;
  font-size: 12px;
}
.search-actions {
  display: flex;
  gap: 8px;
  align-items: end;
}
.search-table {
  overflow: auto;
}
.search-table table {
  width: 100%;
  border-collapse: collapse;
}
.search-table th,
.search-table td {
  padding: 14px;
  text-align: left;
  border-bottom: 1px solid #e3e9f3;
  font-size: 12px;
}
.search-table th {
  background: #f5f7fc;
  color: #687c95;
}
.search-table small {
  display: block;
  font-size: 11px;
  color: #73819a;
  margin-top: 5px;
}
.search-definition {
  font-size: 12px;
  line-height: 1.7;
  color: #65758d;
}
@media (max-width: 1000px) {
  .search-filters {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 650px) {
  .search-filters {
    grid-template-columns: 1fr;
  }
  .search-table thead {
    display: none;
  }
  .search-table tr {
    display: block;
    border: 1px solid #e3e9f3;
    border-radius: 14px;
    margin: 12px 0;
    padding: 12px;
  }
  .search-table td {
    display: block;
    padding: 9px 0;
    border: 0;
  }
  .search-table td:before {
    content: attr(data-label);
    display: block;
    font-size: 10px;
    color: #7e8ca2;
    margin-bottom: 6px;
  }
  .search-table td button {
    width: 100%;
  }
}
</style>
