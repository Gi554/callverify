<script setup lang="ts">
// Task alerts for Assurance setters and administrators: badge and panel on the bell, a banner
// for new tasks, a once-per-session reminder of overdue tasks and optional browser notifications.
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { Bell, X, ArrowRight, Clock3, BellRing } from 'lucide-vue-next';
const props = defineProps<{
  workspace: string;
  role: string;
  username: string;
  request: (path: string, body?: any, method?: string) => Promise<any>;
}>();
const emit = defineEmits<{ navigate: [value: string] }>();
const POLL_MS = 30000;
const unread = ref(0),
  overdue = ref(0),
  recent = ref<any[]>([]),
  open = ref(false),
  banners = ref<any[]>([]),
  overduePrompt = ref(false),
  permission = ref(typeof Notification === 'undefined' ? 'unsupported' : Notification.permission);
let known: Set<number> | null = null,
  timer: ReturnType<typeof setInterval> | undefined,
  disposed = false;
const promptKey = computed(() => `amx-overdue-prompt:${props.workspace}:${props.username}`);
const badge = computed(() => (unread.value > 99 ? '99+' : String(unread.value)));
const teamWord = computed(() => (props.role === 'administrator' ? 'de l’équipe' : ''));
function due(row: any) {
  return row.due_at
    ? new Intl.DateTimeFormat('fr-FR', { dateStyle: 'short', timeStyle: 'short' }).format(
        new Date(row.due_at),
      )
    : '';
}
function prospect(row: any) {
  return row.contact_name || 'Prospect sans nom';
}
function announce(row: any) {
  banners.value = [...banners.value.slice(-2), row];
  if (permission.value === 'granted' && document.hidden) {
    try {
      new Notification(`Orvia · ${row.label}`, { body: prospect(row), tag: `amx-task-${row.id}` });
    } catch {
      /* Browsers may refuse notifications outside a service worker: the banner remains. */
    }
  }
}
const isolation = computed(() => props.workspace === 'isolation');
const priorities: Record<string, string> = {
  low: 'basse',
  normal: 'normale',
  high: 'haute',
  urgent: 'urgente',
};
// Assurance has a notification inbox with read receipts.
async function loadAssurance() {
  const [summary, tasks, list] = await Promise.all([
    props.request('notifications/summary/'),
    props.request('follow-ups/summary/'),
    props.request('notifications/?state=open&unread=true'),
  ]);
  unread.value = summary.unread_open;
  overdue.value = tasks.overdue;
  return list;
}
// Isolation has no inbox: open reminders, newest first, stand in for notifications and the
// badge counts overdue reminders.
async function loadIsolation() {
  const [late, list] = await Promise.all([
    props.request('follow-ups/?state=overdue'),
    props.request('follow-ups/?state=open&order=recent'),
  ]);
  overdue.value = late.count;
  unread.value = late.count;
  return {
    results: list.results.map((row: any) => ({
      id: row.id,
      label: 'Rappel à effectuer',
      contact_name: row.prospect_name,
      priority: '',
      late: row.overdue,
      due_at: row.due_at,
    })),
  };
}
const badgeLabel = computed(() =>
  isolation.value
    ? `${unread.value} rappel(s) en retard`
    : `${unread.value} notification(s) non lue(s)`,
);
async function refresh() {
  try {
    const list = isolation.value ? await loadIsolation() : await loadAssurance();
    if (disposed) return;
    recent.value = list.results.slice(0, 6);
    // The first load only remembers what exists: banners are for notifications arriving later.
    if (known) for (const row of list.results) if (!known.has(row.id)) announce(row);
    known = new Set([...(known || []), ...list.results.map((row: any) => row.id)]);
    let prompted = false;
    try {
      prompted = sessionStorage.getItem(promptKey.value) === '1';
    } catch {
      prompted = false;
    }
    if (overdue.value > 0 && !prompted) {
      overduePrompt.value = true;
      try {
        sessionStorage.setItem(promptKey.value, '1');
      } catch {
        /* Without storage the reminder may come back after a reload. */
      }
    }
  } catch {
    /* Alerts are best effort: the tasks screen remains the reference. */
  }
}
async function openTask(row: any) {
  banners.value = banners.value.filter((item) => item.id !== row.id);
  open.value = false;
  try {
    if (!isolation.value) await props.request(`notifications/${row.id}/read/`, {});
  } catch {
    /* Reading is optional: the task stays open until it is closed. */
  }
  emit('navigate', 'followups');
  void refresh();
}
function goToTasks() {
  open.value = false;
  overduePrompt.value = false;
  emit('navigate', 'followups');
}
async function enableBrowser() {
  if (typeof Notification === 'undefined') return;
  permission.value = await Notification.requestPermission();
}
function closeOnEscape(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    open.value = false;
    overduePrompt.value = false;
  }
}
onMounted(() => {
  void refresh();
  timer = setInterval(() => void refresh(), POLL_MS);
  window.addEventListener('keydown', closeOnEscape);
});
onBeforeUnmount(() => {
  disposed = true;
  if (timer) clearInterval(timer);
  window.removeEventListener('keydown', closeOnEscape);
});
</script>

