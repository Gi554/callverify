<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';
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
  <section aria-label="Notifications de suivi Assurance">
    <h3>Notifications de suivi</h3>
    <p role="status">
      {{ summary.open }} notification(s) liée(s) à un suivi ouvert · {{ summary.unread_open }} non
      lue(s).
    </p>
    <p>
      Marquer comme lu ne clôture jamais une tâche. Les alertes restent actives jusqu’à sa
      résolution.
    </p>
    <p v-if="error" role="alert">{{ error }}</p>
    <button
      class="secondary"
      :disabled="busy"
      @click="
        expanded = !expanded;
        page = 1;
        refresh();
      "
    >
      {{ expanded ? 'Masquer les notifications' : 'Voir les notifications' }}</button
    ><button class="secondary" :disabled="busy" @click="refresh">Actualiser</button
    ><button class="secondary" @click="$emit('openTasks')">Ouvrir les tâches de suivi</button>
    <section v-if="expanded">
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
      ><label
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
      <article v-for="row in rows" :key="row.id">
        <h4>{{ row.label }} · Tâche {{ row.task_id }}</h4>
        <p>
          {{ new Date(row.created_at).toLocaleString('fr-FR') }} ·
          {{ row.resolved ? 'Suivi résolu' : 'Suivi ouvert' }} · Priorité {{ row.priority }} ·
          Échéance {{ new Date(row.due_at).toLocaleString('fr-FR') }}
        </p>
        <p v-if="row.read_at">Lue le {{ new Date(row.read_at).toLocaleString('fr-FR') }}</p>
        <button v-else class="secondary" :disabled="busy" @click="read(row)">
          Marquer comme lue
        </button>
      </article>
      <p v-if="!rows.length">Aucune notification pour ces filtres.</p>
      <p>{{ count }} notification(s) · page {{ page }}</p>
      <button
        class="secondary"
        :disabled="busy || page === 1"
        @click="
          page--;
          refresh();
        "
      >
        Précédent</button
      ><button
        class="secondary"
        :disabled="busy || page * 25 >= count"
        @click="
          page++;
          refresh();
        "
      >
        Suivant
      </button>
    </section>
  </section>
</template>
