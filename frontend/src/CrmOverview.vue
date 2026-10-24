<script setup lang="ts">
import { computed, ref, onMounted } from 'vue';
import {
  Users,
  ListTodo,
  CalendarCheck,
  ArrowUpRight,
  PhoneCall,
  UserRoundCheck,
  ArrowRight,
  RefreshCw,
  Sparkles,
  Clock3,
  BarChart3,
} from 'lucide-vue-next';
const props = defineProps<{
  workspace: string;
  role: string;
  summary: any;
  username: string;
  request: (path: string) => Promise<any>;
}>();
defineEmits<{ navigate: [value: string]; refresh: [] }>();
const assurance = computed(() => props.workspace === 'assurance');
const metrics = computed(() => [
  {
    label: assurance.value ? 'Contacts dans votre périmètre' : 'Prospects dans votre périmètre',
    value: props.summary.contacts ?? props.summary.prospects ?? 0,
    icon: Users,
    tone: 'olive',
  },
  assurance.value
    ? {
        label: props.role === 'advisor' ? 'Comptes rendus attendus' : 'Tâches de suivi ouvertes',
        value: props.role === 'advisor' ? props.summary.reports_due : props.summary.open_follow_ups,
        icon: props.role === 'advisor' ? CalendarCheck : ListTodo,
        tone: 'purple',
      }
    : {
        label: props.role === 'client' ? 'Visites à venir' : 'Rappels arrivés à échéance',
        value: props.role === 'client' ? props.summary.upcoming : props.summary.callbacks_due,
        icon: props.role === 'client' ? CalendarCheck : PhoneCall,
        tone: 'purple',
      },
  ...(!assurance.value && props.role === 'administrator'
    ? [
        {
          label: 'Prospects sans affectation',
          value: props.summary.unassigned,
          icon: UserRoundCheck,
          tone: 'orange',
        },
      ]
    : []),
]);
const upcoming = ref<any[]>([]),
  loading = ref(true),
  error = ref('');
async function loadUpcoming() {
  loading.value = true;
  error.value = '';
  try {
    const data = await props.request(
      assurance.value
        ? 'appointments/?period=upcoming&status=scheduled'
        : 'visits/?period=upcoming',
    );
    upcoming.value = data.results.filter((row: any) => row.status === 'scheduled').slice(0, 3);
  } catch (e: any) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}
