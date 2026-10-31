<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import PortalLogin from './PortalLogin.vue';
import PortalWorkspaceChooser from './PortalWorkspaceChooser.vue';
import ClientFolders from './ClientFolders.vue';
import CrmShell from './CrmShell.vue';
import CrmOverview from './CrmOverview.vue';
import IsolationStatistics from './IsolationStatistics.vue';
import IsolationAgenda from './IsolationAgenda.vue';
import IsolationNotices from './IsolationNotices.vue';
import PortalAccess from './PortalAccess.vue';
import PortalPassword from './PortalPassword.vue';
import PortalRecovery from './PortalRecovery.vue';
import PortalInvitationAccept from './PortalInvitationAccept.vue';
import IsolationWorkQueue from './IsolationWorkQueue.vue';
import IsolationClient from './IsolationClient.vue';
import IsolationQualification from './IsolationQualification.vue';
import AssuranceContacts from './AssuranceContacts.vue';
import AssuranceProspects from './AssuranceProspects.vue';
import AssuranceAgreementRegistry from './AssuranceAgreementRegistry.vue';
import AssuranceAgreementAlerts from './AssuranceAgreementAlerts.vue';
import AssuranceAssignments from './AssuranceAssignments.vue';
import CrmAppointmentsCalendar from './CrmAppointmentsCalendar.vue';
import AssuranceAppointments from './AssuranceAppointments.vue';
import AssuranceAdvisorProspects from './AssuranceAdvisorProspects.vue';
import IsolationVisits from './IsolationVisits.vue';
import IsolationTasksBoard from './IsolationTasksBoard.vue';
import IsolationCloserVisits from './IsolationCloserVisits.vue';
import AssuranceFollowUps from './AssuranceFollowUps.vue';
import AssuranceSetterTasks from './AssuranceSetterTasks.vue';
import AssuranceNotifications from './AssuranceNotifications.vue';
import AssuranceAppointmentNotifications from './AssuranceAppointmentNotifications.vue';
import TaskAlerts from './TaskAlerts.vue';
import CallsCenter from './CallsCenter.vue';
import AssuranceReminders from './AssuranceReminders.vue';
import AssuranceStatistics from './AssuranceStatistics.vue';
import AssuranceCompensation from './AssuranceCompensation.vue';
import AssuranceFieldSettings from './AssuranceFieldSettings.vue';
import { RefreshCw } from 'lucide-vue-next';
import { appointmentLink, isolationVisitLink } from './appointment-link';
const pendingAppointment = ref(appointmentLink(new URL(location.href)));
const pendingIsolationVisit = ref(isolationVisitLink(new URL(location.href)));
const appointmentFocus = ref<number | null>(null);
type Membership = { workspace: string; role: string };
const user = ref<{
  username: string;
  workspaces: Membership[];
  admin_workspaces: string[];
  landing: string | null;
} | null>(null);
const workspace = ref(''),
  error = ref(''),
  busy = ref(false),
  ready = ref(false);
const recoveryOpen = ref(false),
  resetUid = ref(''),
  resetToken = ref('');
const inviteId = ref(''),
  inviteToken = ref('');
function closeRecovery() {
  recoveryOpen.value = false;
  resetUid.value = '';
  resetToken.value = '';
}
const passwordOpen = ref(false),
  calendarNotice = ref('');
const managing = ref(false),
  assuranceModule = ref('overview'),
  isolationModule = ref('overview');
const summary = ref<any>(null);
const notificationVersion = ref(0),
  contentVersion = ref(0),
  agreementDeadline = ref('');
async function refreshAssurance() {
  try {
    const data = await assurance('dashboard/');
    if (workspace.value === 'assurance') {
      summary.value = data;
      notificationVersion.value++;
    }
  } catch (e: any) {
    if (workspace.value === 'assurance') error.value = e.message;
  }
}
let csrf = '',
  workspaceVersion = 0;
