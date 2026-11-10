<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { Activity, ArrowRight, ClipboardList, LogOut, RefreshCw } from 'lucide-vue-next';
import StatBars from './StatBars.vue';
import StatDonut from './StatDonut.vue';
import StatKpi from './StatKpi.vue';
import PlatformAccounts from './PlatformAccounts.vue';

const props = defineProps<{
  username: string;
  adminSpaces: string[];
  request: (path: string, body?: unknown) => Promise<any>;
}>();
const emit = defineEmits<{ spaces: []; action: [space: string, section: string]; logout: [] }>();
type Overview = {
  memberships: { workspace: string; role: string; count: number }[];
  days: { day: string; assurance: number; isolation: number }[];
  incidents: {
    calls: { workspace: string; state: string; count: number }[];
    mail: { workspace: string; status: string; count: number }[];
    technical?: {
      area: string;
      kind: string;
      status: number | null;
      count: number;
      last_seen: string;
    }[];
  };
  recent_actions: {
    id: number;
    action: string;
    workspace: string;
    actor: string;
    target: number;
    reason: string;
    created_at: string;
  }[];
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
const incidentLabels: Record<string, string> = {
  rejected: 'Appels refusés par le fournisseur',
  unknown: 'Appels au résultat technique inconnu',
  blocked: 'Appels bloqués par les règles',
  failed: 'Courriels en échec',
  expired: 'Courriels expirés',
};
const auditLabels: Record<string, string> = {
  'platform.suspend': 'Compte suspendu',
  'platform.reactivate': 'Compte réactivé',
  'platform.revoke_sessions': 'Sessions révoquées',
  'platform.grant_admin': 'Accès administrateur accordé',
  'platform.suspend_admin': 'Accès administrateur suspendu',
};
const auditDate = new Intl.DateTimeFormat('fr-CA', {
  dateStyle: 'short',
  timeStyle: 'short',
  timeZone: 'America/Toronto',
});
const incidentRows = computed(() => {
  const incidents = data.value?.incidents;
  if (!incidents) return [];
  return [
    ...incidents.calls.map((row) => ({
      key: `call-${row.workspace}-${row.state}`,
      area: row.workspace,
      label: incidentLabels[row.state],
      count: row.count,
      lastSeen: '',
    })),
    ...incidents.mail.map((row) => ({
      key: `mail-${row.workspace}-${row.status}`,
      area: row.workspace,
      label: incidentLabels[row.status],
      count: row.count,
      lastSeen: '',
    })),
    ...(incidents.technical || []).map((row) => ({
      key: `technical-${row.area}-${row.kind}-${row.status}`,
      area: row.area,
      label: row.status
        ? `HTTP ${row.status}`
        : row.kind === 'network'
          ? 'Connexion réseau'
          : 'Erreur d’interface',
      count: row.count,
      lastSeen: row.last_seen,
    })),
  ].sort((first, second) => second.count - first.count);
});
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
      <PlatformAccounts :request="request" @changed="load" />
      <section v-if="data" class="platform-card">
        <header class="section-heading">
          <span class="section-icon warning"><Activity :size="20" /></span>
          <div>
            <h2>Incidents observés</h2>
            <p>Appels, courriels et signalements techniques.</p>
          </div>
          <span class="area period">Dernières 24 h</span>
        </header>
        <ul v-if="incidentRows.length" class="incident-grid">
          <li v-for="row in incidentRows" :key="row.key">
            <span class="area" :class="row.area">{{
              spaces.find((space) => space.key === row.area)?.label || 'Portail'
            }}</span>
            <strong class="incident-count">{{ row.count }}</strong>
            <span>{{ row.label }}</span>
            <small v-if="row.lastSeen"
              >Dernier signalement {{ auditDate.format(new Date(row.lastSeen)) }}</small
            >
          </li>
        </ul>
        <p v-else class="panel-empty">Aucun incident enregistré sur la période.</p>
      </section>
      <section v-if="data" class="platform-card">
        <header class="section-heading">
          <span class="section-icon"><ClipboardList :size="20" /></span>
          <div>
            <h2>Journal du superadmin</h2>
            <p>Les 20 dernières actions sur les comptes et les accès. Heure du Québec.</p>
          </div>
        </header>
        <p v-if="!data.recent_actions.length" class="panel-empty">
          Les actions apparaîtront ici après leur confirmation.
        </p>
        <ol v-else class="audit-list">
          <li v-for="row in data.recent_actions" :key="row.id">
            <div>
              <strong>{{ auditLabels[row.action] || row.action }}</strong>
              <span>Compte #{{ row.target }} · Par {{ row.actor }}</span>
              <p>{{ row.reason }}</p>
            </div>
            <time :datetime="row.created_at">{{ auditDate.format(new Date(row.created_at)) }}</time>
          </li>
        </ol>
      </section>
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
.section-heading {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
.section-heading h2,
.section-heading p,
.audit-list p {
  margin: 0;
}
.section-heading p,
.audit-list span,
.audit-list time,
.incident-grid small {
  color: #526174;
  font-size: 0.85rem;
}
.section-icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 12px;
  color: #503b87;
  background: #eee9fa;
}
.section-icon.warning {
  color: #8a4218;
  background: #fff1e5;
}
.area {
  width: fit-content;
  padding: 4px 9px;
  border-radius: 999px;
  background: #edf1f5;
  color: #3b4b5f;
  font-size: 0.78rem;
  font-weight: 650;
}
.area.assurance {
  color: #195746;
  background: #e7f3ed;
}
.area.isolation {
  color: #503b87;
  background: #eee9fa;
}
.period {
  margin-left: auto;
}
.incident-grid,
.audit-list {
  list-style: none;
  padding: 0;
  margin: 18px 0 0;
}
.incident-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 210px), 1fr));
  gap: 12px;
}
.incident-grid li,
.panel-empty {
  border-radius: 12px;
  background: #f7f9fc;
  padding: 14px;
}
.incident-grid li,
.audit-list li > div {
  display: grid;
  gap: 5px;
}
.incident-count {
  color: #8a4218;
  font-size: 1.9rem;
  line-height: 1.15;
}
.audit-list li {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px 16px;
  padding: 12px 0;
  border-top: 1px solid #e2e8f0;
  overflow-wrap: anywhere;
}
.panel-empty {
  color: #526174;
  margin: 16px 0 0;
}
</style>