function date(row: any) {
  return new Intl.DateTimeFormat('fr-FR', {
    timeZone: row.timezone || 'America/Toronto',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(row.starts_at));
}
const activity = ref<any>(null),
  activityError = ref(''),
  activityLoading = ref(false);
let activityVersion = 0;
async function loadActivity() {
  if (!assurance.value || props.role !== 'setter') return;
  const version = ++activityVersion;
  activityLoading.value = true;
  activityError.value = '';
  try {
    const data = await props.request('statistics/');
    if (version === activityVersion) activity.value = data;
  } catch (e: any) {
    if (version === activityVersion) {
      activity.value = null;
      activityError.value = e.message;
    }
  } finally {
    if (version === activityVersion) activityLoading.value = false;
  }
}
const bars = computed(() =>
  activity.value
    ? [
        { label: 'Effectués', value: activity.value.totals.performed, color: '#8c6df2' },
        { label: 'Non effectués', value: activity.value.totals.not_performed, color: '#b39bf4' },
        { label: 'Annulés', value: activity.value.totals.cancelled, color: '#d4c5fa' },
        { label: 'À venir', value: activity.value.totals.upcoming, color: '#a4c5f3' },
      ]
    : [],
);
const barMax = computed(() => Math.max(1, ...bars.value.map((b) => b.value)));
const activityPeriod = computed(() =>
  activity.value
    ? `${activity.value.from.split('-').reverse().join('/')} – ${activity.value.to.split('-').reverse().join('/')}`
    : '30 derniers jours',
);
const admin = computed(() => props.role === 'administrator');
// Isolation exposes no task summary endpoint: open tasks come from the dashboard summary.
const teamTasks = ref<{ open: number | null; overdue: number } | null>(null),
  teamTasksLoading = ref(false),
  teamTasksError = ref('');
const teamOpen = computed(() =>
  assurance.value ? teamTasks.value?.open : props.summary.open_follow_ups,
);
let teamTasksVersion = 0;
async function loadTeamTasks() {
  if (!admin.value) return;
  const version = ++teamTasksVersion;
  teamTasksLoading.value = true;
  teamTasksError.value = '';
  try {
    let counts: { open: number | null; overdue: number };
    if (assurance.value) {
      const data = await props.request('follow-ups/summary/');
      counts = { open: data.open, overdue: data.overdue };
    } else {
      const data = await props.request('follow-ups/?state=overdue');
      counts = { open: null, overdue: data.count };
    }
    if (version === teamTasksVersion) teamTasks.value = counts;
  } catch (e: any) {
    if (version === teamTasksVersion) {
      teamTasks.value = null;
      teamTasksError.value = e.message;
    }
  } finally {
    if (version === teamTasksVersion) teamTasksLoading.value = false;
  }
}
function refreshHome() {
  void loadUpcoming();
  void loadActivity();
  void loadTeamTasks();
}
onMounted(refreshHome);
</script>
<template>
  <section v-if="role === 'setter'" class="setter-homepage">
    <div class="home-topline">
      <span class="home-workspace"
        ><span></span>{{ assurance ? 'Assurance' : 'Isolation' }} · Mon espace</span
      ><button
        class="home-refresh"
        :disabled="loading || activityLoading"
        @click="
          $emit('refresh');
          refreshHome();
        "
      >
        <RefreshCw :size="15" />Actualiser
      </button>
    </div>
    <div class="home-hero">
      <div class="home-main-snapshot">
        <header class="home-welcome">
          <h1>Bonjour {{ username }} <span aria-hidden="true">✦</span></h1>
          <p>Une vue claire sur votre journée. À vous de jouer.</p>
        </header>
        <div class="home-highlights">
          <button class="home-highlight peach" @click="$emit('navigate', 'contacts')">
            <span class="highlight-label">Mes prospects</span
            ><small>Vos fiches, au même endroit</small
            ><Users class="metric-decoration" :size="40" /><strong>{{
              summary.contacts ?? summary.prospects ?? 0
            }}</strong
            ><span class="metric-arrow"><ArrowUpRight :size="21" /></span>
          </button>
          <button
            class="home-highlight blue"
            @click="$emit('navigate', assurance ? 'followups' : 'contacts')"
          >
            <span class="highlight-label">{{
              assurance ? 'Tâches ouvertes' : 'Rappels à traiter'
            }}</span
            ><small>Les prochaines actions</small
            ><ListTodo class="metric-decoration" :size="40" /><strong>{{
              (assurance ? summary.open_follow_ups : summary.callbacks_due) ?? 0
            }}</strong
            ><span class="metric-arrow"><ArrowUpRight :size="21" /></span>
          </button>
          <button class="home-highlight lilac" @click="$emit('navigate', 'appointments')">
            <span class="highlight-label">Prochain {{ assurance ? 'rendez-vous' : 'créneau' }}</span
            ><small>Gardez le fil de votre agenda</small
            ><CalendarCheck class="metric-decoration" :size="40" /><strong class="next-slot">{{
              loading
                ? 'Chargement…'
                : error
                  ? 'Indisponible'
                  : upcoming.length
                    ? date(upcoming[0])
                    : 'À organiser'
            }}</strong
            ><span class="metric-arrow"><ArrowUpRight :size="21" /></span>
          </button>
        </div>
      </div>
      <aside class="home-hero-side">
        <button
          class="home-status-pill dark"
          @click="$emit('navigate', assurance ? 'followups' : 'contacts')"
        >
          <span class="pill-icon"><Clock3 :size="19" /></span
          ><span
            ><strong
              >{{ (assurance ? summary.open_follow_ups : summary.callbacks_due) ?? 0 }}
              {{ assurance ? 'tâche(s)' : 'rappel(s)' }}</strong
            ><small>À traiter</small></span
          ><ArrowUpRight :size="19" /></button
        ><button class="home-status-pill" @click="$emit('navigate', 'appointments')">
          <span class="pill-icon"><CalendarCheck :size="19" /></span
          ><span><strong>Mon agenda</strong><small>Rendez-vous et disponibilités</small></span
          ><ArrowUpRight :size="19" />
        </button>
        <button class="home-feature" @click="$emit('navigate', 'contacts')">
          <span class="feature-tag"><Sparkles :size="13" />LE BON RÉFLEXE</span
          ><strong>Votre prochain échange<br />commence ici.</strong
          ><span>Retrouver mes prospects <ArrowUpRight :size="19" /></span>
        </button>
      </aside>
    </div>
    <div class="home-body">
      <div class="home-left">
        <section v-if="assurance" class="home-panel home-performance">
          <header class="panel-heading">
            <div>
              <h2>Mes rendez-vous en un regard</h2>
              <p>{{ activityPeriod }} · dates en UTC</p>
            </div>
            <button
              class="round-link"
              aria-label="Ouvrir mes statistiques"
              @click="$emit('navigate', 'statistics')"
            >
              <ArrowUpRight :size="18" />
            </button>
          </header>
          <p v-if="activityLoading" role="status" class="panel-feedback">
            Chargement des statistiques…
          </p>
          <div v-else-if="activityError" class="panel-feedback" role="alert">
            <p>{{ activityError }}</p>
            <button class="home-refresh" @click="loadActivity">Réessayer</button>
          </div>
          <div v-else-if="activity" class="performance-content">
            <div class="performance-total">
              <span>Rendez-vous sur la période</span
              ><strong>{{ activity.totals.appointments }}</strong
              ><small>{{ activity.totals.reported }} compte(s) rendu(s)</small>
            </div>
            <div
              class="home-chart"
              role="img"
              :aria-label="bars.map((b) => `${b.label} : ${b.value}`).join(', ')"
            >
              <div v-for="bar in bars" :key="bar.label" class="chart-column">
                <span class="bar-value">{{ bar.value }}</span>
                <div class="bar-track">
                  <span
                    :style="{ height: `${(bar.value / barMax) * 100}%`, background: bar.color }"
                  ></span>
                </div>
                <span class="bar-label">{{ bar.label }}</span>
              </div>
            </div>
          </div>
          <p v-if="activity && !activityLoading && !activityError" class="chart-caption">
            Selon la date du rendez-vous. Les rendez-vous passés sans compte rendu ne sont pas
            classés comme effectués.
          </p>
        </section>
        <section class="home-panel home-agenda">
          <header class="panel-heading">
            <div>
              <h2>{{ assurance ? 'Mes prochains rendez-vous' : 'Mes prochaines visites' }}</h2>
              <p>Les trois prochains créneaux prévus</p>
            </div>
            <CalendarCheck :size="21" />
          </header>
          <p v-if="loading" class="panel-feedback" role="status">Chargement de votre agenda…</p>
          <div v-else-if="error" class="panel-feedback" role="alert">
            <p>{{ error }}</p>
            <button class="home-refresh" @click="loadUpcoming">Réessayer</button>
          </div>
          <div v-else-if="!upcoming.length" class="agenda-empty">
            <span><CalendarCheck :size="24" /></span>
            <div>
              <h3>La suite reste à écrire</h3>
              <p>Aucun {{ assurance ? 'rendez-vous' : 'créneau' }} à venir pour le moment.</p>
            </div>
          </div>
          <div v-else class="agenda-table-wrap">
            <table class="home-agenda-table">
              <thead>
                <tr>
                  <th>Prospect</th>
                  <th>Date et heure</th>
                  <th>Fuseau</th>
                  <th>Statut</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in upcoming" :key="row.id">
                  <td>
                    {{ (assurance ? row.contact : row.prospect)?.name || 'Dossier sans nom' }}
                  </td>
                  <td>
                    <time>{{ date(row) }}</time>
                  </td>
                  <td>{{ row.timezone || 'America/Toronto' }}</td>
                  <td><span class="appointment-status">Prévu</span></td>
                </tr>
              </tbody>
            </table>
          </div>
          <button class="text-link" @click="$emit('navigate', 'appointments')">
            Voir tout mon agenda<ArrowRight :size="16" />
          </button>
        </section>
      </div>
      <aside class="home-panel home-actions">
        <header class="panel-heading">
          <div>
            <h2>Ma boîte à outils</h2>
            <p>L’essentiel, à portée de main.</p>
          </div>
          <Sparkles :size="20" />
        </header>
        <button class="action-tile violet" @click="$emit('navigate', 'contacts')">
          <span class="action-tile-title"
            ><span class="action-bubble"><Users :size="16" /></span>Mes prospects<ArrowUpRight
              :size="16" /></span
          ><span class="action-tile-body"
            >Retrouvez une fiche, complétez les informations et préparez votre échange.<span
              >Ouvrir les prospects <ArrowRight :size="14" /></span
          ></span>
        </button>
        <button class="action-tile orange" @click="$emit('navigate', 'appointments')">
          <span class="action-tile-title"
            ><span class="action-bubble"><CalendarCheck :size="16" /></span>Mon agenda<ArrowUpRight
              :size="16" /></span
          ><span class="action-tile-body"
            >Consultez les créneaux réservés et préparez vos prochains rendez-vous.<span
              >Consulter l’agenda <ArrowRight :size="14" /></span
          ></span>
        </button>
        <button
          class="action-tile green"
          @click="$emit('navigate', assurance ? 'followups' : 'statistics')"
        >
          <span class="action-tile-title"
            ><span class="action-bubble"
              ><component :is="assurance ? ListTodo : BarChart3" :size="16" /></span
            >{{ assurance ? 'Mes suivis' : 'Mes statistiques' }}<ArrowUpRight :size="16" /></span
          ><span class="action-tile-body"
            >{{
              assurance
                ? 'Gardez une longueur d’avance sur vos tâches et vos prochaines échéances.'
                : 'Consultez vos résultats et retrouvez le détail de votre activité.'
            }}<span
              >{{ assurance ? 'Traiter mes tâches' : 'Voir mes résultats' }}
              <ArrowRight :size="14" /></span
          ></span>
        </button>
      </aside>
    </div>
    <section v-if="assurance" class="home-alerts" aria-labelledby="home-alerts-title">
      <header class="home-alerts-head">
        <span class="followup-summary-icon"><ListTodo :size="18" /></span>
        <div>
          <h2 id="home-alerts-title">Alertes et notifications</h2>
          <p>Les notifications de vos suivis, en un coup d’œil.</p>
        </div>
      </header>
      <div class="home-alerts-grid"><slot /></div>
    </section>
  </section>
  <section v-else-if="admin" class="setter-homepage admin-homepage">
    <div class="home-topline">
      <span class="home-workspace"
        ><span></span>{{ assurance ? 'Assurance' : 'Isolation' }} · Administration</span
      ><button
        class="home-refresh"
        :disabled="loading || teamTasksLoading"
        @click="
          $emit('refresh');
          refreshHome();
        "
      >
        <RefreshCw :size="15" />Actualiser
      </button>
    </div>
    <div class="home-hero">
      <div class="home-main-snapshot">
        <header class="home-welcome">
          <h1>Bonjour {{ username }} <span aria-hidden="true">✦</span></h1>
          <p>Le pilotage de votre équipe, en un coup d’œil.</p>
        </header>
        <div class="home-highlights">
          <button class="home-highlight peach" @click="$emit('navigate', 'contacts')">
            <span class="highlight-label">Prospects</span
            ><small>Tout le périmètre de l’équipe</small
            ><Users class="metric-decoration" :size="40" /><strong>{{
              summary.contacts ?? summary.prospects ?? 0
            }}</strong
            ><span class="metric-arrow"><ArrowUpRight :size="21" /></span>
          </button>
          <button class="home-highlight blue" @click="$emit('navigate', 'followups')">
            <span class="highlight-label">Tâches ouvertes</span
            ><small>Les suivis en cours de l’équipe</small
            ><ListTodo class="metric-decoration" :size="40" /><strong>{{
              teamOpen ?? (teamTasksError ? 'Indisponible' : '…')
            }}</strong
            ><span class="metric-arrow"><ArrowUpRight :size="21" /></span>
          </button>
          <button class="home-highlight lilac" @click="$emit('navigate', 'followups')">
            <span class="highlight-label">Tâches en retard</span
            ><small>À relancer ou réattribuer</small
            ><Clock3 class="metric-decoration" :size="40" /><strong>{{
              teamTasksError ? 'Indisponible' : teamTasks ? teamTasks.overdue : '…'
            }}</strong
            ><span class="metric-arrow"><ArrowUpRight :size="21" /></span>
          </button>
        </div>
        <p v-if="teamTasksError" class="panel-feedback" role="alert">
          Compteurs de tâches indisponibles : {{ teamTasksError }}
          <button class="home-refresh" @click="loadTeamTasks">Réessayer</button>
        </p>
      </div>
      <aside class="home-hero-side">
        <button
          v-if="assurance"
          class="home-status-pill dark"
          @click="$emit('navigate', 'assignments')"
        >
          <span class="pill-icon"><UserRoundCheck :size="19" /></span
          ><span><strong>Affectations</strong><small>Setters et conseillers</small></span
          ><ArrowUpRight :size="19" />
        </button>
        <button v-else class="home-status-pill dark" @click="$emit('navigate', 'contacts')">
          <span class="pill-icon"><UserRoundCheck :size="19" /></span
          ><span
            ><strong>{{ summary.unassigned ?? 0 }} prospect(s)</strong
            ><small>Sans affectation</small></span
          ><ArrowUpRight :size="19" />
        </button>
        <button class="home-status-pill" @click="$emit('navigate', 'appointments')">
          <span class="pill-icon"><CalendarCheck :size="19" /></span
          ><span
            ><strong>Agenda de l’équipe</strong
            ><small>{{ assurance ? 'Rendez-vous' : 'Visites' }} planifiés</small></span
          ><ArrowUpRight :size="19" />
        </button>
        <button class="home-feature" @click="$emit('navigate', 'statistics')">
          <span class="feature-tag"><BarChart3 :size="13" />PILOTAGE</span
          ><strong>Suivez l’activité<br />de votre équipe.</strong
          ><span>Ouvrir les statistiques <ArrowUpRight :size="19" /></span>
        </button>
      </aside>
    </div>
    <section class="home-panel home-agenda">
      <header class="panel-heading">
        <div>
          <h2>
            {{ assurance ? 'Prochains rendez-vous de l’équipe' : 'Prochaines visites de l’équipe' }}
          </h2>
          <p>Les trois prochains créneaux prévus</p>
        </div>
        <CalendarCheck :size="21" />
      </header>
      <p v-if="loading" class="panel-feedback" role="status">Chargement de l’agenda…</p>
      <div v-else-if="error" class="panel-feedback" role="alert">
        <p>{{ error }}</p>
        <button class="home-refresh" @click="loadUpcoming">Réessayer</button>
      </div>
      <div v-else-if="!upcoming.length" class="agenda-empty">
        <span><CalendarCheck :size="24" /></span>
        <div>
          <h3>Agenda libre</h3>
          <p>Aucun {{ assurance ? 'rendez-vous' : 'créneau' }} à venir dans l’équipe.</p>
        </div>
      </div>
      <div v-else class="agenda-table-wrap">
        <table class="home-agenda-table">
          <thead>
            <tr>
              <th>Prospect</th>
              <th>Date et heure</th>
              <th>Fuseau</th>
              <th>Statut</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in upcoming" :key="row.id">
              <td>{{ (assurance ? row.contact : row.prospect)?.name || 'Dossier sans nom' }}</td>
              <td>
                <time>{{ date(row) }}</time>
              </td>
              <td>{{ row.timezone || 'America/Toronto' }}</td>
              <td><span class="appointment-status">Prévu</span></td>
            </tr>
          </tbody>
        </table>
      </div>
      <button class="text-link" @click="$emit('navigate', 'appointments')">
        Voir l’agenda de l’équipe<ArrowRight :size="16" />
      </button>
    </section>
    <section v-if="assurance" class="home-alerts" aria-labelledby="home-alerts-title-team">
      <header class="home-alerts-head">
        <span class="followup-summary-icon"><ListTodo :size="18" /></span>
        <div>
          <h2 id="home-alerts-title-team">Alertes et notifications</h2>
          <p>Échéances des mandats et suivis de l’équipe, en un coup d’œil.</p>
        </div>
      </header>
      <div class="home-alerts-grid"><slot /></div>
    </section>
  </section>
  <section v-else class="crm-overview">
    <div class="crm-metrics">
      <div v-for="metric in metrics" :key="metric.label" class="crm-metric">
        <span class="metric-icon" :class="metric.tone"
          ><component :is="metric.icon" :size="20"
        /></span>
        <div>
          <p>{{ metric.label }}</p>
          <strong>{{ metric.value ?? 0 }}</strong>
        </div>
      </div>
    </div>
    <div class="crm-overview-grid">
      <section class="crm-priorities">
        <div class="overview-section-title">
          <h3>Votre activité</h3>
          <span>{{ workspace === 'assurance' ? 'Assurance' : 'Isolation' }}</span>
        </div>
        <button class="overview-action" @click="$emit('navigate', 'contacts')">
          <span class="action-icon"><Users :size="20" /></span
          ><span
            ><strong>{{
              role === 'client' ? 'Consulter mes dossiers' : 'Retrouver mes contacts'
            }}</strong
            ><small>{{
              role === 'client'
                ? 'Voir les visites et les setters à l’origine des réservations.'
                : 'Ouvrir les fiches, qualifier et préparer les prochains échanges.'
            }}</small></span
          ><ArrowUpRight :size="18" /></button
        ><button
          v-if="role !== 'client'"
          class="overview-action"
          @click="$emit('navigate', 'appointments')"
        >
          <span class="action-icon purple"><CalendarCheck :size="20" /></span
          ><span
            ><strong>{{ assurance ? 'Gérer les rendez-vous' : 'Gérer les visites' }}</strong
            ><small>Consulter les créneaux et suivre les comptes rendus.</small></span
          ><ArrowUpRight :size="18" /></button
        ><button
          v-if="assurance && role !== 'advisor'"
          class="overview-action"
          @click="$emit('navigate', 'followups')"
        >
          <span class="action-icon orange"><ListTodo :size="20" /></span
          ><span
            ><strong>Traiter les tâches de suivi</strong
            ><small>Retrouver les actions ouvertes et les prochaines échéances.</small></span
          ><ArrowUpRight :size="18" />
        </button>
      </section>
      <aside class="crm-workspace-note">
        <span class="note-tag">VOTRE AGENDA</span>
        <h3>{{ assurance ? 'Prochains rendez-vous' : 'Prochaines visites' }}</h3>
        <p v-if="loading">Chargement de l’agenda…</p>
        <p v-else-if="error" role="alert">
          {{ error }} <button class="secondary" @click="loadUpcoming">Réessayer</button>
        </p>
        <p v-else-if="!upcoming.length">Aucun créneau à venir dans votre périmètre.</p>
        <ol v-else class="upcoming-list">
          <li v-for="row in upcoming" :key="row.id">
            <span>{{ date(row) }}</span
            ><strong>{{
              (assurance ? row.contact : row.prospect)?.name || 'Dossier sans nom'
            }}</strong>
          </li>
        </ol>
        <button class="agenda-link" @click="$emit('navigate', 'appointments')">
          Ouvrir l’agenda<ArrowUpRight :size="16" />
        </button>
      </aside>
    </div>
    <div class="crm-dashboard-details"><slot /></div>
  </section>
</template>
<style scoped>
.crm-welcome {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #edf4ff;
  border: 1px solid #e1e7ef;
  border-radius: 15px;
  padding: 30px 34px;
  margin-bottom: 22px;
}
.crm-welcome > div > span {
  color: #84916d;
  font-size: 10px;
  font-weight: 650;
  letter-spacing: 1.5px;
}
.crm-welcome h2 {
  font-size: 30px;
  letter-spacing: -1px;
  margin: 12px 0;
  color: #2e3c27;
}
.crm-welcome h2 .welcome-dot {
  color: #7f9453;
}
.crm-welcome p {
  font-size: 13px;
  color: #64748b;
  margin: 0;
}
.welcome-mark {
  width: 84px;
  height: 84px;
  display: grid;
  place-items: center;
  border-radius: 24px;
  background: #e4ebd4;
  color: #829664;
  transform: rotate(-8deg);
}
.crm-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 18px;
  margin-bottom: 26px;
}
.crm-metric {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 24px;
  background: #fff;
  border: 1px solid #e1e7ef;
  border-radius: 13px;
}
.metric-icon,
.action-icon {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  border-radius: 12px;
  color: #3f7bc3;
  background: #eaf2ff;
}
.metric-icon.purple,
.action-icon.purple {
  color: #9984bb;
  background: #f2eef8;
}
.metric-icon.orange,
.action-icon.orange {
  color: #c49c71;
  background: #faf1e5;
}
.crm-metric p {
  font-size: 11px;
  color: #6e7865;
  margin: 0 0 9px;
}
.crm-metric strong {
  font-size: 28px;
  letter-spacing: -0.8px;
  font-weight: 650;
}
.crm-overview-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.7fr) minmax(260px, 1fr);
  gap: 24px;
}
.crm-priorities {
  border: 1px solid #e1e7ef;
  border-radius: 14px;
  background: white;
  overflow: hidden;
}
.overview-section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 22px 24px;
  border-bottom: 1px solid #edf0e5;
}
.overview-section-title h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 650;
}
.overview-section-title > span {
  font-size: 11px;
  background: #f4f6ee;
  color: #899775;
  padding: 5px 9px;
  border-radius: 6px;
}
.overview-action {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
  padding: 22px 24px;
  border: 0;
  border-bottom: 1px solid #edf0e5;
  background: white;
  text-align: left;
  cursor: pointer;
  color: inherit;
}
.overview-action:last-child {
  border-bottom: 0;
}
.overview-action:hover {
  background: #fcfdf9;
}
.overview-action > span:nth-child(2) {
  flex: 1;
}
.overview-action strong {
  display: block;
  font-size: 13px;
  font-weight: 600;
}
.overview-action small {
  display: block;
  margin-top: 7px;
  color: #64748b;
  font-size: 11px;
  line-height: 1.5;
}
.overview-action > svg {
  color: #97a482;
}
.crm-workspace-note {
  border: 1px solid #e1e7ef;
  background: #fff;
  padding: 28px;
  border-radius: 14px;
  align-self: start;
}
.note-tag {
  color: #8d987b;
  font-size: 10px;
  letter-spacing: 1.3px;
}
.crm-workspace-note h3 {
  font-size: 22px;
  font-weight: 550;
  letter-spacing: -0.6px;
  line-height: 1.4;
  margin: 20px 0 14px;
}
.crm-workspace-note p {
  color: #64748b;
  line-height: 1.9;
  font-size: 12px;
}
.crm-workspace-note > div {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 10px;
  color: #64748b;
  border-top: 1px solid #e1e7ef;
  margin-top: 25px;
  padding-top: 18px;
}
.note-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #8ca36d;
}
.crm-dashboard-details {
  margin-top: 24px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}
