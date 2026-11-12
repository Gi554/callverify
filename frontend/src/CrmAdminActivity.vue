<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue';
import { RefreshCw, SlidersHorizontal } from 'lucide-vue-next';
import StatKpi from './StatKpi.vue';
const props = defineProps<{ workspace: string; request: (path: string) => Promise<any> }>();
const today = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'America/Toronto',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
}).format(new Date());
// Whole current month: appointments booked for the coming days must be counted too.
const [year, month] = today.split('-').map(Number);
const monthEnd = String(new Date(Date.UTC(year, month, 0)).getUTCDate()).padStart(2, '0');
const from = ref(today.slice(0, 8) + '01'),
  to = ref(today.slice(0, 8) + monthEnd),
  setter = ref(''),
  owner = ref(''),
  closer = ref(''),
  campaign = ref('');
const options = ref<Record<string, any[]>>({});
const result = ref<any>(null),
  busy = ref(false),
  error = ref('');
const assurance = computed(() => props.workspace === 'assurance');
const criteria = computed(() =>
  new URLSearchParams({
    from: from.value,
    to: to.value,
    ...(setter.value ? { setter_id: setter.value } : {}),
    ...(owner.value ? { [assurance.value ? 'advisor_id' : 'client_id']: owner.value } : {}),
    ...(closer.value && !assurance.value ? { closer_id: closer.value } : {}),
    ...(campaign.value ? { campaign_id: campaign.value } : {}),
  }).toString(),
);
const counters = computed(() => [
  { key: 'scheduled', label: 'Rendez-vous programmés' },
  { key: 'performed', label: 'Présentés' },
  { key: 'closed', label: 'Closés' },
  { key: 'not_closed', label: 'Non closés' },
  { key: 'not_performed', label: 'Non présentés' },
  { key: 'updates_due', label: 'En attente de mise à jour' },
  { key: 'pending_callbacks', label: 'Rappels en attente' },
]);
let generation = 0,
  disposed = false,
  interval: ReturnType<typeof setInterval> | undefined;
