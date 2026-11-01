<script setup lang="ts">
import { ref, onMounted } from 'vue';
import IsolationStatistics from './IsolationStatistics.vue';
import IsolationVisits from './IsolationVisits.vue';
import SidePanel from './SidePanel.vue';
import IsolationPageHeader from './IsolationPageHeader.vue';
import {
  Search,
  FolderOpen,
  Users,
  Clock3,
  CircleCheck,
  ArrowUpRight,
  CalendarDays,
} from 'lucide-vue-next';
import { initials } from './isolation-visit-display';
const showStatistics = ref(false);
const props = defineProps<{
  portal: (path: string, body?: any) => Promise<any>;
  request: (path: string, body?: any, method?: string) => Promise<any>;
}>();
const visitsOpen = ref(false),
  visitsBusy = ref(false),
  visitsRef = ref<InstanceType<typeof IsolationVisits> | null>(null),
  dossierName = ref('');
const summary = ref<any>(null),
  rows = ref<any[]>([]),
  page = ref(1),
  count = ref(0),
  search = ref(''),
  prospect = ref<number | undefined>(undefined),
  busy = ref(false),
  error = ref('');
async function load() {
  busy.value = true;
  error.value = '';
  try {
    summary.value = await props.request('client-dashboard/');
    const data = await props.request(
      `client-prospects/?page=${page.value}&search=${encodeURIComponent(search.value)}`,
    );
    rows.value = data.results;
    count.value = data.count;
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
onMounted(load);
</script>
<template>
  <section class="iso-page">
    <IsolationPageHeader
      title="Mes fiches clients"
      subtitle="Vos dossiers, les échanges et la suite de chaque rendez-vous."
      eyebrow="MES DOSSIERS · ISOLATION"
      :busy="busy"
      @refresh="load"
    >
      <template #actions
        ><button class="secondary" @click="showStatistics = !showStatistics">
          {{ showStatistics ? 'Fermer les statistiques' : 'Statistiques' }}
        </button></template
      >
    </IsolationPageHeader>
    <section v-if="showStatistics" class="iso-panel">
      <IsolationStatistics role="client" :request="request" />
    </section>
    <div class="iso-metrics">
      <div class="iso-metric purple">
        <div>
          <span>Dossiers clients</span><strong>{{ count }}</strong
          ><small>{{ search ? 'Selon votre recherche' : 'Dans votre espace' }}</small>
        </div>
        <span class="iso-metric-icon"><Users :size="24" /></span>
      </div>
      <div class="iso-metric blue">
        <div>
          <span>Rendez-vous à venir</span><strong>{{ summary?.upcoming ?? '—' }}</strong
          ><small>Les prochaines rencontres</small>
        </div>
        <span class="iso-metric-icon"><CalendarDays :size="24" /></span>
      </div>
      <div class="iso-metric green">
        <div>
          <span>Résultats renseignés</span><strong>{{ summary?.reported ?? '—' }}</strong
          ><small>Votre suivi en un regard</small>
        </div>
        <span class="iso-metric-icon"><CircleCheck :size="24" /></span>
      </div>
    </div>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="summary?.results_due" class="iso-notice">
      <Clock3 :size="17" /><span
        ><strong>{{ summary.results_due }} résultat(s) attendent votre retour.</strong> Ouvrez une
        fiche pour compléter le résultat d’une visite.</span
      >
    </p>
    <section class="iso-panel">
      <header class="iso-panel-heading">
        <div>
          <h2>
            Votre carnet clients <span class="iso-counter">{{ count }}</span>
          </h2>
          <p>Ouvrez un dossier pour retrouver ses visites et sa qualification.</p>
        </div>
        <button
          class="iso-text-link"
          @click="
            prospect = undefined;
            visitsOpen = true;
          "
        >
          Toutes les visites <ArrowUpRight :size="15" />
        </button>
      </header>
      <form
        class="iso-toolbar"
        @submit.prevent="
          page = 1;
          load();
        "
      >
        <label class="iso-search"
          ><Search :size="17" /><input
            v-model="search"
            aria-label="Rechercher un dossier par nom"
            placeholder="Rechercher un client…"
          /><button class="iso-text-link" :disabled="busy">Rechercher</button></label
        ><span class="iso-toolbar-note"
          ><FolderOpen :size="14" />Vos dossiers, au même endroit</span
        >
      </form>
    </section>
    <div v-if="rows.length" class="iso-visits-grid iso-folders-grid">
      <article v-for="row in rows" :key="row.id" class="iso-folder-card">
        <div class="iso-folder-tab"><FolderOpen :size="17" /><span>DOSSIER CLIENT</span></div>
        <div class="iso-folder-identity">
          <span class="iso-avatar">{{ initials(row.name || 'Client') }}</span>
          <h3>{{ row.name || 'Prospect sans nom' }}</h3>
        </div>
        <p>{{ row.raw_phone || 'Téléphone non renseigné' }}</p>
        <small class="iso-folder-reference">{{ row.reference || 'Sans référence' }}</small>
        <button
          class="iso-card-open"
          :disabled="busy"
          @click="
            prospect = row.id;
            dossierName = row.name || 'Prospect sans nom';
            visitsOpen = true;
          "
        >
          Ouvrir la fiche <ArrowUpRight :size="17" />
        </button>
      </article>
    </div>
    <div v-else class="iso-empty">
      <span class="iso-empty-icon"><FolderOpen :size="26" /></span
      ><strong>{{ busy ? 'Chargement des dossiers…' : 'Aucun dossier à afficher' }}</strong>
      <p>
        {{
          search
            ? 'Essayez un autre nom dans votre recherche.'
            : 'Les fiches des prospects qui vous sont confiés apparaîtront ici.'
        }}
      </p>
    </div>
    <footer class="iso-pagination">
      <span>{{ count }} dossier(s) · page {{ page }}</span
      ><button
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
        Suivant
      </button>
    </footer>
    <SidePanel
      :open="visitsOpen"
      :title="prospect ? dossierName : 'Toutes mes visites'"
      eyebrow="FICHE CLIENT · ISOLATION"
      :close-disabled="visitsBusy"
      @request-close="visitsRef?.close()"
    >
      <IsolationVisits
        class="iso-detail"
        v-if="visitsOpen"
        ref="visitsRef"
        :key="prospect || 0"
        role="client"
        :prospect-id="prospect"
        :portal="portal"
        :request="request"
        @busy="visitsBusy = $event"
        @close="visitsOpen = false"
        @changed="load"
      />
    </SidePanel>
  </section>
</template>
