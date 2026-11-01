<script setup lang="ts">
import { ref, onMounted } from 'vue';
import {
  CalendarDays,
  CircleCheck,
  Clock3,
  ArrowUpRight,
  Users,
  Bell,
  Leaf,
  ChevronRight,
} from 'lucide-vue-next';
import IsolationPageHeader from './IsolationPageHeader.vue';
import IsolationVisitCard from './IsolationVisitCard.vue';
const props = defineProps<{
  summary: any;
  username: string;
  request: (path: string) => Promise<any>;
}>();
const emit = defineEmits<{ navigate: [id: string]; refresh: []; open: [id: number] }>();
const upcoming = ref<any[]>([]),
  loading = ref(false),
  error = ref(''),
  personalCount = ref<number | null>(null);
async function load() {
  if (loading.value) return;
  loading.value = true;
  error.value = '';
  const results = await Promise.allSettled([
    props.request('visits/?period=upcoming&page_size=3'),
    props.request('client-follow-ups/?page=1'),
  ]);
  if (results[0].status === 'fulfilled') upcoming.value = results[0].value.results;
  else
    error.value =
      results[0].reason?.message || 'Les prochains rendez-vous ne sont pas disponibles.';
  personalCount.value = results[1].status === 'fulfilled' ? results[1].value.count : null;
  loading.value = false;
}
function refresh() {
  emit('refresh');
  load();
}
onMounted(load);
</script>
<template>
  <section class="iso-page iso-client-home">
    <IsolationPageHeader
      title="Votre équipe, vos rendez-vous"
      subtitle="Bienvenue dans votre espace. Tout est là pour préparer la suite."
      :busy="loading"
      @refresh="refresh"
    />
    <div class="iso-metrics">
      <button class="iso-metric blue" @click="emit('navigate', 'appointments')">
        <div>
          <span>Rendez-vous à venir</span><strong>{{ summary.upcoming ?? '—' }}</strong
          ><small>Les prochaines rencontres</small>
        </div>
        <span class="iso-metric-icon"><CalendarDays :size="25" /></span>
      </button>
      <button class="iso-metric peach" @click="emit('navigate', 'visit-history')">
        <div>
          <span>Résultats à compléter</span><strong>{{ summary.results_due ?? '—' }}</strong
          ><small>Votre retour fait la différence</small>
        </div>
        <span class="iso-metric-icon"><Clock3 :size="25" /></span>
      </button>
      <button class="iso-metric green" @click="emit('navigate', 'visit-history')">
        <div>
          <span>Résultats renseignés</span><strong>{{ summary.reported ?? '—' }}</strong
          ><small>Des dossiers qui avancent</small>
        </div>
        <span class="iso-metric-icon"><CircleCheck :size="25" /></span>
      </button>
    </div>
    <div class="iso-home-grid">
      <section class="iso-panel">
        <header class="iso-panel-heading">
          <div>
            <h2>La suite, en un coup d’œil</h2>
            <p>Vos dossiers et les actions qui vous attendent.</p>
          </div>
          <span class="iso-quick-icon"><Leaf :size="20" /></span>
        </header>
        <div class="iso-quick-actions">
          <button @click="emit('navigate', 'contacts')">
            <span class="iso-quick-icon"><Users :size="18" /></span
            ><span
              ><strong>Mes fiches clients</strong
              ><small
                >{{ summary.prospects ?? '—' }} dossiers · coordonnées et historique</small
              ></span
            ><ChevronRight :size="16" />
          </button>
          <button @click="emit('navigate', 'personal-followups')">
            <span class="iso-quick-icon"><Clock3 :size="18" /></span
            ><span
              ><strong>Mes relances personnelles</strong
              ><small>{{
                personalCount === null
                  ? 'Dates et notes de rappel'
                  : personalCount + ' relance(s) dans votre espace'
              }}</small></span
            ><ChevronRight :size="16" />
          </button>
          <button @click="emit('navigate', 'missing-updates')">
            <span class="iso-quick-icon"><Bell :size="18" /></span
            ><span
              ><strong>Rendez-vous sans mise à jour</strong
              ><small
                >{{ summary.missing_updates ?? '—' }} résultats attendus depuis plus de 24 h</small
              ></span
            ><ChevronRight :size="16" />
          </button>
        </div>
      </section>
      <aside class="iso-home-feature">
        <span>LE BON RÉFLEXE</span>
        <h2>Une visite terminée ?<br />Gardez votre équipe<br />dans la boucle.</h2>
        <p>Confirmez la présence, partagez le résultat et choisissez la prochaine action.</p>
        <button @click="emit('navigate', 'visit-history')">
          Compléter mes résultats <ArrowUpRight :size="17" /></button
        ><Leaf class="iso-welcome-art" :size="170" />
      </aside>
    </div>
    <section class="iso-panel">
      <header class="iso-panel-heading">
        <div>
          <h2>Vos prochains rendez-vous</h2>
          <p>Des rencontres à préparer, à l’heure du Québec.</p>
        </div>
        <button class="iso-text-link" @click="emit('navigate', 'appointments')">
          Tout voir<ArrowUpRight :size="15" />
        </button>
      </header>
      <p v-if="error" role="alert">{{ error }}</p>
      <div v-if="upcoming.length" class="iso-visits-grid">
        <IsolationVisitCard
          v-for="row in upcoming"
          :key="row.id"
          :visit="row"
          @open="emit('open', row.id)"
        />
      </div>
      <div v-else-if="!error" class="iso-empty">
        <span class="iso-empty-icon"><CalendarDays :size="26" /></span
        ><strong>{{
          loading
            ? 'Chargement de vos rendez-vous…'
            : 'Un peu de place pour les prochaines rencontres'
        }}</strong>
        <p>Les rendez-vous transmis par vos setters apparaîtront ici.</p>
        <button v-if="!loading" class="secondary" @click="emit('navigate', 'isolation-agenda')">
          Voir mon agenda <ArrowUpRight :size="15" />
        </button>
      </div>
    </section>
  </section>
</template>
