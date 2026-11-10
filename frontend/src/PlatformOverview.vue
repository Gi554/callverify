<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { ArrowRight, LogOut, RefreshCw } from 'lucide-vue-next';
import StatBars from './StatBars.vue';
import StatDonut from './StatDonut.vue';
import StatKpi from './StatKpi.vue';

const props = defineProps<{
  username: string;
  adminSpaces: string[];
  request: (path: string) => Promise<Overview>;
}>();
const emit = defineEmits<{ spaces: []; action: [space: string, section: string]; logout: [] }>();
type Overview = {
  memberships: { workspace: string; role: string; count: number }[];
  days: { day: string; assurance: number; isolation: number }[];
};
const data = ref<Overview>();
const busy = ref(false);
const error = ref('');
const spaces = [
  { key: 'assurance', label: 'Assurance', color: '#267664' },
  { key: 'isolation', label: 'Isolation', color: '#6b59b7' },
] as const;
const roles: Record<string, string> = {
  administrator: 'Administrateurs',
  setter: 'Setters',
  advisor: 'Conseillers',
  client: 'Clients',
};
const actions = [
  { key: 'users', label: 'Gérer les utilisateurs' },
  { key: 'invitations', label: 'Gérer les invitations' },
  { key: 'phone', label: 'Gérer les postes' },
  { key: 'rules', label: 'Ouvrir les règles d’appel' },
  { key: 'history', label: 'Consulter le journal des accès' },
];
const calls = computed(() =>
  (data.value?.days || []).reduce((total, day) => total + day.assurance + day.isolation, 0),
);
const memberships = computed(() =>
  (data.value?.memberships || []).reduce((total, row) => total + row.count, 0),
);
const accessSegments = computed(() =>
  spaces.map((space) => ({
    label: space.label,
    color: space.color,
    value: (data.value?.memberships || [])
      .filter((row) => row.workspace === space.key)
      .reduce((total, row) => total + row.count, 0),
  })),
);
async function load() {
  if (busy.value) return;
  busy.value = true;
  error.value = '';
  try {
    data.value = await props.request('platform-overview/');
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'La supervision est indisponible.';
  } finally {
    busy.value = false;
  }
}
onMounted(load);
</script>

<template>
  <div class="login-shell workspace-welcome">
    <header class="login-header">
      <a href="/crm" class="brand">Orvia<span class="brand-dot">.</span></a>
      <button type="button" class="workspace-signout" @click="emit('logout')">
        <LogOut :size="16" /> Se déconnecter
      </button>
    </header>
    <main class="platform-overview" :aria-busy="busy">
      <div class="platform-heading">
        <div>
          <small>SUPER ADMINISTRATION</small>
          <h1>Vue d’ensemble</h1>
          <p>{{ username }} · Activité et accès des espaces Assurance et Isolation</p>
        </div>
        <div class="platform-actions">
          <button type="button" class="secondary" :disabled="busy" @click="load">
            <RefreshCw :size="16" /> Actualiser
          </button>
          <button type="button" class="primary" @click="emit('spaces')">
            Mes espaces <ArrowRight :size="16" />
          </button>
        </div>
      </div>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-else-if="busy && !data" role="status">Chargement des indicateurs…</p>
      <template v-if="data">
        <div class="platform-grid">
          <StatKpi
            label="Accès actifs"
            :value="memberships"
            hint="Un compte peut avoir plusieurs accès."
          />
          <StatKpi
            label="Tentatives d’appel"
            :value="calls"
            hint="Sur les 30 derniers jours, heure du Québec."
          />
        </div>
        <div class="platform-charts">
          <StatBars title="Tentatives d’appel par espace" :days="data.days" :series="[...spaces]" />
          <StatDonut
            title="Répartition des accès actifs"
            :center="String(memberships)"
            caption="Accès actifs"
            :segments="accessSegments"
          />
        </div>
      </template>
      <div class="platform-grid">
        <section v-for="space in spaces" :key="space.key" class="platform-card">
          <h2>{{ space.label }}</h2>
          <dl v-if="data" class="platform-roles">
            <div
              v-for="row in data.memberships.filter((item) => item.workspace === space.key)"
              :key="row.role"
            >
              <dt>{{ roles[row.role] || row.role }}</dt>
              <dd>{{ row.count }}</dd>
            </div>
          </dl>
          <div v-if="adminSpaces.includes(space.key)" class="platform-actions">
            <button
              v-for="action in actions"
              :key="action.key"
              type="button"
              class="secondary"
              @click="emit('action', space.key, action.key)"
            >
              {{ action.label }} <ArrowRight :size="14" />
            </button>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>

<style scoped>
.platform-overview {
  width: min(1120px, calc(100% - 32px));
  margin: 36px auto;
  display: grid;
  gap: 20px;
}
.platform-heading,
.platform-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}
.platform-heading {
  justify-content: space-between;
}
.platform-heading h1,
.platform-card h2 {
  margin: 0.3em 0;
}
.platform-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr));
  gap: 16px;
}
.platform-charts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 430px), 1fr));
  gap: 16px;
}
.platform-card {
  padding: 20px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
}
.platform-roles > div {
  display: flex;
  justify-content: space-between;
  padding: 7px 0;
}
.platform-actions button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
</style>