async function portal(path: string, body?: any, method?: string) {
  if (body !== undefined && !csrf) {
    const response = await fetch('/api/portal/csrf/', { credentials: 'include' });
    csrf = (await response.json()).csrfToken;
  }
  const response = await fetch('/api/portal/' + path, {
    method: method || (body !== undefined ? 'POST' : 'GET'),
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(csrf ? { 'X-CSRFToken': csrf } : {}) },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    throw new Error(
      result.detail ||
        Object.entries(result)
          .map(([key, value]) => key + ': ' + String(value))
          .join(' · ') ||
        'Accès indisponible',
    );
  }
  return response.status === 204 ? null : response.json();
}
async function business(path: string, body?: any, method?: string, target = workspace.value) {
  const grant = await portal('access/' + target + '/', {});
  const response = await fetch('/api/' + target + '/' + path, {
    method: method || (body !== undefined ? 'POST' : 'GET'),
    headers: {
      Authorization: 'Bearer ' + grant.token,
      ...(body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
    },
    ...(body !== undefined ? { body: body instanceof FormData ? body : JSON.stringify(body) } : {}),
  });
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    const failure = new Error(
      result.detail ||
        (Array.isArray(result) ? result.join(' · ') : Object.values(result).join(' · ')) ||
        'Service métier indisponible',
    ) as Error & { status: number };
    failure.status = response.status;
    throw failure;
  }
  if (response.headers.get('Content-Disposition')?.includes('attachment')) return response.blob();
  return response.status === 204 ? null : response.json();
}
function assurance(path: string, body?: any, method?: string) {
  return business(path, body, method, 'assurance');
}
function isolationDashboard(role: string) {
  return role === 'closer'
    ? 'closer-visits/dashboard/'
    : role === 'client'
      ? 'client-dashboard/'
      : 'workspace-dashboard/';
}
function isolation(path: string, body?: any, method?: string) {
  return business(path, body, method, 'isolation');
}
// The last workspace is reopened on reload, so multi-space users skip the space chooser.
const LAST_WORKSPACE = 'amx-workspace';
function rememberedWorkspace() {
  try {
    return localStorage.getItem(LAST_WORKSPACE) || '';
  } catch {
    return '';
  }
}
async function enter(value: string) {
  if (!user.value?.workspaces.some((item) => item.workspace === value)) return;
  try {
    localStorage.setItem(LAST_WORKSPACE, value);
  } catch {
    /* Storage unavailable: the profile menu still switches spaces. */
  }
  const version = ++workspaceVersion;
  error.value = '';
  busy.value = true;
  workspace.value = value;
  summary.value = null;
  // Advisors start in their agenda, with their own prospects and availability settings.
  assuranceModule.value = role.value === 'advisor' ? 'appointments' : 'overview';
  appointmentFocus.value = null;
  if (value === 'assurance' && pendingAppointment.value && role.value === 'advisor') {
    appointmentFocus.value = pendingAppointment.value;
    pendingAppointment.value = null;
    const url = new URL(location.href);
    url.searchParams.delete('appointment');
    url.searchParams.delete('workspace');
    history.replaceState(null, '', url.pathname + url.search + url.hash);
  }
  isolationModule.value = 'overview';
  if (value === 'isolation' && pendingIsolationVisit.value && role.value === 'client') {
    isolationModule.value = 'appointments';
    appointmentFocus.value = pendingIsolationVisit.value;
    pendingIsolationVisit.value = null;
    const url = new URL(location.href);
    url.searchParams.delete('visit');
    url.searchParams.delete('workspace');
    history.replaceState(null, '', url.pathname + url.search + url.hash);
  }
  managing.value = false;
  passwordOpen.value = false;
  try {
    const data = await business(
      value === 'isolation'
        ? isolationDashboard(
            user.value?.workspaces.find((m) => m.workspace === 'isolation')?.role || '',
          )
        : 'dashboard/',
      undefined,
      undefined,
      value,
    );
    if (version === workspaceVersion) summary.value = data;
  } catch (e: any) {
    if (version === workspaceVersion) {
      error.value = e.message;
      summary.value = null;
    }
  } finally {
    if (version === workspaceVersion) busy.value = false;
  }
}
async function login(credentials: { username: string; password: string }) {
  busy.value = true;
  error.value = '';
  try {
    const authenticated = await portal('login/', {
      username: credentials.username,
      password: credentials.password,
    });
    csrf = '';
    user.value = authenticated;
    // A single authorised space opens directly; several are listed in « Mes espaces ».
    if (
      pendingIsolationVisit.value &&
      authenticated.workspaces.some(
        (m: Membership) => m.workspace === 'isolation' && m.role === 'client',
      )
    )
      await enter('isolation');
    else if (
      pendingAppointment.value &&
      authenticated.workspaces.some(
        (m: Membership) => m.workspace === 'assurance' && m.role === 'advisor',
      )
    )
      await enter('assurance');
    else if (authenticated.workspaces.length === 1)
      await enter(authenticated.workspaces[0].workspace);
  } catch (e: any) {
    error.value = e.message;
  } finally {
    credentials.password = '';
    busy.value = false;
  }
}
async function refreshWorkspace() {
  const target = workspace.value,
    version = ++workspaceVersion;
  error.value = '';
  busy.value = true;
  try {
    const data = await business(
      target === 'assurance' ? 'dashboard/' : isolationDashboard(role.value),
      undefined,
      undefined,
      target,
    );
    if (version === workspaceVersion) {
      summary.value = data;
      notificationVersion.value++;
      contentVersion.value++;
    }
  } catch (e: any) {
    if (version === workspaceVersion) error.value = e.message;
  } finally {
    if (version === workspaceVersion) busy.value = false;
  }
}
async function refreshIsolation() {
  try {
    const data = await isolation(isolationDashboard(role.value));
    if (workspace.value === 'isolation') summary.value = data;
  } catch (e: any) {
    if (workspace.value === 'isolation') error.value = e.message;
  }
}
async function logout() {
  await portal('session/', {});
  workspaceVersion++;
  try {
    for (const key of Object.keys(sessionStorage))
      if (key.startsWith('amx-call:')) sessionStorage.removeItem(key);
  } catch {}
  user.value = null;
  workspace.value = '';
  summary.value = null;
  passwordOpen.value = false;
  csrf = '';
}

