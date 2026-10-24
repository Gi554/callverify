<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { CalendarDays, Clock3, Link2, Plus, Save, X } from 'lucide-vue-next';
import PortalCalendars from './PortalCalendars.vue';
import SidePanel from './SidePanel.vue';
const props = defineProps<{
  request: (path: string, body?: any) => Promise<any>;
  portal: (path: string, body?: any) => Promise<any>;
}>();
const days = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche'];
const zones = [
  'America/Toronto',
  'America/Vancouver',
  'America/Edmonton',
  'America/Winnipeg',
  'America/Halifax',
  'America/St_Johns',
  'Europe/Paris',
];
const value = ref<any>(null),
  draft = ref<any>(null),
  busy = ref(false),
  error = ref(''),
  message = ref(''),
  tab = ref('hours');
const base = ref('');
const dirty = computed(() => !!draft.value && JSON.stringify(draft.value) !== base.value);
async function load() {
  busy.value = true;
  error.value = '';
  try {
    value.value = await props.request('advisor-availability/');
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
function edit() {
  draft.value = JSON.parse(JSON.stringify(value.value));
  base.value = JSON.stringify(draft.value);
  error.value = '';
  message.value = '';
}
function close() {
  if (!busy.value && (!dirty.value || confirm('Abandonner les horaires non enregistrés ?')))
    draft.value = null;
}
async function reloadDraft() {
  if (
    busy.value ||
    (dirty.value && !confirm('Abandonner les saisies et recharger les horaires actuels ?'))
  )
    return;
  draft.value = null;
  await load();
}
function add(day: number) {
  draft.value.windows.push({ weekday: day, start: '09:00', end: '17:00' });
}
function remove(row: any) {
  draft.value.windows.splice(draft.value.windows.indexOf(row), 1);
}
async function save() {
  busy.value = true;
  error.value = '';
  try {
    value.value = await props.request('advisor-availability/', draft.value);
    draft.value = null;
    message.value = 'Vos disponibilités sont enregistrées.';
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
onMounted(load);
</script>
<template>
  <section class="advisor-agenda">
    <header>
      <span class="agenda-icon"><CalendarDays :size="26" /></span>
      <div>
        <h1>Mon agenda et mes disponibilités</h1>
        <p>Choisissez vos horaires de rendez-vous et connectez votre agenda personnel.</p>
      </div>
    </header>
    <nav aria-label="Paramètres de mon agenda">
      <button :class="{ active: tab === 'hours' }" @click="tab = 'hours'">
        <Clock3 :size="17" />Mes disponibilités</button
      ><button :class="{ active: tab === 'connection' }" @click="tab = 'connection'">
        <Link2 :size="17" />Mes agendas connectés
      </button>
    </nav>
    <p v-if="error && !draft" role="alert">
      {{ error }} <button :disabled="busy" @click="load">Réessayer</button>
    </p>
    <p v-if="message" role="status" class="agenda-message">{{ message }}</p>
    <div v-show="tab === 'hours'" v-if="value" class="agenda-hours">
      <div class="hours-heading">
        <div>
          <h2>Mes horaires de rendez-vous</h2>
          <p>
            {{ value.timezone }} ·
            {{
              value.enabled
                ? 'Horaires appliqués aux nouvelles réservations'
                : 'Horaires personnalisés non activés'
            }}
          </p>
        </div>
        <button class="primary" :disabled="busy" @click="edit">
          {{ value.enabled ? 'Modifier mes horaires' : 'Définir mes horaires' }}
        </button>
      </div>
      <p class="agenda-note">
        Les rendez-vous doivent entrer dans une de vos plages. Les rendez-vous déjà pris restent
        conservés. Un agenda Google ou Microsoft connecté est également vérifié au moment de la
        réservation.
      </p>
      <p v-if="!value.enabled" class="agenda-warning">
        Activez vos horaires pour limiter les créneaux proposés aux setters. Pour le moment, seuls
        les conflits avec les rendez-vous existants et l’agenda externe sont contrôlés.
      </p>
      <div v-else class="week-summary">
        <article v-for="(day, index) in days" :key="day">
          <strong>{{ day }}</strong
          ><template v-if="value.windows.some((row: any) => row.weekday === index)"
            ><span
              v-for="(row, n) in value.windows.filter((row: any) => row.weekday === index)"
              :key="n"
              >{{ row.start }} – {{ row.end }}</span
            ></template
          ><span v-else class="closed">Indisponible</span>
        </article>
      </div>
    </div>
    <div v-show="tab === 'connection'" class="agenda-connection">
      <PortalCalendars :request="portal" workspace="assurance" simple />
    </div>
    <SidePanel
      :open="!!draft"
      title="Mes horaires de rendez-vous"
      eyebrow="MES DISPONIBILITÉS"
      :close-disabled="busy"
      @request-close="close"
    >
      <form v-if="draft" class="hours-form" @submit.prevent="save">
        <fieldset :disabled="busy">
          <p v-if="error" role="alert">
            {{ error }}
            <button type="button" :disabled="busy" @click="reloadDraft">
              Recharger les horaires
            </button>
          </p>
          <label class="hours-toggle"
            ><input v-model="draft.enabled" type="checkbox" />Appliquer mes horaires aux
            réservations</label
          >
          <label class="hours-zone"
            >Fuseau horaire<select v-model="draft.timezone">
              <option v-for="zone in zones" :key="zone" :value="zone">
                {{
                  zone === 'America/Toronto'
                    ? 'Toronto / Montréal'
                    : zone.replace('America/', '').replace('_', ' ')
                }}
              </option>
            </select></label
          >
          <p class="agenda-note">
            Ajoutez une ou plusieurs plages par jour. Sans plage, le jour est fermé. Les plages
            doivent commencer et finir le même jour et ne pas se chevaucher.
          </p>
          <p v-if="draft.enabled && !draft.windows.length" class="agenda-warning">
            Aucune plage définie : aucune nouvelle réservation ne sera acceptée.
          </p>
          <div v-for="(day, index) in days" :key="day" class="hours-day">
            <div class="day-heading">
              <strong>{{ day }}</strong
              ><button
                type="button"
                :aria-label="`Ajouter une plage pour ${day}`"
                @click="add(index)"
              >
                <Plus :size="15" />Ajouter une plage
              </button>
            </div>
            <p v-if="!draft.windows.some((row: any) => row.weekday === index)" class="closed">
              Indisponible
            </p>
            <div
              v-for="(row, n) in draft.windows.filter((row: any) => row.weekday === index)"
              :key="n"
              class="hours-range"
            >
              <label
                >De<input
                  v-model="row.start"
                  type="time"
                  required
                  :aria-label="`${day} début ${n + 1}`" /></label
              ><label
                >À<input
                  v-model="row.end"
                  type="time"
                  required
                  :aria-label="`${day} fin ${n + 1}`" /></label
              ><button
                type="button"
                :aria-label="`Retirer la plage ${n + 1} du ${day}`"
                @click="remove(row)"
              >
                <X :size="16" />
              </button>
            </div>
          </div>
          <button class="primary hours-save" type="submit" :disabled="!dirty">
            <Save :size="17" />Enregistrer mes disponibilités
          </button>
        </fieldset>
      </form>
    </SidePanel>
  </section>
</template>
<style scoped>
.advisor-agenda {
  color: #293a53;
}
.advisor-agenda header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}
.advisor-agenda h1 {
  margin: 0 0 8px;
}
.advisor-agenda p {
  color: #6f8097;
  line-height: 1.7;
}
.advisor-agenda .agenda-icon {
  display: grid;
  place-items: center;
  height: 58px;
  width: 58px;
  border-radius: 16px;
  background: #eee8ff;
  color: #7458c7;
}
.advisor-agenda nav {
  display: flex;
  gap: 10px;
  margin-bottom: 24px;
  border-bottom: 1px solid #e0e7f0;
  padding-bottom: 12px;
  flex-wrap: wrap;
}
.advisor-agenda button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 11px 15px;
  border: 1px solid #dce4ef;
  background: #fff;
  color: #45618c;
  border-radius: 9px;
  cursor: pointer;
}
.advisor-agenda button.active {
  color: #5d43b2;
  background: #f1ecff;
  border-color: #d9cef7;
}
.advisor-agenda button.primary {
  background: #336ce8;
  color: white;
  border-color: transparent;
}
.advisor-agenda button:disabled {
  opacity: 0.45;
  cursor: default;
}
.advisor-agenda .agenda-hours {
  background: #fff;
  padding: 24px;
  border: 1px solid #e0e7f1;
  border-radius: 16px;
}
.advisor-agenda .agenda-connection {
  padding: 0;
  border: 0;
  background: transparent;
}
.advisor-agenda .hours-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.advisor-agenda h2 {
  font-size: 19px;
  margin: 0;
}
.advisor-agenda .agenda-note {
  font-size: 12px;
  line-height: 1.7;
}
.advisor-agenda .agenda-warning {
  background: #fff5e4;
  padding: 14px;
  border-radius: 10px;
  color: #8b6632;
}
.advisor-agenda .agenda-message {
  background: #e6f6ee;
  padding: 14px;
  border-radius: 10px;
  color: #297652;
}
.advisor-agenda .week-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 12px;
  margin-top: 20px;
}
.advisor-agenda .week-summary article {
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: #f5f7fd;
  border: 1px solid #e9edf6;
  padding: 18px;
  border-radius: 12px;
}
.advisor-agenda .closed {
  color: #99a3b4;
  font-size: 12px;
}
.advisor-agenda .hours-form fieldset {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  padding: 0;
  border: 0;
  gap: 16px;
  min-width: 0;
}
.advisor-agenda .hours-toggle {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: initial;
}
.advisor-agenda .hours-toggle input {
  accent-color: #6753cf;
  width: 18px;
  height: 18px;
}
.advisor-agenda .hours-zone {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: initial;
}
.advisor-agenda .hours-zone select,
.advisor-agenda .hours-range input {
  padding: 11px;
  border: 1px solid #dbe3f0;
  border-radius: 8px;
  background: white;
  color: #293a53;
}
.advisor-agenda .hours-day {
  padding: 16px;
  border: 1px solid #e0e7f1;
  border-radius: 12px;
}
.advisor-agenda .day-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.advisor-agenda .hours-range {
  display: flex;
  align-items: end;
  gap: 10px;
  margin-top: 12px;
}
.advisor-agenda .hours-range label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
  min-width: 0;
}
.advisor-agenda .hours-save {
  justify-content: center;
  width: 100%;
}
@media (max-width: 600px) {
  .advisor-agenda .hours-heading {
    align-items: stretch;
    flex-direction: column;
  }
  .advisor-agenda header {
    align-items: flex-start;
  }
  .advisor-agenda .agenda-icon {
    flex-shrink: 0;
  }
}
</style>
