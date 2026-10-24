<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';
import { RefreshCw } from 'lucide-vue-next';
const props = defineProps<{
  request: (path: string, body?: any) => Promise<any>;
  refreshVersion?: number;
}>();
defineEmits<{ openTasks: [] }>();
const expanded = ref(false),
  summary = ref({ open: 0, unread_open: 0 }),
  rows = ref<any[]>([]),
  count = ref(0),
  page = ref(1),
  state = ref('open'),
  unread = ref(false),
  busy = ref(false),
  error = ref('');
let timer: ReturnType<typeof setInterval> | undefined;
async function refresh() {
  if (busy.value) return;
  busy.value = true;
  error.value = '';
  try {
    summary.value = await props.request('notifications/summary/');
    if (expanded.value) {
      const data = await props.request(
        `notifications/?page=${page.value}&state=${state.value}&unread=${unread.value}`,
      );
      rows.value = data.results;
      count.value = data.count;
    }
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function read(row: any) {
  busy.value = true;
  error.value = '';
  try {
    await props.request(`notifications/${row.id}/read/?state=all`, {});
    if (unread.value) page.value = 1;
  } catch (e: any) {
    error.value = e.message;
    return;
  } finally {
    busy.value = false;
  }
  await refresh();
}
const when = (value: string) => new Date(value).toLocaleString('fr-FR');
onMounted(() => {
  refresh();
  timer = setInterval(() => {
    if (!document.hidden) refresh();
  }, 30000);
});
onUnmounted(() => {
  if (timer) clearInterval(timer);
});
watch(() => props.refreshVersion, refresh);
</script>
<template>
  <div class="alert-card" aria-label="Notifications de suivi Assurance">
    <header>
      <h3>Notifications de suivi</h3>
      <button
        type="button"
        class="alert-refresh"
        :disabled="busy"
        title="Actualiser les notifications"
        aria-label="Actualiser les notifications"
        @click="refresh"
      >
        <RefreshCw :size="15" />
      </button>
    </header>
    <p class="sr-only" role="status">
      {{ summary.open }} notification(s) liée(s) à un suivi ouvert, {{ summary.unread_open }} non
      lue(s).
    </p>
    <div class="alert-tiles two">
      <div class="alert-tile static">
        <strong>{{ summary.open }}</strong
        ><span>Liées à un suivi ouvert</span>
      </div>
      <div class="alert-tile" :class="summary.unread_open > 0 ? 'info' : 'static'">
        <strong>{{ summary.unread_open }}</strong
        ><span>Non lues</span>
      </div>
    </div>
    <p v-if="error" role="alert" class="alert-error">{{ error }}</p>
    <div class="alert-actions">
      <button
        type="button"
        class="secondary"
        :disabled="busy"
        @click="
          expanded = !expanded;
          page = 1;
          refresh();
        "
      >
        {{ expanded ? 'Masquer les notifications' : 'Voir les notifications' }}</button
      ><button type="button" class="primary" @click="$emit('openTasks')">
        Ouvrir les tâches de suivi
      </button>
    </div>
    <div v-if="expanded" class="alert-list">
      <div class="alert-filters">
        <label
          >État du suivi<select
            v-model="state"
            :disabled="busy"
            @change="
              page = 1;
              refresh();
            "
          >
            <option value="open">Ouvert</option>
            <option value="resolved">Résolu</option>
            <option value="all">Tous</option>
          </select></label
        ><label class="check"
          ><input
            v-model="unread"
            type="checkbox"
            :disabled="busy"
            @change="
              page = 1;
              refresh();
            "
          />Non lues uniquement</label
        >
      </div>
      <ul>
        <li v-for="row in rows" :key="row.id">
          <div>
            <strong>{{ row.label }} · Tâche {{ row.task_id }}</strong>
            <small
              >{{ when(row.created_at) }} · {{ row.resolved ? 'Suivi résolu' : 'Suivi ouvert' }} ·
              Priorité {{ row.priority }} · Échéance {{ when(row.due_at) }}</small
            >
          </div>
          <small v-if="row.read_at" class="read">Lue le {{ when(row.read_at) }}</small>
          <button v-else type="button" class="secondary" :disabled="busy" @click="read(row)">
            Marquer comme lue
          </button>
        </li>
        <li v-if="!rows.length" class="empty">Aucune notification pour ces filtres.</li>
      </ul>
      <footer>
        <span>{{ count }} notification(s) · page {{ page }}</span
        ><button
          type="button"
          class="secondary"
          :disabled="busy || page === 1"
          @click="
            page--;
            refresh();
          "
        >
          Précédent</button
        ><button
          type="button"
          class="secondary"
          :disabled="busy || page * 25 >= count"
          @click="
            page++;
            refresh();
          "
        >
          Suivant
        </button>
      </footer>
    </div>
  </div>
</template>
<style scoped>
.alert-card {
  display: grid;
  gap: 14px;
  align-content: start;
  min-width: 0;
  padding: 18px;
  border: 1px solid #ece8f4;
  border-radius: 16px;
  background: #fff;
}
.alert-card header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.alert-card h3 {
  margin: 0;
  font-size: 14px;
  color: #2d2640;
}
.alert-refresh {
  display: grid;
  place-items: center;
  flex: none;
  width: 32px;
  height: 32px;
  min-height: 0;
  padding: 0;
  border: 1px solid #e4dff0;
  border-radius: 10px;
  background: #faf8fe;
  color: #7a6d86;
}
.alert-tiles.two {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.alert-tile {
  display: grid;
  gap: 4px;
  align-content: start;
  padding: 14px 12px;
  border: 1px solid #ece8f4;
  border-radius: 14px;
  background: #faf9fd;
}
.alert-tile strong {
  font-size: 26px;
  line-height: 1;
  color: #2d2640;
}
.alert-tile span {
  font-size: 12px;
  line-height: 1.35;
  color: #7a6d86;
}
.alert-tile.info {
  border-color: #c9dafb;
  background: #f1f6ff;
}
.alert-tile.info strong {
  color: #1d4ed8;
}
.alert-error {
  margin: 0;
  color: #b42318;
  font-size: 13px;
}
.alert-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.alert-list {
  display: grid;
  gap: 12px;
  padding-top: 4px;
  border-top: 1px solid #f0edf6;
}
.alert-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: 12px 16px;
  font-size: 12px;
  color: #7a6d86;
}
.alert-filters label {
  display: grid;
  gap: 4px;
}
.alert-filters label.check {
  display: flex;
  align-items: center;
  gap: 6px;
}
.alert-list ul {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.alert-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid #f0edf6;
  border-radius: 12px;
  background: #fcfbfe;
}
.alert-list li > div {
  display: grid;
  gap: 3px;
  min-width: 0;
}
.alert-list li strong {
  font-size: 13px;
  color: #2d2640;
}
.alert-list small {
  font-size: 11px;
  line-height: 1.5;
  color: #96899f;
}
.alert-list li.empty {
  justify-content: center;
  color: #96899f;
  font-size: 12px;
}
.alert-list footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #7a6d86;
}
.alert-list footer span {
  margin-right: auto;
}
@media (max-width: 520px) {
  .alert-list li {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
