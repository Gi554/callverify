<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { Clock3, ArrowUpRight, Phone, CalendarDays } from 'lucide-vue-next';
import IsolationPageHeader from './IsolationPageHeader.vue';
import { initials } from './isolation-visit-display';
import SidePanel from './SidePanel.vue';
import IsolationVisits from './IsolationVisits.vue';
import { bookingInterval } from './booking-time';
const props = defineProps<{
  role: string;
  request: (path: string, body?: any) => Promise<any>;
  portal: (path: string, body?: any) => Promise<any>;
}>();
const rows = ref<any[]>([]),
  count = ref(0),
  page = ref(1),
  busy = ref(false),
  error = ref('');
const bookingNotice = ref('');
const selected = ref<any>(null),
  due = ref(''),
  note = ref(''),
  dirty = ref(false),
  visitBusy = ref(false);
const visits = ref<InstanceType<typeof IsolationVisits> | null>(null);
const historyRows = ref<any[]>([]),
  historyPage = ref(1),
  historyCount = ref(0),
  historyBusy = ref(false);
async function loadHistory() {
  if (!selected.value || historyBusy.value) return;
  const id = selected.value.id;
  historyBusy.value = true;
  try {
    const data = await props.request(`client-follow-ups/${id}/history/?page=${historyPage.value}`);
    if (selected.value?.id === id) {
      historyRows.value = data.results;
      historyCount.value = data.count;
    }
  } catch (e: any) {
    error.value = e.message;
  } finally {
    historyBusy.value = false;
  }
}
function date(value: string) {
  return new Intl.DateTimeFormat('fr-CA', {
    timeZone: 'America/Toronto',
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}
function local(value: string) {
  if (!value) return '';
  const p = Object.fromEntries(
    new Intl.DateTimeFormat('en-CA', {
      timeZone: 'America/Toronto',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
    })
      .formatToParts(new Date(value))
      .map((part) => [part.type, part.value]),
  );
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}
async function load() {
  if (busy.value) return;
  busy.value = true;
  error.value = '';
  try {
    const data = await props.request(`client-follow-ups/?page=${page.value}`);
    rows.value = data.results;
    count.value = data.count;
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
function open(row: any) {
  selected.value = row;
  due.value = local(row.due_at);
  note.value = row.note;
  dirty.value = false;
  historyRows.value = [];
  historyPage.value = 1;
  historyCount.value = 0;
  loadHistory();
}
function close() {
  if (busy.value || visitBusy.value) return;
  if (dirty.value && !window.confirm('Quitter sans enregistrer la date et la note de relance ?'))
    return;
  visits.value?.close();
}
async function save() {
  if (busy.value || visitBusy.value) return;
  busy.value = true;
  error.value = '';
  try {
    selected.value = await props.request(`client-follow-ups/${selected.value.id}/update_plan/`, {
      revision: selected.value.revision,
      note: note.value,
      due_at: due.value
        ? due.value === local(selected.value.due_at)
          ? selected.value.due_at
          : bookingInterval(due.value, 'America/Toronto', 30).starts_at
        : null,
    });
    dirty.value = false;
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
  if (!dirty.value) await load();
  if (!dirty.value) await loadHistory();
}
async function changed() {
  if (selected.value) {
    try {
      const current = await props.request(`client-follow-ups/${selected.value.id}/`);
      if (current.programmed_visit_id) {
        bookingNotice.value =
          'Nouvelle visite enregistrée dans Orvia. Consultez « Rendez-vous à venir » pour vérifier sa publication dans Google.';
      }
      if (current.closed_at) {
        selected.value = null;
        dirty.value = false;
      }
    } catch (e: any) {
      error.value = e.message;
    }
  }
  await load();
}
onMounted(load);
</script>
<template>
  <section class="iso-page">
    <IsolationPageHeader
      title="Mes relances personnelles"
      subtitle="Le bon moment pour reprendre contact, avec toutes les informations sous la main."
      eyebrow="À RECONTACTER PAR MOI-MÊME · ISOLATION"
      :busy="busy"
      @refresh="load"
    />
    <section class="iso-closer-banner">
      <div>
        <span class="iso-quick-icon"><Clock3 :size="23" /></span>
        <div>
          <h2>{{ count }} relance(s) dans votre carnet</h2>
          <p>
            Ces suivis restent dans l’espace du client. Les rappels du setter sont gérés séparément.
          </p>
        </div>
      </div>
      <span class="iso-toolbar-note"><CalendarDays :size="16" />Heure du Québec</span>
    </section>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="bookingNotice" class="iso-notice info" role="status">{{ bookingNotice }}</p>
    <div v-if="rows.length" class="iso-visits-grid">
      <article v-for="row in rows" :key="row.id" class="iso-visit-card iso-personal-card">
        <div class="iso-visit-top">
          <span class="iso-avatar">{{ initials(row.name) }}</span
          ><span
            class="iso-status"
            :class="!row.due_at ? 'muted' : Date.parse(row.due_at) <= Date.now() ? 'amber' : 'blue'"
            ><span></span
            >{{
              !row.due_at
                ? 'À planifier'
                : Date.parse(row.due_at) <= Date.now()
                  ? 'À recontacter'
                  : 'Rappel prévu'
            }}</span
          >
        </div>
        <h3>{{ row.name }}</h3>
        <p class="iso-card-phone"><Phone :size="13" />{{ row.phone }}</p>
        <div class="iso-personal-due">
          <Clock3 :size="15" />
          <div>
            <strong>{{ row.due_at ? date(row.due_at) : 'Choisir une date de rappel' }}</strong
            ><small>{{
              row.due_at ? 'Heure du Québec' : 'Une date peut être ajoutée dans la fiche.'
            }}</small>
          </div>
        </div>
        <p class="iso-personal-reason">{{ row.reason }}</p>
        <p class="iso-note-preview">
          {{ row.note || 'Ajoutez une note pour préparer le prochain échange.' }}
        </p>
        <p v-if="role === 'administrator'" class="iso-toolbar-note">
          Client · {{ row.client.name }}
        </p>
        <button class="iso-card-open" :disabled="busy" @click="open(row)">
          Ouvrir la fiche <ArrowUpRight :size="17" />
        </button>
      </article>
    </div>
    <div v-else class="iso-empty">
      <span class="iso-empty-icon"><Clock3 :size="27" /></span
      ><strong>{{
        busy ? 'Chargement des relances…' : 'Votre carnet de relances est à jour'
      }}</strong>
      <p>Les prospects que vous choisissez de recontacter personnellement apparaîtront ici.</p>
    </div>
    <footer class="iso-pagination">
      <span>{{ count }} relance(s) · page {{ page }}</span
      ><button
        class="secondary"
        :disabled="busy || page === 1"
        @click="
          page--;
          load();
        "
      >
        Précédent</button
      ><button
        class="secondary"
        :disabled="busy || page * 25 >= count"
        @click="
          page++;
          load();
        "
      >
        Suivant
      </button>
    </footer>
    <SidePanel
      :open="!!selected"
      :title="selected?.name || 'Relance personnelle'"
      :close-disabled="busy || visitBusy"
      @request-close="close"
    >
      <section v-if="selected" class="iso-detail">
        <p>{{ selected.phone }} · {{ selected.reason }}</p>
        <p v-if="error" role="alert">{{ error }}</p>
        <form
          class="iso-form"
          v-if="role === 'client'"
          @submit.prevent="save"
          @input="dirty = true"
        >
          <fieldset :disabled="busy || visitBusy">
            <label
              >Date et heure de rappel · Québec<input v-model="due" type="datetime-local"
            /></label>
            <label>Note de relance<textarea v-model="note" maxlength="3000"></textarea></label>
            <button class="primary">Enregistrer la relance</button>
          </fieldset>
        </form>
        <p v-else>{{ selected.note || 'Aucune note.' }}</p>
        <details>
          <summary>Historique des dates et notes de relance</summary>
          <article v-for="entry in historyRows" :key="entry.id">
            <small>{{ date(entry.created_at) }} · Québec</small>
            <p>Rappel : {{ entry.due_at ? date(entry.due_at) : 'Date non définie' }}</p>
            <p style="white-space: pre-wrap">{{ entry.note || 'Aucune note.' }}</p>
          </article>
          <p v-if="!historyRows.length">
            {{ historyBusy ? 'Chargement…' : 'Aucune modification de relance enregistrée.' }}
          </p>
          <button
            class="secondary"
            :disabled="historyBusy || historyPage === 1"
            @click="
              historyPage--;
              loadHistory();
            "
          >
            Précédent
          </button>
          <button
            class="secondary"
            :disabled="historyBusy || historyPage * 25 >= historyCount"
            @click="
              historyPage++;
              loadHistory();
            "
          >
            Suivant
          </button>
        </details>
        <IsolationVisits
          ref="visits"
          :key="selected.id"
          :role="role"
          :prospect-id="selected.prospect_id"
          :client-followup-id="role === 'client' ? selected.id : undefined"
          :portal="portal"
          :request="request"
          @busy="visitBusy = $event"
          @close="selected = null"
          @changed="changed"
        />
      </section>
    </SidePanel>
  </section>
</template>