.crm-dashboard-details:deep(> section) {
  background: white;
  border: 1px solid #e1e7ef;
  border-radius: 13px;
  padding: 22px;
  font-size: 12px;
  line-height: 1.7;
}
.crm-dashboard-details:deep(h3) {
  margin: 0 0 12px;
  font-size: 15px;
}
.crm-dashboard-details:deep(button) {
  margin: 6px 6px 0 0;
  font-size: 11px;
  padding: 9px 12px;
}
.crm-dashboard-details:deep(p) {
  margin: 8px 0;
  color: #64748b;
}
.upcoming-list {
  list-style: none;
  padding: 0;
  margin: 14px 0;
}
.upcoming-list li {
  padding: 14px 0;
  border-bottom: 1px solid #e1e7ef;
}
.upcoming-list span {
  display: block;
  font-size: 11px;
  color: #7b8969;
}
.upcoming-list strong {
  display: block;
  margin-top: 6px;
  font-size: 13px;
  font-weight: 550;
}
.agenda-link {
  display: flex;
  align-items: center;
  gap: 12px;
  border: 0;
  border-top: 1px solid #dfe5d3;
  background: none;
  color: #2563a6;
  font-size: 12px;
  font-weight: 600;
  width: 100%;
  padding: 18px 0 0;
  margin-top: 24px;
  cursor: pointer;
}
.crm-dashboard-details:empty {
  display: none;
}
@media (max-width: 1050px) {
  .crm-overview-grid {
    grid-template-columns: 1fr;
  }
  .crm-dashboard-details {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 650px) {
  .crm-welcome {
    padding: 24px;
  }
  .crm-welcome h2 {
    font-size: 24px;
  }
  .welcome-mark {
    display: none;
  }
  .crm-metrics {
    grid-template-columns: 1fr;
  }
  .crm-metric {
    padding: 19px;
  }
  .overview-action {
    padding: 20px;
  }
  .crm-workspace-note {
    display: none;
  }
}
.crm-metric {
  padding: 22px;
  border-radius: 8px;
}
.crm-metric strong {
  color: #20324b;
  font-size: 30px;
}
.crm-metrics {
  gap: 16px;
}
.crm-overview-grid {
  gap: 18px;
}
.crm-priorities,
.crm-workspace-note {
  border-radius: 8px;
}
.crm-dashboard-details {
  gap: 18px;
}
.crm-dashboard-details:deep(> section) {
  border-radius: 8px;
}
.crm-workspace-note h3 {
  font-size: 17px;
  font-weight: 650;
  letter-spacing: 0;
}
.overview-section-title h3 {
  color: #263b55;
}
.overview-action:hover {
  background: #f7faff;
}
.overview-section-title > span {
  background: #edf4ff;
  color: #3f6eaa;
}
.overview-action small {
  color: #64748b;
}
</style>
<style scoped>
.setter-homepage {
  max-width: 1450px;
  margin: auto;
  color: #24232c;
  font-family: Inter, 'Segoe UI', sans-serif;
  --home-muted: #74717e;
  --home-line: #ece9f0;
}
.setter-homepage button {
  font-family: inherit;
  cursor: pointer;
}
.setter-homepage button:disabled {
  cursor: wait;
  opacity: 0.6;
}
.setter-homepage button:focus-visible {
  outline: 3px solid #9271ef;
  outline-offset: 4px;
}
.home-topline {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 18px;
}
.home-workspace {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #6f687f;
}
.home-workspace > span {
  width: 7px;
  height: 7px;
  background: #9474e4;
  border-radius: 50%;
}
.home-refresh {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid #e5e1eb;
  border-radius: 30px;
  background: #ffffffb0;
  padding: 10px 16px;
  font-size: 12px;
  color: #5f586e;
}
.home-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.85fr) minmax(270px, 1fr);
  gap: 24px;
  background: #ffffffa6;
  border: 1px solid #fff;
  border-radius: 26px;
  padding: 24px;
  margin-bottom: 20px;
  box-shadow: 0 10px 40px #65558605;
}
.home-welcome h1 {
  font-size: 30px !important;
  font-weight: 650;
  letter-spacing: -1px;
  line-height: 1.25;
  color: #24212b !important;
  margin: 0 0 8px;
  overflow-wrap: anywhere;
}
.home-welcome h1 > span {
  color: #9473df;
  font-size: 25px;
}
.home-welcome p {
  font-size: 12px;
  color: var(--home-muted);
  margin: 0;
  line-height: 1.6;
}
.home-highlights {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-top: 24px;
}
.home-highlight {
  position: relative;
  container-type: inline-size;
  text-align: left;
  border: 0;
  border-radius: 23px;
  min-height: 205px;
  padding: 20px 18px 55px;
  color: #24212b;
  overflow: hidden;
  transition:
    transform 0.18s,
    box-shadow 0.18s;
}
.home-highlight:hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 25px #372a6310;
}
.home-highlight.peach {
  background: #fceacd;
}
.home-highlight.blue {
  background: #cedffd;
}
.home-highlight.lilac {
  background: #e5e1ec;
}
.highlight-label {
  display: block;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: -0.3px;
}
.home-highlight small {
  display: block;
  font-size: 10px;
  line-height: 1.5;
  margin-top: 6px;
  color: #5b5362;
}
.home-highlight strong {
  position: absolute;
  bottom: 21px;
  left: 18px;
  /* Shrinks with narrow cards so large counts never slide under the arrow button. */
  font-size: min(31px, 19cqi);
  line-height: 1.2;
  letter-spacing: -1px;
  white-space: nowrap;
  max-width: calc(100% - 72px);
}
.home-highlight strong.next-slot {
  white-space: normal;
  font-size: 17px;
  letter-spacing: -0.4px;
}
.metric-decoration {
  position: absolute;
  right: 20px;
  top: 83px;
  opacity: 0.13;
}
.metric-arrow {
  position: absolute;
  right: 0;
  bottom: 0;
  display: grid;
  place-items: center;
  background: #17151c;
  color: white;
  width: 43px;
  height: 43px;
  border-radius: 50%;
  border: 7px solid #fcfafc;
  box-sizing: content-box;
}
.home-hero-side {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 8px;
}
.home-status-pill {
  display: flex;
  align-items: center;
  gap: 12px;
  border: 0;
  background: #fff;
  border-radius: 50px;
  padding: 10px 14px;
  color: #27242e;
  text-align: left;
}
.home-status-pill.dark {
  background: #19171f;
  color: white;
  transform: rotate(-3deg);
  margin-bottom: 3px;
}
.pill-icon {
  display: grid;
  place-items: center;
  background: #eeeaf6;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dark .pill-icon {
  background: #8862ea;
}
.home-status-pill > span:nth-child(2) {
  flex: 1;
  min-width: 0;
}
.home-status-pill strong {
  display: block;
  font-size: 17px;
  font-weight: 600;
}
.home-status-pill small {
  display: block;
  font-size: 10px;
  opacity: 0.65;
  margin-top: 3px;
}
.home-feature {
  position: relative;
  isolation: isolate;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
  min-height: 135px;
  text-align: left;
  border: 0;
  border-radius: 20px;
  background: linear-gradient(125deg, #6f688f, #817ba5 55%, #a7a2c4);
  color: white;
  padding: 20px;
  margin-top: 10px;
}
.home-feature:before,
.home-feature:after {
  content: '';
  position: absolute;
  z-index: -1;
  width: 220px;
  height: 220px;
  border: 25px solid #ffffff0d;
  transform: rotate(35deg);
  right: -80px;
  top: -100px;
}
.home-feature:after {
  right: -20px;
  top: -130px;
  border-width: 1px;
}
.feature-tag {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 9px;
  letter-spacing: 1px;
  color: #eee8ff;
}
.home-feature strong {
  font-size: 21px;
  line-height: 1.25;
  letter-spacing: -0.5px;
}
.home-feature > span:last-child {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  color: #f0edfb;
}
.home-body {
  display: grid;
  grid-template-columns: minmax(0, 1.85fr) minmax(270px, 1fr);
  gap: 20px;
  align-items: start;
}
.home-left {
  display: grid;
  gap: 20px;
  min-width: 0;
}
.home-panel {
  border-radius: 23px;
  background: #ffffffc9;
  border: 1px solid #fff;
  padding: 22px;
  min-width: 0;
}
.panel-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 20px;
}
.setter-homepage h2 {
  font-size: 16px !important;
  font-weight: 600;
  letter-spacing: -0.35px;
  color: #2c2835;
  margin: 0;
}
.panel-heading p {
  font-size: 10px;
  color: var(--home-muted);
  margin: 6px 0 0;
  line-height: 1.5;
}
.panel-heading > svg {
  color: #9c8ab9;
}
.round-link {
  width: 32px;
  height: 32px;
  border: 1px solid #e7e1ed;
  background: white;
  border-radius: 50%;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}
