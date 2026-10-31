<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import IsolationCloserAssignment from './IsolationCloserAssignment.vue';
import IsolationC2 from './IsolationC2.vue';
import IsolationC2Snapshot from './IsolationC2Snapshot.vue';
import { bookingInterval } from './booking-time';
import AvailabilitySlots from './AvailabilitySlots.vue';
import IsolationVisitResult from './IsolationVisitResult.vue';
import IsolationSharedActivities from './IsolationSharedActivities.vue';
import IsolationVisitSupplements from './IsolationVisitSupplements.vue';
const props = defineProps<{
  visitId?: number;
  prospectId?: number;
  role: string;
  portal: (path: string, body?: any) => Promise<any>;
  request: (path: string, body?: any, method?: string) => Promise<any>;
}>();
function visitDate(value: string, zone: string) {
  return new Intl.DateTimeFormat('fr-FR', {
    timeZone: zone,
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}
const emit = defineEmits<{ close: []; changed: []; busy: [value: boolean]; updated: [row: any] }>();
const c2 = ref<any>(null),
  c2Busy = ref(false),
  c2Dirty = ref(false),
  localStart = ref(''),
  duration = ref(60);
function close() {
  if (busy.value || c2Busy.value) return;
  if (
    !c2Dirty.value ||
    window.confirm('Quitter sans enregistrer les modifications de qualification ?')
  )
    emit('close');
}
const assigning = ref<any>(null);
const supplements = ref<any>(null),
  sharedActivities = ref<any>(null);
const reporting = ref<any>(null),
  dueOnly = ref(false);
const outcomes: Record<string, string> = {
  closed: 'Vente conclue',
  completed: 'Effectuée',
  follow_up: 'Suivi nécessaire',
  interested: 'Intéressé',
  not_interested: 'Non intéressé',
  not_performed: 'Non effectuée',
};
const prospect = ref<any>(null),
  rows = ref<any[]>([]),
  page = ref(1),
  count = ref(0),
  busy = ref(false),
  error = ref(''),
  start = ref(''),
  end = ref(''),
  zone = ref('America/Toronto'),
  reason = ref(''),
  editing = ref<any>(null),
  cancelling = ref<any>(null),
  history = ref<any>(null),
  historyRows = ref<any[]>([]),
  historyPage = ref(1),
  historyCount = ref(0);
watch([busy, c2Busy], () => emit('busy', busy.value || c2Busy.value), { flush: 'sync' });
let requestId = crypto.randomUUID();
function changed() {
  requestId = crypto.randomUUID();
}
async function run(action: () => Promise<void>) {
  if (busy.value) return;
  busy.value = true;
  error.value = '';
  try {
    await action();
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function load() {
  if (props.visitId) {
    rows.value = [await props.request(`visits/${props.visitId}/`)];
    count.value = 1;
    emit('updated', rows.value[0]);
    return;
  }
  if (props.prospectId)
    prospect.value = await props.request(
      `${props.role === 'client' ? 'client-prospects' : 'work-queue'}/${props.prospectId}/`,
    );
  const data = await props.request(
    `visits/?page=${page.value}&result_due=${dueOnly.value}${props.prospectId ? '&prospect_id=' + props.prospectId : ''}`,
  );
  rows.value = data.results;
  count.value = data.count;
}
function loadBusy(start: string, end: string) {
  const query = new URLSearchParams({ prospect_id: String(prospect.value.id), start, end });
  return props.request(`visits/availability/?${query}`).then((data: any) => data.busy);
}
async function attest(row: any) {
  if (!row.assigned_setter)
    throw new Error('Affectez le prospect à un setter actif avant de réserver.');
  return (
    await props.portal('isolation/visit-proof/', {
      prospect_id: row.id,
      setter_id: row.assigned_setter.id,
    })
  ).proof;
}
async function save() {
  await run(async () => {
    const record = editing.value;
    if (!record) {
      if (!c2.value) throw new Error('Chargez la qualification avant de réserver.');
      await c2.value.ensureSaved();
    }
    const current = record
      ? await props.request(`work-queue/${record.prospect.id}/`)
      : prospect.value;
    const proof = await attest(current);
    const interval = record
      ? { starts_at: start.value, ends_at: end.value, timezone: zone.value }
      : bookingInterval(localStart.value, zone.value, Number(duration.value));
    const body: any = { ...interval, proof, revision: record ? record.revision : current.revision };
    if (record) {
      body.reason = reason.value;
      await props.request(`visits/${record.id}/reschedule/`, body);
    } else {
      body.prospect_id = current.id;
      body.request_id = requestId;
      await props.request('visits/', body);
    }
    editing.value = null;
    changed();
    start.value = '';
    end.value = '';
    reason.value = '';
    await load();
    emit('changed');
  });
}
async function cancel() {
  await run(async () => {
    await props.request(`visits/${cancelling.value.id}/cancel/`, {
      revision: cancelling.value.revision,
      reason: reason.value,
    });
    cancelling.value = null;
    reason.value = '';
    await load();
    emit('changed');
  });
}
async function loadHistory() {
  const data = await props.request(`visits/${history.value.id}/history/?page=${historyPage.value}`);
  historyRows.value = data.results;
  historyCount.value = data.count;
}
defineExpose({ close });
onMounted(() => run(load));
</script>
<template>
  <section>
    <h3 v-if="!visitId && prospect">Visites · {{ prospect.name || prospect.raw_phone }}</h3>
    <p v-if="!visitId && role !== 'client'">
      Les visites concernent le client Isolation unique. Les conflits internes et les occupations de
      son agenda Google ou Microsoft connecté sont contrôlés avant confirmation.
    </p>
    <p v-if="error" role="alert">{{ error }}</p>
    <button class="secondary" :disabled="busy" @click="run(load)">
      Recharger les visites et la fiche</button
    ><label v-if="!visitId && role === 'client'"
      ><input
        v-model="dueOnly"
        type="checkbox"
        @change="
          run(async () => {
            page = 1;
            await load();
          })
        "
      />Résultats à renseigner uniquement</label
    ><IsolationC2
      v-if="role !== 'client' && prospect"
      v-show="!editing"
      ref="c2"
      :key="prospect.id"
      :prospect-id="prospect.id"
      :request="request"
      :blocked="busy"
      @saved="(revision) => (prospect.revision = revision)"
      @busy="c2Busy = $event"
      @dirty="c2Dirty = $event"
    />
    <form
      v-if="role !== 'client' && (prospect || editing)"
      @submit.prevent="save"
      @input="changed"
      @change="changed"
    >
      <fieldset :disabled="busy || c2Busy">
        <legend>{{ editing ? 'Reporter une visite' : 'Programmer une visite' }}</legend>
        <template v-if="!editing"
          ><AvailabilitySlots
            v-if="prospect"
            v-model="localStart"
            :zone="zone"
            :duration="Number(duration)"
            :disabled="busy || c2Busy"
            :load="loadBusy"
            :load-key="String(prospect.id)"
            label="Disponibilités du client Isolation"
            note="L’agenda Google ou Microsoft du client est vérifié à la confirmation."
          /><label
            >Date et heure du rendez-vous<input
              v-model="localStart"
              type="datetime-local"
              required /></label
          ><label
            >Durée<select v-model="duration">
              <option :value="30">30 minutes</option>
              <option :value="60">1 heure</option>
              <option :value="90">1 h 30</option>
              <option :value="120">2 heures</option>
            </select></label
          ></template
        ><template v-else
          ><label
            >Début ISO 8601 avec décalage<input
              v-model="start"
              placeholder="2026-12-01T10:00:00-05:00"
              required /></label
          ><label
            >Fin ISO 8601 avec décalage<input
              v-model="end"
              placeholder="2026-12-01T11:00:00-05:00"
              required /></label></template
        ><label
          >Heure du rendez-vous<select v-model="zone" required>
            <option value="America/Toronto">Toronto / Montréal</option>
            <option value="America/Vancouver">Vancouver</option>
            <option value="America/Halifax">Halifax</option>
            <option value="UTC">UTC</option>
          </select></label
        ><label v-if="editing"
          >Motif du report<textarea v-model="reason" required maxlength="1000"></textarea></label
        ><button class="primary">
          {{ editing ? 'Confirmer le report' : 'Programmer la visite' }}</button
        ><button
          v-if="editing"
          type="button"
          class="secondary"
          @click="
            editing = null;
            start = '';
            end = '';
            reason = '';
          "
        >
          Annuler le report
        </button>
      </fieldset>
    </form>
    <article v-for="row in rows" :key="row.id">
      <h4>
        {{ row.prospect.name || row.prospect.phone }} ·
        {{
          row.status === 'cancelled'
            ? 'Annulée'
            : row.result
              ? row.result.performed
                ? 'Effectuée'
                : 'Non effectuée'
              : 'Planifiée'
        }}
      </h4>
      <p>
        {{ visitDate(row.starts_at, row.timezone) }} → {{ visitDate(row.ends_at, row.timezone) }} ·
        {{ row.timezone }}
      </p>
      <IsolationC2Snapshot :snapshot="row.c2_snapshot" />
      <p>Closer : {{ row.closer?.name || 'Non attribué' }}</p>
      <button
        v-if="['client', 'administrator'].includes(role) && row.status === 'scheduled'"
        class="secondary"
        :disabled="busy"
        @click="assigning = row"
      >
        Attribuer / réattribuer un closer
      </button>
      <p v-if="row.result">
        Vente :
        {{
          row.result.closed === null
            ? 'Non renseignée'
            : row.result.closed
              ? 'Conclue'
              : 'Non conclue'
        }}
      </p>
      <p>
        Client : {{ row.client.name }} · Setter à la réservation : {{ row.original_setter.name }}
      </p>
      <template
        v-if="
          role !== 'client' &&
          row.status === 'scheduled' &&
          new Date(row.starts_at).getTime() > Date.now()
        "
        ><button
          class="secondary"
          :disabled="busy"
          @click="
            editing = row;
            cancelling = null;
            start = row.starts_at;
            end = row.ends_at;
            zone = 'UTC';
            reason = '';
          "
        >
          Reporter</button
        ><button
          class="secondary"
          :disabled="busy"
          @click="
            cancelling = row;
            editing = null;
            reason = '';
          "
        >
          Annuler la visite
        </button></template
      >
      <p v-if="row.result">
        Résultat : {{ row.result.performed ? 'Oui, effectuée' : 'Non, non effectuée' }} ·
        {{ outcomes[row.result.outcome] }} ·
        {{ new Date(row.result.created_at).toLocaleString('fr-FR') }}
      </p>
      <p v-if="row.result" style="white-space: pre-wrap">{{ row.result.note }}</p>
      <button v-if="row.result" class="secondary" :disabled="busy" @click="supplements = row">
        Consulter / compléter le résultat
      </button>
      <p v-else-if="row.result_due">Résultat en attente</p>
      <button
        v-if="role === 'client' && row.result_due"
        class="primary"
        :disabled="busy"
        @click="reporting = row"
      >
        Renseigner le résultat</button
      ><button class="secondary" :disabled="busy" @click="sharedActivities = row">
        Observations partagées</button
      ><button
        v-if="role === 'administrator'"
        class="secondary"
        :disabled="busy"
        @click="
          run(async () => {
            history = row;
            historyPage = 1;
            await loadHistory();
          })
        "
      >
        Historique
      </button>
    </article>
    <p v-if="!rows.length">Aucune visite dans votre périmètre.</p>
    <p v-if="!visitId">{{ count }} visite(s) · page {{ page }}</p>
    <button
      class="secondary"
      v-if="!visitId"
      :disabled="busy || page === 1"
      @click="
        run(async () => {
          page--;
          await load();
        })
      "
    >
      Précédent</button
    ><button
      class="secondary"
      v-if="!visitId"
      :disabled="busy || page * 25 >= count"
      @click="
        run(async () => {
          page++;
          await load();
        })
      "
    >
      Suivant</button
    ><IsolationCloserAssignment
      v-if="assigning"
      :key="assigning.id"
      :visit="assigning"
      :request="request"
      :portal="portal"
      @busy="busy = $event"
      @saved="
        assigning = null;
        run(load);
      "
    />
    <section v-if="sharedActivities">
      <IsolationSharedActivities
        :key="sharedActivities.id"
        :visit-id="sharedActivities.id"
        :prospect-id="sharedActivities.prospect.id"
        :role="role"
        :request="request"
      /><button class="secondary" @click="sharedActivities = null">Fermer les observations</button>
    </section>
    <section v-if="supplements">
      <IsolationVisitSupplements
        :key="supplements.id"
        :visit-id="supplements.id"
        :role="role"
        :request="request"
      /><button class="secondary" @click="supplements = null">Fermer les compléments</button>
    </section>
    <IsolationVisitResult
      v-if="reporting && role === 'client'"
      :key="reporting.id"
      :visit="reporting"
      :request="request"
      @cancel="reporting = null"
      @saved="
        run(async () => {
          reporting = null;
          page = 1;
          await load();
          emit('changed');
        })
      "
    />
    <form v-if="cancelling" @submit.prevent="cancel">
      <label
        >Motif d’annulation<textarea v-model="reason" required maxlength="1000"></textarea></label
      ><button class="primary" :disabled="busy">Confirmer l’annulation</button
      ><button type="button" class="secondary" :disabled="busy" @click="cancelling = null">
        Conserver la visite
      </button>
    </form>
    <section v-if="history">
      <h4>Historique de la visite {{ history.id }}</h4>
      <article v-for="entry in historyRows" :key="entry.id">
        <small>{{ entry.action }} · {{ new Date(entry.created_at).toLocaleString('fr-FR') }}</small>
        <pre>{{ JSON.stringify(entry.metadata, null, 2) }}</pre>
      </article>
      <button
        class="secondary"
        :disabled="busy || historyPage === 1"
        @click="
          run(async () => {
            historyPage--;
            await loadHistory();
          })
        "
      >
        Précédent</button
      ><button
        class="secondary"
        :disabled="busy || historyPage * 25 >= historyCount"
        @click="
          run(async () => {
            historyPage++;
            await loadHistory();
          })
        "
      >
        Suivant</button
      ><button class="secondary" @click="history = null">Fermer l’historique</button>
    </section>
    <button class="secondary" :disabled="busy" @click="close">Fermer les visites</button>
  </section>
</template>