const role = computed(
  () =>
    summary.value?.role ||
    user.value?.workspaces.find((item) => item.workspace === workspace.value)?.role ||
    '',
);
const activeModule = computed(() =>
  workspace.value === 'assurance' ? assuranceModule.value : isolationModule.value,
);
const navigation = computed(() => {
  if (!workspace.value) return [];
  if (workspace.value === 'assurance' && role.value === 'advisor')
    return [
      { id: 'appointments', label: 'Mes rendez-vous', icon: 'appointments' },
      { id: 'contacts', label: 'Mes prospects', icon: 'contacts' },
    ];
  if (role.value === 'closer')
    return [
      { id: 'overview', label: 'Mes visites', icon: 'appointments' },
      { id: 'statistics', label: 'Mes statistiques', icon: 'statistics' },
    ];
  if (workspace.value === 'isolation' && role.value === 'client')
    return [
      { id: 'overview', label: 'Vue d’ensemble', icon: 'overview' },
      { id: 'appointments', label: 'Visites programmées', icon: 'appointments' },
      { id: 'visit-history', label: 'Historique des visites', icon: 'appointments' },
      { id: 'isolation-agenda', label: 'Agenda et disponibilités', icon: 'appointments' },
    ];
  const items = [
    { id: 'overview', label: 'Vue d’ensemble', icon: 'overview' },
    {
      id: 'contacts',
      label: role.value === 'client' ? 'Mes dossiers' : 'Contacts',
      icon: 'contacts',
    },
    {
      id: 'appointments',
      label: workspace.value === 'assurance' ? 'Rendez-vous' : 'Visites',
      icon: 'appointments',
    },
  ];
  if (workspace.value === 'assurance') {
    if (role.value !== 'advisor')
      items.push(
        { id: 'followups', label: 'Tâches de suivi', icon: 'followups' },
        { id: 'statistics', label: 'Statistiques', icon: 'statistics' },
        {
          id: 'assignments',
          label: role.value === 'administrator' ? 'Affectations' : 'Mes conseillers',
          icon: 'assignments',
        },
      );
    if (role.value === 'administrator')
      items.push(
        { id: 'compensation', label: 'Suivi et rémunération', icon: 'statistics' },
        { id: 'agreements', label: 'Mandats et contrats', icon: 'agreements' },
        { id: 'fields', label: 'Paramètres métier', icon: 'fields' },
      );
  } else {
    if (['client', 'administrator'].includes(role.value))
      items.push({
        id: 'isolation-agenda',
        label: 'Agenda et disponibilités',
        icon: 'appointments',
      });
    if (['setter', 'administrator'].includes(role.value))
      items.push({ id: 'followups', label: 'Tâches de rappel', icon: 'followups' });
    items.push({ id: 'statistics', label: 'Statistiques', icon: 'statistics' });
    if (role.value === 'administrator')
      items.push({ id: 'qualification', label: 'Vérification des numéros', icon: 'qualification' });
  }
  // Setters and administrators call from a prospect card; administrators keep team history.
  if (role.value === 'administrator')
    items.splice(1, 0, { id: 'client-folders', label: 'Dossiers clients', icon: 'agreements' });
  if (['setter', 'administrator'].includes(role.value))
    items.push({ id: 'calls', label: 'Appels', icon: 'calls' });
  return items;
});
// Prospect card to open on arrival in Prospects (from the calls module).
const prospectFocus = ref<{ id: number; mode: 'edit' | 'call' } | null>(null);
function openProspect(value: { id: number; mode: 'edit' | 'call' }) {
  prospectFocus.value = value;
  selectModule('contacts');
}
function openIsolationVisit(id: number) {
  selectModule('appointments');
  appointmentFocus.value = id;
}
function openAssuranceAppointment(id: number) {
  selectModule('appointments');
  appointmentFocus.value = id;
}
const pageTitle = computed(
  () => navigation.value.find((item) => item.id === activeModule.value)?.label || 'Mes espaces',
);
function selectModule(id: string) {
  if (!navigation.value.some((item) => item.id === id)) return;
  if (id !== 'contacts') prospectFocus.value = null;
  if (id !== 'appointments') appointmentFocus.value = null;
  managing.value = false;
  passwordOpen.value = false;
  if (workspace.value === 'assurance') assuranceModule.value = id;
  else isolationModule.value = id;
  window.scrollTo({ top: 0, behavior: 'auto' });
}
function openAccount() {
  passwordOpen.value = !passwordOpen.value;
  managing.value = false;
}
function openAccess() {
  managing.value = !managing.value;
  passwordOpen.value = false;
}
const title = (value: string) => (value === 'assurance' ? 'Assurance' : 'Isolation');
onMounted(async () => {
  const oauth = location.pathname.match(/^\/crm\/oauth\/(google|microsoft|calendly)$/);
  if (oauth) {
    const query = new URLSearchParams(location.search);
    const body: any = { state: query.get('state') || '' };
    if (query.has('error')) body.error = query.get('error');
    else body.code = query.get('code') || '';
    history.replaceState(null, '', '/crm');
    try {
      await portal(
        oauth[1] === 'calendly' ? 'calendly/callback/' : 'calendar/callback/' + oauth[1] + '/',
        body,
      );
      passwordOpen.value = true;
      calendarNotice.value =
        oauth[1] === 'calendly'
          ? 'Calendly connecté. Ouvrez Mon agenda ou Mon compte pour choisir votre page de réservation.'
          : 'Agenda connecté. Consultez Mon compte et mes sessions pour vérifier les disponibilités.';
    } catch (e: any) {
      calendarNotice.value = e.message;
    }
  }
  const invitation = location.hash.match(/^#invite=([a-f0-9-]{36}):([A-Za-z0-9_-]+)$/);
  if (invitation) {
    inviteId.value = invitation[1]!;
    inviteToken.value = invitation[2]!;
    history.replaceState(null, '', location.pathname + location.search);
    ready.value = true;
    return;
  }
  const recovery = location.hash.match(/^#reset=([A-Za-z0-9_-]+):([A-Za-z0-9_-]+)$/);
  if (recovery) {
    resetUid.value = recovery[1]!;
    resetToken.value = recovery[2]!;
    recoveryOpen.value = true;
    history.replaceState(null, '', location.pathname + location.search);
    ready.value = true;
    return;
  }
  try {
    user.value = await portal('session/');
    const allowed = user.value?.workspaces.map((item) => item.workspace) || [];
    const target = [
      pendingIsolationVisit.value ? 'isolation' : '',
      pendingAppointment.value ? 'assurance' : '',
      rememberedWorkspace(),
      user.value?.landing || '',
      allowed[0] || '',
    ].find((value) => value && allowed.includes(value));
    if (target) await enter(target);
  } catch {
  } finally {
    ready.value = true;
  }
});
</script>
<template>
  <div
    class="amx-root"
    :class="{
      'is-authenticated': !!user,
      'setter-home':
        !!user &&
        ['setter', 'administrator'].includes(role) &&
        activeModule === 'overview' &&
        !passwordOpen &&
        !managing,
      'advisors-page-layout':
        !!user && activeModule === 'assignments' && role === 'setter' && !passwordOpen && !managing,
      'folders-page-layout':
        !!user && activeModule === 'client-folders' && !passwordOpen && !managing,
      'calls-page-layout': !!user && activeModule === 'calls' && !passwordOpen && !managing,
      'tasks-page-layout':
        !!user &&
        ['setter', 'administrator'].includes(role) &&
        activeModule === 'followups' &&
        !passwordOpen &&
        !managing,
      'calendar-layout':
        !!user &&
        ['setter', 'administrator', 'advisor'].includes(role) &&
        activeModule === 'appointments' &&
        !passwordOpen &&
        !managing,
      'contacts-layout': !!user && activeModule === 'contacts' && !passwordOpen && !managing,
    }"
  >
    <PortalLogin
      v-if="ready && !user && !recoveryOpen && !inviteId"
      :busy="busy"
      :error="error"
      @submit="login"
      @recover="
        recoveryOpen = true;
        error = '';
      "
    />
    <PortalWorkspaceChooser
      v-else-if="ready && user && !workspace && !passwordOpen && !managing"
      :username="user.username"
      :spaces="user.workspaces"
      :busy="busy"
      :error="error"
      @enter="enter"
      @logout="logout"
    />
    <CrmShell
      v-else
      :username="user?.username || ''"
      :workspace="workspace"
      :role="role"
      :spaces="user?.workspaces || []"
      :items="navigation"
      :active="activeModule"
      :page-title="pageTitle"
      :account-open="passwordOpen"
      :access-open="managing"
      :can-manage="!!user?.admin_workspaces?.length"
      @workspace="enter"
      @navigate="selectModule"
      @account="openAccount"
      @access="openAccess"
      @logout="logout"
    >
      <template v-if="user && workspace && ['setter', 'administrator'].includes(role)" #alerts>
        <TaskAlerts
          :key="workspace + user.username"
          :workspace="workspace"
          :role="role"
          :username="user.username"
          :request="workspace === 'assurance' ? assurance : isolation"
          @navigate="selectModule"
        />
      </template>
      <main class="amx-main">
        <IsolationNotices
          v-if="workspace === 'isolation' && role === 'client' && ready"
          :request="isolation"
          @open="openIsolationVisit"
        />
        <p v-if="calendarNotice" role="status">{{ calendarNotice }}</p>
        <p v-if="!ready" class="subtle">Chargement de votre espace…</p>
        <p v-if="error" role="alert" class="error">{{ error }}</p>
        <PortalInvitationAccept
          v-if="ready && inviteId"
          :id="inviteId"
          :token="inviteToken"
          :request="portal"
          @close="
            inviteId = '';
            inviteToken = '';
          "
        />
        <PortalRecovery
          v-else-if="ready && recoveryOpen"
          :uid="resetUid"
          :token="resetToken"
          :request="portal"
          @close="closeRecovery"
        />
        <template v-else-if="user">
          <div
            v-if="
              !['agenda-settings', 'client-folders'].includes(activeModule) ||
              passwordOpen ||
              managing
            "
            class="amx-heading"
          >
            <div>
              <p class="amx-eyebrow">{{ workspace ? title(workspace) : 'Orvia CRM' }}</p>
              <h1>
                {{ passwordOpen ? 'Mon compte' : managing ? 'Utilisateurs et accès' : pageTitle }}
              </h1>
              <p class="subtle">
                {{
                  passwordOpen
                    ? 'Gérez votre compte, vos sessions et vos agendas.'
                    : managing
                      ? 'Organisez les accès de votre équipe.'
                      : workspace
                        ? 'Votre activité, vos dossiers et vos prochaines actions.'
                        : 'Choisissez votre espace pour commencer.'
                }}
              </p>
            </div>
            <button
              v-if="workspace && !passwordOpen && !managing"
              class="secondary"
              :disabled="busy"
              @click="refreshWorkspace"
            >
              <RefreshCw :size="16" />Actualiser
            </button>
          </div>
          <div v-if="passwordOpen" class="crm-settings-page">
            <PortalPassword :request="portal" />
          </div>
          <PortalAccess
            class="crm-settings-page"
            v-else-if="managing"
            :spaces="user.admin_workspaces"
            :username="user.username"
            :request="portal"
          />
          <template v-else>
            <p v-if="busy" role="status">Chargement de votre espace…</p>
            <template v-if="workspace && summary">
              <IsolationAgenda
                v-if="
                  workspace === 'isolation' &&
                  activeModule === 'isolation-agenda' &&
                  ['client', 'administrator'].includes(role)
                "
                :request="isolation"
                :portal="portal"
                :role="role"
              />
              <IsolationCloserVisits
                v-else-if="
                  workspace === 'isolation' && role === 'closer' && activeModule === 'overview'
                "
                :request="isolation"
              /><CrmOverview
                v-else-if="activeModule === 'overview'"
                :workspace="workspace"
                :role="role"
                :summary="summary"
                :username="user.username"
                :request="workspace === 'assurance' ? assurance : isolation"
                @navigate="selectModule"
                @refresh="refreshWorkspace"
              >
                <template v-if="workspace === 'assurance'"
                  ><AssuranceAgreementAlerts
                    v-if="role === 'administrator'"
                    :request="assurance"
                    :refresh-version="notificationVersion"
                    @open="
                      agreementDeadline = $event;
                      assuranceModule = 'agreements';
                    " /><AssuranceReminders
                    v-if="role === 'administrator'"
                    :role="role"
                    :request="assurance" /><AssuranceNotifications
                    v-if="role !== 'advisor'"
                    :request="assurance"
                    :refresh-version="notificationVersion"
                    @open-tasks="selectModule('followups')" /><AssuranceAppointmentNotifications
                    v-if="role === 'setter'"
                    :request="assurance"
                    @open="openAssuranceAppointment"
                /></template>
                <IsolationNotices
                  v-else-if="workspace === 'isolation' && role === 'setter'"
                  :request="isolation"
                  @tasks="selectModule('followups')"
                />
              </CrmOverview>
              <section
                v-else
                :key="workspace + activeModule + contentVersion"
                class="card amx-workspace"
              >
                <div class="amx-content">
                  <ClientFolders
                    v-if="activeModule === 'client-folders' && role === 'administrator'"
                    :workspace="workspace === 'assurance' ? 'assurance' : 'isolation'"
                    :request="workspace === 'assurance' ? assurance : isolation"
                    :portal="portal"
                  />
                  <CallsCenter
                    v-else-if="activeModule === 'calls'"
                    :key="'calls-' + workspace"
                    :workspace="workspace"
                    :role="role"
                    :request="workspace === 'assurance' ? assurance : isolation"
                    :portal="portal"
                    @open-prospect="openProspect"
                  />
                  <template v-else-if="workspace === 'assurance'">
                    <AssuranceProspects
                      v-if="
                        assuranceModule === 'contacts' && ['setter', 'administrator'].includes(role)
                      "
                      :key="prospectFocus ? 'focus-' + prospectFocus.id : 'board'"
                      :focus="prospectFocus"
                      :portal="portal"
                      :request="assurance"
                      :role="role"
                      @imported="summary.contacts = $event"
                    />
                    <AssuranceAdvisorProspects
                      v-else-if="assuranceModule === 'contacts' && role === 'advisor'"
                      :portal="portal"
                      :request="assurance"
                      :username="user.username"
                    />
                    <AssuranceContacts
                      v-else-if="assuranceModule === 'contacts'"
                      :portal="portal"
                      :request="assurance"
                      :role="role"
                      @imported="summary.contacts = $event"
                    />
                    <AssuranceAgreementRegistry
                      v-else-if="assuranceModule === 'agreements' && role === 'administrator'"
                      :key="agreementDeadline"
                      :initial-deadline="agreementDeadline"
                      :request="assurance"
                      :portal="portal"
                      @changed="refreshAssurance"
                    />
                    <AssuranceAssignments
                      v-else-if="assuranceModule === 'assignments' && role !== 'advisor'"
                      @navigate="selectModule"
                      :request="assurance"
                      :portal="portal"
                      :role="role"
                    />
                    <AssuranceSetterTasks
                      v-else-if="
                        assuranceModule === 'followups' &&
                        ['setter', 'administrator'].includes(role)
                      "
                      :role="role"
                      :portal="portal"
                      :request="assurance"
                      @changed="refreshAssurance"
                      @navigate="selectModule"
                    />
                    <AssuranceFollowUps
                      v-else-if="assuranceModule === 'followups' && role !== 'advisor'"
                      :portal="portal"
                      :role="role"
                      :request="assurance"
                      @changed="refreshAssurance"
                    />
                    <AssuranceCompensation
                      v-else-if="assuranceModule === 'compensation' && role === 'administrator'"
                      :request="assurance"
                      :portal="portal"
                    />
                    <AssuranceStatistics
                      v-else-if="assuranceModule === 'statistics' && role !== 'advisor'"
                      :role="role"
                      :request="assurance"
                      :username="user?.username || ''"
                    />
                    <AssuranceFieldSettings
                      v-else-if="assuranceModule === 'fields' && role === 'administrator'"
                      :request="assurance"
                    />
                    <CrmAppointmentsCalendar
                      v-else-if="['setter', 'administrator', 'advisor'].includes(role)"
                      workspace="assurance"
                      :appointment-id="appointmentFocus"
                      :request="assurance"
                      :portal="portal"
                      :role="role"
                      :username="user?.username || ''"
                      @navigate="selectModule"
                    />
                    <AssuranceAppointments
                      v-else
                      :request="assurance"
                      :portal="portal"
                      :role="role"
                    />
                  </template>
                  <template v-else>
                    <IsolationStatistics
                      v-if="isolationModule === 'statistics'"
                      :role="role"
                      :request="isolation"
                      :username="user?.username || ''"
                    />
                    <IsolationTasksBoard
                      v-else-if="
                        isolationModule === 'followups' &&
                        ['setter', 'administrator'].includes(role)
                      "
                      :role="role"
                      :request="isolation"
                      @navigate="selectModule"
                      @saved="refreshIsolation"
                    /><IsolationQualification
                      v-else-if="isolationModule === 'qualification' && role === 'administrator'"
                      :request="isolation"
                    />
                    <CrmAppointmentsCalendar
                      v-else-if="
                        isolationModule === 'appointments' &&
                        ['setter', 'administrator'].includes(role)
                      "
                      workspace="isolation"
                      :role="role"
                      :portal="portal"
                      :request="isolation"
                      @navigate="selectModule"
                      @changed="refreshIsolation"
                    />
                    <IsolationVisits
                      v-else-if="['appointments', 'visit-history'].includes(isolationModule)"
                      :key="`${isolationModule}-${appointmentFocus || 0}`"
                      :period="
                        appointmentFocus
                          ? undefined
                          : isolationModule === 'visit-history'
                            ? 'history'
                            : 'upcoming'
                      "
                      :visit-id="appointmentFocus || undefined"
                      :role="role"
                      :portal="portal"
                      :request="isolation"
                      @close="selectModule('overview')"
                      @changed="refreshIsolation"
                    />
                    <IsolationClient
                      v-else-if="role === 'client'"
                      :portal="portal"
                      :request="isolation"
                    />
                    <IsolationWorkQueue
                      v-else
                      :key="prospectFocus ? 'focus-' + prospectFocus.id : 'board'"
                      :focus="prospectFocus"
                      :role="role"
                      :portal="portal"
                      :request="isolation"
                    />
                  </template>
                </div>
              </section>
            </template>
          </template>
        </template></main
    ></CrmShell>
    <footer v-if="!user && (recoveryOpen || inviteId)" class="amx-footer">
      Orvia · Votre espace de travail.
    </footer>
  </div>
</template>
<style>
.amx-root {
  min-height: 100vh;
  background: #f6f5ed;
  color: #20271e;
}
.amx-header {
  height: 86px;
  display: flex;
  align-items: center;
  gap: 25px;
  border-bottom: 1px solid #e6e5d9;
  padding: 0 6vw;
}
.amx-brand {
  display: flex;
  gap: 10px;
  align-items: center;
  font-size: 26px;
  font-weight: 800;
  color: #303d20;
  text-decoration: none;
}
.amx-brand span {
  font-size: 12px;
  letter-spacing: 2px;
  color: #7c806d;
}
.amx-header-note {
  color: #7c806d;
  font-size: 13px;
  flex: 1;
}
.amx-main {
  max-width: 1100px;
  margin: auto;
  padding: 64px 28px;
  min-height: calc(100vh - 150px);
}
.amx-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 40px;
}
.amx-heading h1,
.amx-login h1 {
  font-size: 38px;
  letter-spacing: -1.3px;
  margin: 10px 0 15px;
}
.amx-eyebrow {
  color: #777f65;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1.8px;
}
.amx-login {
  max-width: 420px;
  margin: 40px auto 70px;
}
.crm-legacy-link {
  margin-top: 26px;
  padding: 16px;
  border-top: 1px solid #e5e8dc;
  font-size: 12px;
  color: #7b876b;
}
.crm-legacy-link summary {
  cursor: pointer;
  font-weight: 600;
}
.is-authenticated .amx-footer {
  display: none;
}
.amx-login form {
  display: grid;
  gap: 22px;
  margin-top: 32px;
}
.amx-root label {
  display: grid;
  gap: 9px;
  font-size: 13px;
  font-weight: 600;
}
.amx-root input {
  padding: 13px 15px;
  border: 1px solid #dedfce;
  border-radius: 11px;
  background: #fff;
  width: 100%;
  color: #20271e;
}
.amx-footnote,
.amx-footer {
  font-size: 12px;
  color: #868c77;
  line-height: 1.7;
}
.amx-footnote {
  margin-top: 25px;
}
.amx-footer {
  text-align: center;
  padding: 16px;
}
.amx-content {
  padding: 28px;
}
.amx-count {
  display: flex;
  gap: 15px;
  align-items: center;
}
.amx-count strong {
  font-size: 32px;
}
.amx-count span {
  color: #777f65;
}
.amx-contact-form {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: 18px;
  align-items: end;
  margin: 30px 0;
}
.amx-content small {
  display: block;
  margin-top: 12px;
}
@media (max-width: 650px) {
  .amx-header-note {
    display: none;
  }
  .amx-header {
    justify-content: space-between;
    padding: 0 20px;
  }
  .amx-heading {
    align-items: start;
    flex-direction: column;
  }
  .amx-main {
    padding: 35px 20px;
  }
  .amx-contact-form {
    grid-template-columns: 1fr;
  }
}
</style>