async function load() {
  const version = ++generation;
  busy.value = true;
  error.value = '';
  try {
    const data = await props.request(
      `${assurance.value ? 'statistics' : 'workspace-statistics'}/?${criteria.value}`,
    );
    if (!disposed && version === generation) {
      result.value = data;
      options.value = data.filter_options || {};
    }
  } catch (e: any) {
    if (!disposed && version === generation) {
      result.value = null;
      error.value = e.message || 'Activité indisponible.';
    }
  } finally {
    if (!disposed && version === generation) busy.value = false;
  }
}
watch(criteria, () => {
  result.value = null;
  void load();
});
onMounted(() => {
  void load();
  interval = setInterval(() => {
    if (!document.hidden && !busy.value) void load();
  }, 60000);
});
onBeforeUnmount(() => {
  disposed = true;
  generation++;
  if (interval) clearInterval(interval);
});
</script>
<template>
  <section class="admin-activity" aria-label="Pilotage de l’activité">
    <header>
      <div>
        <span class="activity-eyebrow"
          ><SlidersHorizontal :size="14" />PILOTAGE ·
          {{ assurance ? 'ASSURANCE' : 'ISOLATION' }}</span
        >
        <h2>L’activité de votre équipe</h2>
        <p>Les rendez-vous et les suivis, dans votre espace uniquement.</p>
      </div>
      <button class="secondary" :disabled="busy" aria-label="Actualiser l’activité" @click="load">
        <RefreshCw :size="15" />Actualiser
      </button>
    </header>
    <form class="activity-filters" @submit.prevent="load">
      <label>Du<input v-model="from" type="date" required :max="to" /></label
      ><label>Au<input v-model="to" type="date" required :min="from" /></label>
      <label
        >Setter<select v-model="setter">
          <option value="">Tous les setters</option>
          <option v-for="row in options?.setter_id || []" :key="row.id" :value="String(row.id)">
            {{ row.name }}
          </option>
          <option
            v-if="setter && !options?.setter_id?.some((r: any) => String(r.id) === setter)"
            :value="setter"
          >
            Setter sélectionné
          </option>
        </select></label
      >
      <label
        >{{ assurance ? 'Client / conseiller' : 'Client'
        }}<select v-model="owner">
          <option value="">{{ assurance ? 'Tous les conseillers' : 'Tous les clients' }}</option>
          <option
            v-for="row in options?.[assurance ? 'advisor_id' : 'client_id'] || []"
            :key="row.id"
            :value="String(row.id)"
          >
            {{ row.name }}
          </option>
        </select></label
      >
      <label v-if="!assurance"
        >Ancien représentant (historique)<select v-model="closer">
          <option value="">Tous les représentants</option>
          <option v-for="row in options?.closer_id || []" :key="row.id" :value="String(row.id)">
            {{ row.name }}
          </option>
        </select></label
      >
      <label
        >{{ assurance ? 'Campagne / lot importé' : 'Campagne'
        }}<select v-model="campaign">
          <option value="">Toutes les campagnes</option>
          <option v-for="row in options?.campaign_id || []" :key="row.id" :value="String(row.id)">
            {{ row.name }}
          </option>
        </select></label
      >
    </form>
    <p v-if="error" role="alert">
      {{ error }} <button class="secondary" @click="load">Réessayer</button>
    </p>
    <div class="activity-counters" :aria-busy="busy">
      <StatKpi
        v-for="counter in counters"
        :key="counter.key"
        :label="counter.label"
        :value="
          !result
            ? '—'
            : counter.key === 'pending_callbacks'
              ? result.pending_callbacks
              : (result.totals[counter.key] ?? '—')
        "
      />
    </div>
    <footer>
      <span v-if="result"
        >Mis à jour à
        {{
          new Intl.DateTimeFormat('fr-CA', {
            timeZone: 'America/Toronto',
            hour: '2-digit',
            minute: '2-digit',
          }).format(new Date(result.as_of))
        }}
        · Québec</span
      ><span v-else>{{ busy ? 'Chargement…' : 'Données indisponibles' }}</span
      ><span>Actualisation automatique chaque minute quand la page est visible.</span>
    </footer>
    <p class="activity-definition">
      Par défaut, le mois en cours en entier, rendez-vous à venir compris. Rendez-vous selon leur
      date de début ; rappels ouverts selon leur échéance sur la période. Une vente non renseignée
      reste à compléter, sans être classée comme perdue.
      {{ assurance ? 'Les campagnes correspondent aux lots importés Assurance.' : '' }}
    </p>
  </section>
</template>
<style scoped>
.admin-activity {
  background: #fff;
  border: 1px solid #e8e8f2;
  border-radius: 24px;
  padding: 24px;
  margin: 0 0 24px;
  color: #26364c;
  min-width: 0;
}
.admin-activity header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}
.admin-activity h2 {
  margin: 8px 0;
  font-size: 22px;
  letter-spacing: -0.6px;
}
.admin-activity p {
  font-size: 12px;
  color: #7a8699;
  line-height: 1.6;
}
.activity-eyebrow {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  font-size: 10px;
  letter-spacing: 1.3px;
  color: #8970c0;
  font-weight: 700;
}
.activity-filters {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin: 20px 0;
}
.activity-filters label {
  display: grid;
  gap: 6px;
  font-size: 11px;
  color: #657087;
}
.activity-filters input,
.activity-filters select {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  padding: 10px;
  border: 1px solid #e1e6f1;
  border-radius: 10px;
  background: #fbfcff;
  font: inherit;
  color: #344560;
}
.activity-counters {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.activity-counters > :nth-child(3n + 1) {
  background: #f1eafa;
}
.activity-counters > :nth-child(3n + 2) {
  background: #eaf2fe;
}
.activity-counters > :nth-child(3n) {
  background: #eaf6f1;
}
.admin-activity footer {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 16px;
  font-size: 10px;
  color: #8791a4;
}
.admin-activity .activity-definition {
  font-size: 10px;
  margin-bottom: 0;
}
@media (max-width: 1000px) {
  .activity-counters,
  .activity-filters {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 550px) {
  .admin-activity {
    padding: 16px;
    border-radius: 18px;
  }
  .admin-activity header {
    align-items: start;
  }
  .admin-activity header > button {
    font-size: 0;
    padding: 10px;
  }
  .admin-activity h2 {
    font-size: 19px;
  }
  .activity-filters {
    gap: 10px;
  }
  .activity-counters {
    gap: 8px;
  }
}
</style>