<template>
  <div class="task-alerts">
    <button
      type="button"
      class="alerts-bell"
      :aria-expanded="open"
      :aria-label="unread ? badgeLabel : 'Notifications'"
      :title="unread ? badgeLabel : 'Notifications'"
      @click="open = !open"
    >
      <Bell :size="22" /><span v-if="unread" class="alerts-badge">{{ badge }}</span>
    </button>
    <section v-if="open" class="alerts-panel" aria-label="Notifications">
      <header>
        <strong>Notifications</strong>
        <button type="button" class="alerts-close" aria-label="Fermer" @click="open = false">
          <X :size="16" />
        </button>
      </header>
      <button v-if="overdue" type="button" class="alerts-overdue" @click="goToTasks">
        <Clock3 :size="16" />{{ overdue }} tâche(s) {{ teamWord }} en retard<ArrowRight
          :size="15"
        />
      </button>
      <ul>
        <li v-for="row in recent" :key="row.id">
          <button type="button" @click="openTask(row)">
            <strong>{{ row.label }}</strong>
            <span>{{ prospect(row) }}</span>
            <small :class="[row.priority, { high: row.late }]"
              >Échéance {{ due(row)
              }}<template v-if="row.priority">
                · priorité {{ priorities[row.priority] || row.priority }}</template
              ><template v-if="row.late"> · en retard</template></small
            >
          </button>
        </li>
        <li v-if="!recent.length" class="alerts-empty">
          {{ isolation ? 'Aucun rappel ouvert.' : 'Aucune nouvelle notification.' }}
        </li>
      </ul>
      <footer>
        <button type="button" class="secondary" @click="goToTasks">Voir mes tâches</button>
        <button
          v-if="permission === 'default'"
          type="button"
          class="secondary alerts-browser"
          @click="enableBrowser"
        >
          <BellRing :size="15" />Activer les notifications du navigateur
        </button>
        <small v-else-if="permission === 'granted'">Notifications du navigateur activées.</small>
        <small v-else-if="permission === 'denied'"
          >Notifications bloquées dans les réglages du navigateur.</small
        >
      </footer>
    </section>
    <div class="alerts-banners" aria-live="polite">
      <article v-for="row in banners" :key="row.id" class="alerts-banner" role="status">
        <span class="banner-icon"><Bell :size="16" /></span>
        <div>
          <strong>Nouvelle tâche · {{ row.label }}</strong>
          <span>{{ prospect(row) }} · échéance {{ due(row) }}</span>
        </div>
        <button type="button" class="primary" @click="openTask(row)">Ouvrir</button>
        <button
          type="button"
          class="alerts-close"
          aria-label="Fermer l’alerte"
          @click="banners = banners.filter((item) => item.id !== row.id)"
        >
          <X :size="16" />
        </button>
      </article>
    </div>
    <div v-if="overduePrompt" class="alerts-backdrop" @click.self="overduePrompt = false">
      <section class="alerts-modal" role="dialog" aria-modal="true" aria-labelledby="overdue-title">
        <span class="modal-icon"><Clock3 :size="22" /></span>
        <h2 id="overdue-title">{{ overdue }} tâche(s) {{ teamWord }} en retard</h2>
        <p>Des rappels ont dépassé leur échéance. Traitez-les pour ne perdre aucun prospect.</p>
        <div class="modal-actions">
          <button type="button" class="secondary" @click="overduePrompt = false">Plus tard</button>
          <button type="button" class="primary" @click="goToTasks">Traiter maintenant</button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.task-alerts {
  position: relative;
  display: inline-flex;
}
.alerts-bell {
  position: relative;
  display: grid;
  place-items: center;
  border: 0;
  background: none;
  color: inherit;
  cursor: pointer;
}
.alerts-badge {
  position: absolute;
  top: -6px;
  right: -8px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 99px;
  background: #d92d20;
  color: white;
  font-size: 11px;
  font-weight: 700;
  line-height: 18px;
  text-align: center;
  box-sizing: border-box;
}
.alerts-panel {
  position: absolute;
  top: calc(100% + 12px);
  right: -12px;
  z-index: 60;
  display: grid;
  gap: 10px;
  width: min(360px, calc(100vw - 24px));
  padding: 14px;
  border: 1px solid #e3e7ee;
  border-radius: 14px;
  background: white;
  box-shadow: 0 12px 32px #1f2f4524;
  color: #1f2f45;
  text-align: left;
}
.alerts-panel header,
.alerts-panel footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.alerts-close {
  display: grid;
  place-items: center;
  border: 0;
  background: none;
  color: #6b7686;
  cursor: pointer;
}
.alerts-overdue {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid #f4c38b;
  border-radius: 10px;
  background: #fffaf3;
  color: #8a4b0c;
  font-weight: 600;
  cursor: pointer;
}
.alerts-overdue svg:last-child {
  margin-left: auto;
}
.alerts-panel ul {
  display: grid;
  gap: 4px;
  max-height: 320px;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  list-style: none;
}
.alerts-panel li button {
  display: grid;
  gap: 2px;
  width: 100%;
  padding: 10px 12px;
  border: 0;
  border-radius: 10px;
  background: #f6f8fb;
  color: #1f2f45;
  text-align: left;
  cursor: pointer;
}
.alerts-panel li button:hover {
  background: #eef2f8;
}
.alerts-panel li span,
.alerts-panel small {
  color: #5b6b82;
  font-size: 12px;
}
.alerts-panel small.urgent,
.alerts-panel small.high {
  color: #b42318;
}
.alerts-empty {
  padding: 14px;
  color: #6b7686;
  text-align: center;
}
.alerts-browser {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.alerts-banners {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 70;
  display: grid;
  gap: 10px;
  width: min(420px, calc(100vw - 32px));
}
.alerts-banner {
  display: grid;
  grid-template-columns: auto 1fr auto auto;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border: 1px solid #c9dbf5;
  border-radius: 14px;
  background: white;
  box-shadow: 0 12px 28px #1f2f4524;
  color: #1f2f45;
  text-align: left;
}
.alerts-banner div {
  display: grid;
  gap: 2px;
  min-width: 0;
}
.alerts-banner span:not(.banner-icon) {
  color: #5b6b82;
  font-size: 12px;
}
.banner-icon,
.modal-icon {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: #e7f0fd;
  color: #1f5fa8;
}
.alerts-backdrop {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: grid;
  place-items: center;
  padding: 16px;
  background: #0f1b2b66;
}
.alerts-modal {
  display: grid;
  justify-items: start;
  gap: 10px;
  width: min(420px, 100%);
  padding: 22px;
  border-radius: 16px;
  background: white;
  color: #1f2f45;
  text-align: left;
}
.alerts-modal .modal-icon {
  background: #fdeedd;
  color: #b4610c;
}
.alerts-modal h2 {
  margin: 4px 0 0;
  font-size: 18px;
}
.alerts-modal p {
  margin: 0;
  color: #5b6b82;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  width: 100%;
  margin-top: 6px;
}
@media (max-width: 760px) {
  .alerts-panel {
    position: fixed;
    top: 72px;
    right: 12px;
  }
  .alerts-banners {
    right: 12px;
    bottom: 12px;
  }
}
</style>
