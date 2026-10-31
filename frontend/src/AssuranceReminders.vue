<script setup lang="ts">
// Administrator only: how often reminders are produced and how many escalations are active.
import { ref, onMounted, onUnmounted } from 'vue';
import { RefreshCw } from 'lucide-vue-next';
const props = defineProps<{ role: string; request: (path: string, body?: any) => Promise<any> }>();
const busy = ref(false),
  error = ref(''),
  message = ref(''),
  rules = ref<any>(null),
  reason = ref(''),
  editing = ref(false),
  escalationCount = ref<number | null>(null);
let timer: ReturnType<typeof setInterval> | undefined;
async function refresh() {
  if (busy.value || props.role !== 'administrator') return;
  busy.value = true;
  error.value = '';
  try {
    escalationCount.value = (await props.request('reminders/?category=escalations')).count;
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function configure() {
  busy.value = true;
  error.value = '';
  try {
    rules.value = await props.request('reminder-policy/');
    reason.value = '';
    editing.value = true;
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function save() {
  busy.value = true;
  error.value = '';
  message.value = '';
  try {
    rules.value = await props.request('reminder-policy/', { ...rules.value, reason: reason.value });
    message.value =
      'Règles enregistrées. Le worker produira les rappels applicables lors de son prochain passage.';
    editing.value = false;
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
  await refresh();
}
onMounted(() => {
  refresh();
  timer = setInterval(() => {
    if (!document.hidden) refresh();
  }, 60000);
});
onUnmounted(() => {
  if (timer) clearInterval(timer);
});
</script>
<template>
  <div v-if="role === 'administrator'" class="alert-card" aria-label="Rappels automatiques">
    <header>
      <h3>Rappels automatiques</h3>
      <button
        type="button"
        class="alert-refresh"
        :disabled="busy"
        title="Actualiser"
        aria-label="Actualiser les escalades"
        @click="refresh"
      >
        <RefreshCw :size="15" />
      </button>
    </header>
    <div class="alert-tiles one">
      <div class="alert-tile" :class="escalationCount ? 'warning' : 'static'">
        <strong>{{ escalationCount ?? '—' }}</strong
        ><span>Escalade(s) administrative(s) active(s)</span>
      </div>
    </div>
    <p v-if="error" role="alert" class="alert-error">{{ error }}</p>
    <p v-if="message" role="status" class="alert-ok">{{ message }}</p>
    <div v-if="!editing" class="alert-actions">
      <button type="button" class="secondary" :disabled="busy" @click="configure">
        Régler les rappels
      </button>
    </div>
    <form v-if="editing && rules" class="reminder-form" @submit.prevent="save">
      <h4>Cadence des rappels</h4>
      <p>
        Les changements invalident les anciens rappels. Les nouveaux sont générés par le worker ;
        aucune clôture automatique.
      </p>
      <label class="check"
        ><input v-model="rules.tasks_enabled" type="checkbox" :disabled="busy" />Rappeler les tâches
        en retard</label
      ><label
        >Intervalle des tâches (heures)<input
          v-model.number="rules.task_interval_hours"
          type="number"
          min="1"
          max="720"
          required
          :disabled="busy" /></label
      ><label class="check"
        ><input v-model="rules.reports_enabled" type="checkbox" :disabled="busy" />Rappeler les
        comptes rendus manquants</label
      ><label
        >Heure limite le lendemain du RDV (Québec)<input
          v-model="rules.report_cutoff_time"
          type="time"
          required
          :disabled="busy"
      /></label>
      <p>
        Une seule relance par rendez-vous sans compte rendu, le lendemain à 18 h au Québec par
        défaut. Les rendez-vous annulés ou déjà renseignés ne sont pas relancés.
      </p>
      <h4>Escalades administrateur</h4>
      <p>
        Désactivées initialement. Les seuils s’ajoutent à l’échéance de la tâche ou au délai initial
        du compte rendu ; les rappels du type doivent être actifs.
      </p>
      <label class="check"
        ><input v-model="rules.escalations_enabled" type="checkbox" :disabled="busy" />Activer les
        escalades</label
      ><label
        >Retard de tâche avant escalade (heures)<input
          v-model.number="rules.task_escalation_hours"
          type="number"
          min="1"
          max="2160"
          required
          :disabled="busy" /></label
      ><label
        >Délai supplémentaire pour compte rendu (heures)<input
          v-model.number="rules.report_escalation_hours"
          type="number"
          min="1"
          max="2160"
          required
          :disabled="busy" /></label
      ><label
        >Intervalle des escalades (heures)<input
          v-model.number="rules.escalation_interval_hours"
          type="number"
          min="1"
          max="720"
          required
          :disabled="busy" /></label
      ><label
        >Motif obligatoire<textarea
          v-model="reason"
          required
          maxlength="1000"
          :disabled="busy"
        ></textarea>
      </label>
      <div class="alert-actions">
        <button class="primary" :disabled="busy">Enregistrer</button
        ><button type="button" class="secondary" :disabled="busy" @click="editing = false">
          Annuler
        </button>
      </div>
    </form>
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
.alert-tile {
  display: grid;
  gap: 4px;
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
.alert-ok {
  margin: 0;
  color: #067647;
  font-size: 13px;
}
.alert-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.reminder-form {
  display: grid;
  gap: 12px;
  padding-top: 14px;
  border-top: 1px solid #f0edf6;
  font-size: 12px;
  color: #5b4f68;
}
.reminder-form h4 {
  margin: 6px 0 0;
  font-size: 13px;
  color: #2d2640;
}
.reminder-form p {
  margin: 0;
  line-height: 1.6;
  color: #7a6d86;
}
.reminder-form label {
  display: grid;
  gap: 4px;
}
.reminder-form label.check {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
