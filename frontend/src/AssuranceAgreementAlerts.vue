<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue';
import { RefreshCw } from 'lucide-vue-next';
const props = defineProps<{
  request: (path: string, body?: any, method?: string) => Promise<any>;
  refreshVersion: number;
}>();
const emit = defineEmits<{ open: [deadline: string] }>();
const data = ref<any>(null),
  error = ref(''),
  busy = ref(false);
let timer: ReturnType<typeof setInterval> | undefined;
async function load() {
  if (busy.value) return;
  busy.value = true;
  error.value = '';
  try {
    data.value = await props.request('agreement-deadlines/');
  } catch (e: any) {
    data.value = null;
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
watch(
  () => props.refreshVersion,
  () => load(),
);
onMounted(() => {
  void load();
  timer = setInterval(() => {
    if (document.visibilityState === 'visible') void load();
  }, 60000);
});
onBeforeUnmount(() => {
  if (timer) clearInterval(timer);
});
</script>
<template>
  <div class="alert-card" aria-label="Échéances des mandats et contrats">
    <header>
      <h3>Échéances des mandats et contrats</h3>
      <button
        type="button"
        class="alert-refresh"
        :disabled="busy"
        title="Actualiser les échéances"
        aria-label="Actualiser les échéances"
        @click="load"
      >
        <RefreshCw :size="15" />
      </button>
    </header>
    <p v-if="error" role="alert" class="alert-error">Échéances indisponibles : {{ error }}</p>
    <template v-if="data">
      <p class="sr-only" role="status">
        {{ data.overdue }} suivi(s) avec date de fin dépassée, {{ data.upcoming }} échéance(s) dans
        les 30 jours, {{ data.undated }} suivi(s) sans date de fin.
      </p>
      <div class="alert-tiles">
        <button
          type="button"
          class="alert-tile"
          :class="{ danger: data.overdue > 0 }"
          @click="emit('open', 'overdue')"
        >
          <strong>{{ data.overdue }}</strong
          ><span>Date de fin dépassée</span>
        </button>
        <button
          type="button"
          class="alert-tile"
          :class="{ warning: data.upcoming > 0 }"
          @click="emit('open', 'upcoming')"
        >
          <strong>{{ data.upcoming }}</strong
          ><span>Dans les 30 jours</span>
        </button>
        <div class="alert-tile static">
          <strong>{{ data.undated }}</strong
          ><span>Sans date de fin</span>
        </div>
      </div>
      <p class="alert-foot">
        Situation au {{ data.as_of }} (UTC), suivis « En suivi » uniquement. Consulter une alerte ne
        la supprime pas.
      </p>
    </template>
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
.alert-tiles {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.alert-tile {
  display: grid;
  gap: 4px;
  align-content: start;
  min-height: 0;
  padding: 14px 12px;
  border: 1px solid #ece8f4;
  border-radius: 14px;
  background: #faf9fd;
  color: #4a3f58;
  text-align: left;
  font: inherit;
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
button.alert-tile {
  cursor: pointer;
}
button.alert-tile:hover {
  border-color: #cfc4e6;
}
.alert-tile.danger {
  border-color: #f4c7c3;
  background: #fff3f1;
}
.alert-tile.danger strong {
  color: #b42318;
}
.alert-tile.warning {
  border-color: #f6dca8;
  background: #fff9ec;
}
.alert-tile.warning strong {
  color: #b54708;
}
.alert-error {
  margin: 0;
  color: #b42318;
  font-size: 13px;
}
.alert-foot {
  margin: 0;
  color: #96899f;
  font-size: 11px;
  line-height: 1.6;
}
@media (max-width: 480px) {
  .alert-tiles {
    grid-template-columns: 1fr;
  }
  .alert-tile {
    grid-template-columns: auto 1fr;
    align-items: center;
    gap: 12px;
  }
}
</style>