.performance-content {
  display: flex;
  align-items: center;
  gap: 25px;
  min-height: 155px;
}
.performance-total {
  background: #fff;
  border-radius: 17px;
  padding: 18px;
  flex: 0 0 130px;
}
.performance-total > span {
  font-size: 10px;
  color: #6f687c;
  line-height: 1.5;
  display: block;
}
.performance-total strong {
  display: block;
  font-size: 35px;
  letter-spacing: -1.2px;
  margin: 10px 0;
}
.performance-total small {
  font-size: 10px;
  color: #7a6b92;
  background: #f5f0fc;
  border-radius: 20px;
  padding: 5px 7px;
  display: inline-block;
}
.home-chart {
  display: flex;
  align-items: flex-end;
  gap: 14px;
  flex: 1;
  min-width: 0;
  padding: 5px 0;
}
.chart-column {
  flex: 1;
  min-width: 0;
  text-align: center;
}
.bar-value {
  display: block;
  font-size: 11px;
  color: #796297;
  margin-bottom: 5px;
  font-weight: 600;
}
.bar-track {
  height: 100px;
  display: flex;
  align-items: flex-end;
  background: #f4f0f8;
  border-radius: 30px;
  overflow: hidden;
  max-width: 48px;
  margin: auto;
}
.bar-track > span {
  display: block;
  width: 100%;
  border-radius: 30px;
  transition: height 0.3s;
}
.bar-label {
  display: block;
  font-size: 9px;
  line-height: 1.4;
  margin-top: 10px;
  color: #756b82;
}
.chart-caption {
  font-size: 10px;
  color: #89818f;
  line-height: 1.6;
  margin: 16px 0 0;
}
.panel-feedback {
  font-size: 12px;
  color: #80748e;
  padding: 12px 0;
  line-height: 1.7;
}
.agenda-empty {
  display: flex;
  align-items: center;
  gap: 17px;
  padding: 15px 0 25px;
}
.agenda-empty > span {
  display: grid;
  place-items: center;
  flex-shrink: 0;
  width: 55px;
  height: 55px;
  background: #f1eafa;
  color: #a18bc1;
  border-radius: 18px;
}
.agenda-empty h3 {
  font-size: 14px !important;
  color: #5d526e;
  margin: 0 0 7px;
}
.agenda-empty p {
  font-size: 11px;
  color: #88808f;
  line-height: 1.6;
  margin: 0;
}
.text-link {
  display: flex;
  align-items: center;
  gap: 9px;
  background: none;
  border: 0;
  padding: 12px 0 0;
  color: #7560a1;
  font-size: 11px;
}
.agenda-table-wrap {
  overflow: auto;
}
.home-agenda-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 11px;
}
.home-agenda-table th {
  background: #fff;
  color: #90859c;
  font-size: 10px;
  font-weight: 500;
  padding: 10px 8px;
  border: 0;
}
.home-agenda-table td {
  padding: 16px 8px;
  border: 0;
  border-bottom: 1px solid #eee9f2;
  color: #5b516a;
  line-height: 1.6;
}
.appointment-status {
  background: #edf6ed;
  color: #52865a;
  font-size: 10px;
  border-radius: 15px;
  padding: 4px 8px;
  white-space: nowrap;
}
.home-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.home-actions .panel-heading {
  margin-bottom: 4px;
}
.action-tile {
  text-align: left;
  padding: 0;
  background: #fff;
  border: 1px solid #f0edf3;
  border-radius: 15px;
  overflow: hidden;
  color: #42384e;
  transition: transform 0.15s;
}
.action-tile:hover {
  transform: translateX(3px);
}
.action-tile-title {
  display: flex;
  align-items: center;
  gap: 9px;
  background: #f9f7fc;
  padding: 12px;
  font-size: 12px;
  font-weight: 600;
}
.action-tile-title > svg {
  margin-left: auto;
  color: #aa9db7;
}
.action-bubble {
  width: 27px;
  height: 27px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: #936deb;
  color: white;
  flex-shrink: 0;
}
.orange .action-bubble {
  background: #ef9a5a;
}
.green .action-bubble {
  background: #73b695;
}
.action-tile-body {
  display: block;
  font-size: 11px;
  line-height: 1.7;
  padding: 12px 15px;
  color: #82758f;
}
.action-tile-body > span {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #7a60ae;
  font-size: 10px;
  margin-top: 12px;
}
.home-alerts {
  border: 1px solid #fff;
  background: #ffffffb8;
  border-radius: 20px;
  margin-top: 20px;
  padding: 20px 22px 22px;
}
.home-alerts-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.home-alerts-head h2 {
  margin: 0;
  font-size: 15px;
  color: #2d2640;
}
.home-alerts-head p {
  margin: 3px 0 0;
  font-size: 12px;
  color: #7a6d86;
}
.followup-summary-icon {
  background: #eee8fa;
  color: #9270cb;
  width: 34px;
  height: 34px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  flex: none;
}
.home-alerts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 320px), 1fr));
  gap: 16px;
  align-items: start;
}
@media (min-width: 1550px) {
  .home-highlight {
    min-height: 230px;
  }
  .home-hero {
    padding: 30px;
  }
  .home-feature {
    min-height: 155px;
  }
}
@media (max-width: 1150px) {
  .home-hero,
  .home-body {
    grid-template-columns: minmax(0, 1.65fr) minmax(245px, 1fr);
    gap: 16px;
  }
  .home-hero {
    padding: 20px;
  }
  .home-highlight {
    padding: 16px 13px 55px;
  }
  .highlight-label {
    font-size: 13px;
  }
  .home-highlight strong {
    left: 13px;
  }
  .performance-content {
    gap: 14px;
  }
  .performance-total {
    flex-basis: 100px;
    padding: 14px;
  }
  .home-chart {
    gap: 8px;
  }
}
@media (max-width: 950px) {
  .home-hero,
  .home-body {
    grid-template-columns: 1fr;
  }
  .home-hero-side {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }
  .home-feature {
    grid-column: 1/-1;
    min-height: 125px;
  }
  .home-status-pill.dark {
    transform: none;
    margin: 0;
  }
  .home-actions {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .home-actions > .panel-heading {
    grid-column: 1/-1;
  }
  .action-tile-title {
    flex-wrap: wrap;
  }
}
@media (max-width: 600px) {
  .home-hero {
    padding: 18px;
    border-radius: 22px;
  }
  .home-welcome h1 {
    font-size: 25px !important;
  }
  .home-highlights {
    gap: 9px;
    grid-template-columns: 1fr;
  }
  .home-highlight {
    min-height: 145px;
    padding: 18px;
  }
  .home-highlight strong {
    left: 18px;
  }
  .metric-decoration {
    top: 50px;
    right: 85px;
  }
  .home-highlight strong.next-slot {
    font-size: 20px;
    max-width: calc(100% - 85px);
  }
  .home-hero-side {
    grid-template-columns: 1fr;
  }
  .home-feature {
    grid-column: auto;
  }
  .home-actions {
    grid-template-columns: 1fr;
  }
  .home-panel {
    padding: 18px;
  }
  .performance-content {
    align-items: stretch;
    flex-direction: column;
  }
  .performance-total {
    flex-basis: auto;
  }
  .performance-total strong {
    display: inline-block;
    margin: 8px 12px 0 0;
  }
  .home-chart {
    gap: 20px;
  }
  .home-topline {
    gap: 8px;
  }
  .home-refresh {
    font-size: 10px;
    padding: 9px 11px;
  }
  .home-workspace {
    font-size: 10px;
  }
  .bar-track {
    height: 90px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .home-highlight,
  .bar-track > span,
  .action-tile {
    transition: none;
  }
  .home-highlight:hover,
  .action-tile:hover {
    transform: none;
  }
}
.home-highlight {
  display: block;
  align-content: start;
}
</style>
