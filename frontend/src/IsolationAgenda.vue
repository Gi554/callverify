<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import SidePanel from './SidePanel.vue';
import PortalCalendars from './PortalCalendars.vue';
import IsolationReminderPolicy from './IsolationReminderPolicy.vue';
const props = defineProps<{
  role: string;
  request: (path: string, body?: any) => Promise<any>;
  portal: (path: string, body?: any) => Promise<any>;
}>();
const value = ref<any>(null),
  draft = ref<any>(null),
  busy = ref(false),
  error = ref(''),
  message = ref(''),
  tab = ref('hours');
const base = ref('');
const days = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche'];
const dirty = computed(() => draft.value && JSON.stringify(draft.value) !== base.value);
async function load() {
  busy.value = true;
  error.value = '';
  try {
    value.value = await props.request('isolation-working-hours/');
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
function edit() {
  draft.value = JSON.parse(JSON.stringify(value.value));
  base.value = JSON.stringify(draft.value);
}
function close() {
  if (!busy.value && (!dirty.value || window.confirm('Abandonner les horaires non enregistrés ?')))
    draft.value = null;
}
async function save() {
  busy.value = true;
  error.value = '';
  try {
    value.value = await props.request('isolation-working-hours/', {
      revision: draft.value.revision,
      enabled: draft.value.enabled,
      windows: draft.value.windows,
    });
    draft.value = null;
    message.value = 'Horaires enregistrés. Les prochaines réservations seront contrôlées.';
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
onMounted(load);
</script>
<template>
  <section class="isolation-agenda">
    <h2>Mon agenda et mes disponibilités</h2>
    <p>Horaires de visite du client Isolation · heure du Québec</p>
    <nav aria-label="Réglages de l’agenda">
      <button class="secondary" :aria-pressed="tab === 'hours'" @click="tab = 'hours'">
        Mes disponibilités</button
      ><button
        v-if="role === 'client'"
        class="secondary"
        :aria-pressed="tab === 'connection'"
        @click="tab = 'connection'"
      >
        Connexion de mon agenda
      </button>
    </nav>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <template v-if="tab === 'hours' && value">
      <p>
        {{
          value.enabled
            ? 'Seules les plages ci-dessous sont ouvertes à la programmation.'
            : 'Les restrictions horaires ne sont pas encore activées. Activez-les pour limiter les réservations à vos disponibilités.'
        }}
      </p>
      <div class="days">
        <article v-for="(day, index) in days" :key="day">
          <strong>{{ day }}</strong
          ><template v-for="(row, i) in value.windows" :key="i"
            ><span v-if="row.weekday === index">{{ row.start }} – {{ row.end }}</span></template
          ><small v-if="!value.windows.some((r: any) => r.weekday === index)">{{
            value.enabled ? 'Fermé' : 'Aucune plage configurée'
          }}</small>
        </article>
      </div>
      <button class="primary" :disabled="busy" @click="edit">Modifier mes horaires</button
      ><button class="secondary" :disabled="busy" @click="load">Actualiser</button>
      <p>
        L’agenda connecté reste consulté pour les événements déjà occupés. Les titres privés de cet
        agenda ne sont pas affichés aux setters.
      </p>
    </template>
    <PortalCalendars
      v-if="tab === 'connection' && role === 'client'"
      workspace="isolation"
      :request="portal"
      simple
    />
    <IsolationReminderPolicy v-if="role === 'administrator'" :request="request" />
    <SidePanel
      :open="!!draft"
      title="Horaires de visite"
      eyebrow="ISOLATION · QUÉBEC"
      :close-disabled="busy"
      @request-close="close"
    >
      <form v-if="draft" class="hours" @submit.prevent="save">
        <p v-if="error" role="alert">{{ error }}</p>
        <label
          ><input v-model="draft.enabled" type="checkbox" :disabled="busy" />Limiter la
          programmation aux plages définies</label
        >
        <p>
          America/Toronto · Les jours sans plage sont fermés lorsque la restriction est activée.
        </p>
        <article v-for="(day, index) in days" :key="day">
          <h3>{{ day }}</h3>
          <template v-for="(row, i) in draft.windows" :key="i"
            ><div v-if="row.weekday === index" class="window">
              <label>Début<input v-model="row.start" type="time" required :disabled="busy" /></label
              ><label>Fin<input v-model="row.end" type="time" required :disabled="busy" /></label
              ><button
                class="secondary"
                type="button"
                :disabled="busy"
                @click="draft.windows.splice(i, 1)"
              >
                Retirer
              </button>
            </div></template
          ><button
            class="secondary"
            type="button"
            :disabled="busy || draft.windows.length >= 28"
            @click="draft.windows.push({ weekday: index, start: '09:00', end: '17:00' })"
          >
            Ajouter une plage
          </button>
        </article>
        <button class="primary" :disabled="busy">Enregistrer les horaires</button>
      </form>
    </SidePanel>
  </section>
</template>
<style scoped>
.isolation-agenda,
.hours {
  display: grid;
  gap: 20px;
}
h2,
h3,
p {
  margin: 0;
}
p {
  font-size: 13px;
  color: #65718c;
  line-height: 1.6;
}
nav,
.window {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: end;
}
.days {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(125px, 1fr));
  gap: 12px;
}
article {
  display: grid;
  gap: 12px;
  padding: 16px;
  border: 1px solid #e7e2f4;
  border-radius: 14px;
  background: #faf9ff;
}
article small {
  color: #7b8497;
}
.window label {
  display: grid;
  gap: 6px;
}
[role='alert'] {
  color: #b42318;
}
</style>
