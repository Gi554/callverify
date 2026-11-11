<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue';
import { CalendarDays, Clock3 } from 'lucide-vue-next';
import IsolationPageHeader from './IsolationPageHeader.vue';
import IsolationVisitCard from './IsolationVisitCard.vue';
import { visitName, initials, visitStatus, visitTone } from './isolation-visit-display';
import IsolationC2 from './IsolationC2.vue';
import IsolationC2Snapshot from './IsolationC2Snapshot.vue';
import { bookingInterval } from './booking-time';
import type { FollowUpReference } from './follow-up';
import AvailabilitySlots from './AvailabilitySlots.vue';
import IsolationVisitResult from './IsolationVisitResult.vue';
import IsolationSharedActivities from './IsolationSharedActivities.vue';
import IsolationVisitSupplements from './IsolationVisitSupplements.vue';
import IsolationVisitHistory from './IsolationVisitHistory.vue';
import SidePanel from './SidePanel.vue';
const nonqualified = ref(false),
  nonqualifiedReason = ref(''),
  nonqualifiedNote = ref('');
const props = defineProps<{
  visitId?: number;
  period?: 'upcoming' | 'history' | 'missing_updates';
  prospectId?: number;
  reactivationId?: number;
  clientFollowupId?: number;
  followUp?: FollowUpReference;
  role: string;
  portal: (path: string, body?: any) => Promise<any>;
  request: (path: string, body?: any, method?: string) => Promise<any>;
}>();
const listView = computed(() => !props.visitId && !props.prospectId);
const prospectEmail = ref('');
const prospectEmailInitial = ref('');
const selectedVisit = ref<any>(null),
  detailBusy = ref(false),
  detailRef = ref<any>(null);
const pageHeading = computed(() =>
  props.period === 'history'
    ? 'Rendez-vous passés'
    : props.period === 'missing_updates'
      ? 'Rendez-vous sans mise à jour'
      : props.period === 'upcoming'
        ? 'Rendez-vous à venir'
        : 'Mes rendez-vous',
);
const pageSubtitle = computed(() =>
  props.period === 'history'
    ? 'Retrouvez chaque rencontre et partagez la suite avec votre équipe.'
    : props.period === 'missing_updates'
      ? 'Un petit retour, pour que chaque dossier continue d’avancer.'
      : 'Préparez vos rencontres et désignez le bon représentant.',
);
function visitDate(value: string) {
  return new Intl.DateTimeFormat('fr-FR', {
    timeZone: 'America/Toronto',
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}
const emit = defineEmits<{
  close: [];
  changed: [];
  busy: [value: boolean];
  updated: [row: any];
  taskCompleted: [publicationWarning: string];
}>();
const c2 = ref<any>(null),
  c2Busy = ref(false),
  c2Dirty = ref(false),
  resultBusy = ref(false),
  resultDirty = ref(false),
  localStart = ref(''),
  duration = ref(60),
  // Keep the existing Google flow as the default while exposing the explicit
  // ORVIA-only option for setters/admins when no client link is available.
  publication = ref<'internal' | 'google'>('google');
function cancelReport() {
  if (resultBusy.value) return;
  if (resultDirty.value && !window.confirm('Abandonner ce résultat sans enregistrer ?')) return;
  reporting.value = null;
  resultDirty.value = false;
}
function close() {
  if (busy.value || c2Busy.value || resultBusy.value) return;
  if (
    (!c2Dirty.value &&
      !nonqualifiedReason.value &&
      !nonqualifiedNote.value &&
      !resultDirty.value &&
      prospectEmail.value === prospectEmailInitial.value) ||
    window.confirm('Quitter sans enregistrer les modifications ?')
  )
    emit('close');
}
const supplements = ref<any>(null),
  sharedActivities = ref<any>(null);
const reporting = ref<any>(null),
  dueOnly = ref(false);
const outcomes: Record<string, string> = {
  unqualified: 'Non qualifié — non validé',
  closed: 'Vente conclue',
  completed: 'Effectuée',
  follow_up: 'Suivi nécessaire',
  interested: 'Intéressé',
  not_interested: 'Non intéressé',
  not_performed: 'Non effectuée',
};
const publicationMessage = ref('');
const resultHistory = ref<number | null>(null);
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
  previousVisit = ref<any>(null),
  cancelling = ref<any>(null),
  history = ref<any>(null),
  historyRows = ref<any[]>([]),
  historyPage = ref(1),
  historyCount = ref(0);
watch(
  [busy, c2Busy, resultBusy],
  () => emit('busy', busy.value || c2Busy.value || resultBusy.value),
  { flush: 'sync' },
);
let requestId = crypto.randomUUID();
const bookingForm = ref<HTMLFormElement | null>(null);
async function beginAgain(row: any) {
  previousVisit.value = row;
  editing.value = null;
  localStart.value = '';
  changed();
  await nextTick();
  bookingForm.value?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
}
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
      props.clientFollowupId
        ? `client-follow-ups/${props.clientFollowupId}/prospect/`
        : props.reactivationId
          ? `isolation-unqualified/${props.reactivationId}/prospect/`
          : `${props.role === 'client' ? 'client-prospects' : 'work-queue'}/${props.prospectId}/`,
    );
  if (props.clientFollowupId && prospect.value) {
    prospectEmail.value = prospect.value.email || '';
    prospectEmailInitial.value = prospectEmail.value;
  }
  const data = await props.request(
    `visits/?page=${page.value}&result_due=${dueOnly.value}${props.period ? '&period=' + props.period : ''}${props.prospectId ? '&prospect_id=' + props.prospectId : ''}`,
  );
  rows.value = data.results;
  count.value = data.count;
}
async function loadBusy(start: string, end: string) {
  const proof = await attest(prospect.value);
  const data = await props.request('visits/availability/', {
    prospect_id: String(prospect.value.id),
    start,
    end,
    proof,
    ...(props.reactivationId ? { unqualified_id: props.reactivationId } : {}),
    ...(props.clientFollowupId ? { client_followup_id: props.clientFollowupId } : {}),
    publication: publication.value,
  });
  return data.busy;
}
async function attest(row: any) {
  if (!row.assigned_setter)
    throw new Error('Affectez le prospect à un setter actif avant de réserver.');
  return (
    await props.portal('isolation/visit-proof/', {
      prospect_id: row.id,
      setter_id: row.assigned_setter.id,
      ...(props.reactivationId ? { unqualified_id: props.reactivationId } : {}),
      ...(props.clientFollowupId ? { client_followup_id: props.clientFollowupId } : {}),
    })
  ).proof;
}
function qualificationRequest(path: string, body?: any) {
  return props.request(
    props.reactivationId ? `isolation-unqualified/${props.reactivationId}/qualification/` : path,
    body,
  );
}
async function save() {
  await run(async () => {
    const record = editing.value;
    let bookingEmail = '';
    if (!record) {
      if (!c2.value && !props.clientFollowupId)
        throw new Error('Chargez la qualification avant de réserver.');
      bookingEmail = props.clientFollowupId
        ? prospectEmail.value.trim()
        : c2.value.getEmail().trim();
      if (!props.clientFollowupId) await c2.value.ensureSaved(true);
    }
    const current = record
      ? await props.request(`work-queue/${record.prospect.id}/`)
      : prospect.value;
    const proof = await attest(current);
    const interval = record
      ? { starts_at: start.value, ends_at: end.value, timezone: zone.value }
      : bookingInterval(localStart.value, 'America/Toronto', Number(duration.value));
    const body: any = { ...interval, proof, revision: record ? record.revision : current.revision };
    let saved: any;
    if (record) {
      body.reason = reason.value;
      saved = await props.request(`visits/${record.id}/reschedule/`, body);
    } else {
      body.prospect_email = bookingEmail;
      body.prospect_id = current.id;
      body.request_id = requestId;
      body.publication = publication.value;
      if (props.reactivationId) body.unqualified_id = props.reactivationId;
      if (props.clientFollowupId) body.client_followup_id = props.clientFollowupId;
      if (previousVisit.value) body.previous_visit_id = previousVisit.value.id;
      if (props.followUp) body.follow_up = props.followUp;
      saved = await props.request('visits/', body);
    }
    await publish(saved);
    if (props.followUp && !record) {
      emit(
        'taskCompleted',
        publicationMessage.value
          ? 'La visite est enregistrée dans Orvia. Vérifiez son état de publication Google dans les visites.'
          : '',
      );
      return;
    }
    editing.value = null;
    previousVisit.value = null;
    changed();
    start.value = '';
    end.value = '';
    reason.value = '';
    // Reactivation archives its source entry; it cannot be loaded for editing again.
    if (!props.reactivationId && !props.clientFollowupId) await load();
    emit('changed');
  });
}
async function saveUnqualified() {
  await run(async () => {
    await c2.value.ensureSaved();
    const proof = await attest(prospect.value);
    await props.request('isolation-unqualified/', {
      prospect_id: prospect.value.id,
      revision: prospect.value.revision,
      request_id: requestId,
      proof,
      reason: nonqualifiedReason.value,
      note: nonqualifiedNote.value,
    });
    nonqualified.value = false;
    nonqualifiedReason.value = '';
    nonqualifiedNote.value = '';
    changed();
    await load();
    emit('changed');
  });
}
function closeUnqualified() {
  if (
    !busy.value &&
    ((!nonqualifiedReason.value && !nonqualifiedNote.value) ||
      window.confirm('Abandonner cette saisie ?'))
  )
    nonqualified.value = false;
}
async function publish(row: any) {
  publicationMessage.value = '';
  if (!row?.publication_proof) return;
  try {
    if (row.previous_publication_proof) {
      const removed = await props.portal('internal/isolation/publish-visit/', {
        proof: row.previous_publication_proof,
      });
      if (removed.state !== 'removed') throw new Error('Ancien créneau Google encore à vérifier.');
    }
    await props.portal('internal/isolation/publish-visit/', { proof: row.publication_proof });
  } catch {
    publicationMessage.value =
      'La visite est conservée dans Orvia. La publication Google reste à vérifier ; consultez son état ci-dessous avant de recommencer.';
  }
}
async function cancel() {
  await run(async () => {
    const saved = await props.request(`visits/${cancelling.value.id}/cancel/`, {
      revision: cancelling.value.revision,
      reason: reason.value,
    });
    await publish(saved);
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
  <section :class="['iso-visits', listView ? 'iso-page' : 'iso-detail']">
    <IsolationPageHeader
      v-if="listView"
      :title="pageHeading"
      :subtitle="pageSubtitle"
      eyebrow="MES RENDEZ-VOUS · ISOLATION"
      :busy="busy"
      @refresh="run(load)"
    />
    <p class="iso-notice" v-if="period === 'missing_updates'" role="status">
      Rendez-vous terminés depuis au moins 24 heures dont le résultat reste à compléter. Aucune
      absence ni validation n’est déduite automatiquement.
    </p>
    <h3 v-if="!visitId && prospect">Visites · {{ prospect.name || prospect.raw_phone }}</h3>
    <p v-if="!visitId && role !== 'client'">
      Les visites concernent le client Isolation unique. Les conflits internes sont toujours
      contrôlés. La publication dans l’agenda Google du client est facultative.
    </p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="publicationMessage" role="status">{{ publicationMessage }}</p>
    <button v-if="!listView" class="secondary" :disabled="busy" @click="run(load)">
      Recharger les visites et la fiche</button
    ><label
      class="iso-filter-check"
      v-if="!visitId && role === 'client' && period !== 'missing_updates'"
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
      v-if="(role !== 'client' || reactivationId) && prospect"
      v-show="!editing"
      ref="c2"
      :key="prospect.id"
      :prospect-id="prospect.id"
      :request="qualificationRequest"
      :blocked="busy"
      @saved="(revision) => (prospect.revision = revision)"
      @busy="c2Busy = $event"
      @dirty="c2Dirty = $event"
    />
    <form
      class="iso-form"
      ref="bookingForm"
      v-if="(role !== 'client' || reactivationId || clientFollowupId) && (prospect || editing)"
      @submit.prevent="save"
      @input="changed"
      @change="changed"
    >
      <fieldset :disabled="busy || c2Busy">
        <legend>{{ editing ? 'Reporter une visite' : 'Programmer une visite' }}</legend>
        <p v-if="previousVisit">
          Nouvelle visite après la visite non tenue n° {{ previousVisit.id }}. L’ancienne visite et
          son résultat sont conservés.
        </p>
        <template v-if="!editing">
          <p>
            L’agenda et les créneaux sont ceux du client Isolation, qui assure le suivi de la
            visite.
          </p>
          <label v-if="role !== 'client'"
            >Publication de la visite<select v-model="publication">
              <option value="internal">ORVIA uniquement (aucune connexion requise)</option>
              <option value="google">Agenda Google du client</option>
            </select></label
          >
          <label v-if="clientFollowupId"
            >Courriel du prospect · facultatif<input
              v-model="prospectEmail"
              type="email"
              maxlength="254"
          /></label>
          <p>
            Le client Isolation recevra les informations de la visite par courriel. Aucun courriel
            automatique ne sera envoyé au prospect.
          </p>
          <AvailabilitySlots
            v-if="prospect"
            v-model="localStart"
            zone="America/Toronto"
            :duration="Number(duration)"
            :disabled="busy || c2Busy"
            :load="loadBusy"
            :load-key="String(prospect.id)"
            label="Disponibilités du client Isolation"
            note="Les horaires du client sont consultés si son agenda est connecté. Nouvelle vérification à la confirmation."
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
              required /></label
        ></template>
        <p v-if="!editing">Heure du Québec · Montréal / Toronto</p>
        <label v-else
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
    <button
      v-if="prospect && ['setter', 'administrator'].includes(role) && !editing && !followUp"
      class="secondary"
      :disabled="busy || c2Busy"
      @click="nonqualified = true"
    >
      Enregistrer un rendez-vous non qualifié
    </button>
    <SidePanel
      :open="nonqualified"
      title="Rendez-vous non qualifié"
      :close-disabled="busy || c2Busy"
      @request-close="closeUnqualified"
    >
      <form @submit.prevent="saveUnqualified" @input="changed" @change="changed">
        <p>
          Le prospect reste intéressé. Ses informations disponibles, ses appels et ses suivis seront
          consultables par le client Isolation.
        </p>
        <p v-if="error" role="alert">{{ error }}</p>
        <fieldset :disabled="busy || c2Busy">
          <label
            >Motif<select v-model="nonqualifiedReason" required>
              <option value="">Choisir un motif</option>
              <option value="out_of_area">Hors zone d’intervention</option>
              <option value="city_not_served">Ville non desservie actuellement</option>
              <option value="distance">Distance trop importante</option>
              <option value="other">Autre</option>
            </select></label
          >
          <label
            >Notes facultatives<textarea v-model="nonqualifiedNote" maxlength="3000"></textarea>
          </label>
          <button class="primary" :disabled="!nonqualifiedReason">Enregistrer la fiche</button>
        </fieldset>
      </form>
    </SidePanel>
    <section v-if="listView" class="iso-panel">
      <header class="iso-panel-heading">
        <div>
          <h2>
            {{
              period === 'missing_updates'
                ? 'Votre retour est attendu'
                : period === 'history'
                  ? 'L’historique de vos rencontres'
                  : 'Les prochaines rencontres'
            }}
            <span class="iso-counter">{{ count }}</span>
          </h2>
          <p>
            {{
              period === 'missing_updates'
                ? 'Ces rendez-vous sont terminés depuis plus de 24 heures.'
                : 'Coordonnées, qualification et résultat dans chaque fiche.'
            }}
          </p>
        </div>
        <span class="iso-toolbar-note"><Clock3 :size="14" />Heure du Québec</span>
      </header>
    </section>
    <div v-if="listView && rows.length" class="iso-visits-grid">
      <IsolationVisitCard
        v-for="row in rows"
        :key="row.id"
        :visit="row"
        :busy="busy"
        @open="selectedVisit = row"
      />
    </div>
    <template v-if="!listView">
      <article v-for="row in rows" :key="row.id" class="iso-visit-detail">
        <p
          v-if="row.calendar === 'google'"
          :role="row.publication_status === 'error' ? 'alert' : 'status'"
        >
          {{
            row.publication_status === 'confirmed'
              ? 'Visite confirmée dans Google Agenda.'
              : row.publication_status === 'removed'
                ? 'Visite retirée de Google Agenda.'
                : row.publication_status === 'error'
                  ? 'Publication Google à vérifier. Ouvrez Agenda et disponibilités pour consulter la synchronisation avant de reprogrammer.'
                  : 'Enregistrement Orvia conservé. Publication Google en cours ; la visite n’est pas encore confirmée dans Google.'
          }}
        </p>
        <header class="iso-detail-identity">
          <span class="iso-avatar">{{ initials(visitName(row)) }}</span>
          <div>
            <h3>{{ visitName(row) }}</h3>
            <span class="iso-status" :class="visitTone(row)"
              ><span></span>{{ visitStatus(row) }}</span
            >
          </div>
        </header>
        <p v-if="row.previous_visit_id">
          Nouvelle visite après la visite n° {{ row.previous_visit_id }}.
        </p>
        <p v-if="row.next_visit_id">
          Une nouvelle visite n° {{ row.next_visit_id }} a été programmée. Cette occurrence reste
          conservée.
        </p>
        <button
          v-if="
            prospect &&
            !visitId &&
            ['setter', 'administrator'].includes(role) &&
            row.result?.performed === false &&
            row.status === 'scheduled' &&
            !row.next_visit_id
          "
          class="secondary"
          :disabled="busy || c2Busy"
          @click="beginAgain(row)"
        >
          Programmer une nouvelle visite après cette absence
        </button>
        <dl class="iso-detail-grid">
          <div>
            <dt>Rendez-vous · Québec</dt>
            <dd>{{ visitDate(row.starts_at) }}<br />→ {{ visitDate(row.ends_at) }}</dd>
          </div>
          <div>
            <dt>Téléphone</dt>
            <dd>{{ row.c2_snapshot?.fields?.phone || row.prospect.phone || 'Non renseigné' }}</dd>
          </div>
          <div>
            <dt>Adresse du rendez-vous</dt>
            <dd>
              {{ row.c2_snapshot?.fields?.address || 'Non renseignée' }}<br />{{
                row.c2_snapshot?.fields?.city
              }}
              {{ row.c2_snapshot?.fields?.postal_code }}
            </dd>
          </div>
          <div v-if="row.closer">
            <dt>Ancien représentant · historique</dt>
            <dd>{{ row.closer.name }}</dd>
          </div>
          <div>
            <dt>Setter à la réservation</dt>
            <dd>{{ row.original_setter.name }}</dd>
          </div>
          <div>
            <dt>Client Isolation</dt>
            <dd>{{ row.client.name }}</dd>
          </div>
        </dl>
        <IsolationC2Snapshot :snapshot="row.c2_snapshot" />
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
          Résultat :
          {{
            row.result.outcome === 'unqualified'
              ? 'Non qualifié — non validé'
              : row.result.performed
                ? 'Présenté'
                : 'Non présenté'
          }}
          · {{ outcomes[row.result.outcome] }} · {{ visitDate(row.result.created_at) }} · Québec
        </p>
        <p v-if="row.result" style="white-space: pre-wrap">{{ row.result.note }}</p>
        <p v-if="row.result?.absence_reason" style="white-space: pre-wrap">
          {{
            row.result.outcome === 'unqualified'
              ? 'Motif de non-qualification'
              : 'Motif de non-présentation'
          }}
          : {{ row.result.absence_reason }}
        </p>
        <p v-if="row.result && !row.result.performed && row.result.outcome !== 'unqualified'">
          Suivi :
          {{
            row.result.follow_up_owner === 'client'
              ? 'Relance personnelle du client'
              : 'Rappel par le setter'
          }}
        </p>
        <div class="iso-visit-actions">
          <button
            class="secondary"
            :disabled="busy"
            @click="resultHistory = resultHistory === row.id ? null : row.id"
          >
            Historique du rendez-vous
          </button>
          <IsolationVisitHistory
            v-if="resultHistory === row.id"
            :key="`${row.id}-${row.revision}`"
            :visit-id="row.id"
            :request="request"
          />
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
            Historique administratif
          </button>
        </div>
      </article>
    </template>
    <div v-if="!rows.length && !error" class="iso-empty">
      <span class="iso-empty-icon"><CalendarDays :size="26" /></span
      ><strong>{{
        busy
          ? 'Chargement des rendez-vous…'
          : period === 'missing_updates'
            ? 'Tous vos rendez-vous sont à jour'
            : 'Aucun rendez-vous à afficher'
      }}</strong>
      <p>
        {{
          period === 'missing_updates'
            ? 'Les résultats manquants depuis plus de 24 heures apparaîtront ici.'
            : 'Les rendez-vous de cette rubrique apparaîtront ici.'
        }}
      </p>
    </div>
    <footer v-if="!visitId" class="iso-pagination">
      <span>{{ count }} visite(s) · page {{ page }}</span
      ><button
        class="secondary"
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
        :disabled="busy || page * 25 >= count"
        @click="
          run(async () => {
            page++;
            await load();
          })
        "
      >
        Suivant
      </button>
    </footer>
    <SidePanel
      :open="!!selectedVisit"
      :title="
        selectedVisit?.c2_snapshot?.fields?.full_name ||
        selectedVisit?.prospect?.name ||
        'Rendez-vous'
      "
      eyebrow="MON RENDEZ-VOUS · ISOLATION"
      :close-disabled="detailBusy"
      @request-close="detailRef?.close()"
    >
      <IsolationVisits
        v-if="selectedVisit"
        ref="detailRef"
        :key="selectedVisit.id"
        :visit-id="selectedVisit.id"
        :role="role"
        :portal="portal"
        :request="request"
        @busy="detailBusy = $event"
        @close="selectedVisit = null"
        @updated="selectedVisit = $event"
        @changed="
          run(load);
          emit('changed');
        "
      />
    </SidePanel>
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
    <SidePanel
      :open="!!reporting"
      title="Renseigner le résultat de la visite"
      :subtitle="reporting?.prospect?.name || ''"
      eyebrow="ISOLATION · COMPTE RENDU"
      :close-disabled="resultBusy"
      @request-close="cancelReport"
    >
      <IsolationVisitResult
        v-if="reporting && role === 'client'"
        :key="reporting.id"
        :visit="reporting"
        :request="request"
        @busy="resultBusy = $event"
        @dirty="resultDirty = $event"
        @cancel="cancelReport"
        @saved="
          run(async () => {
            reporting = null;
            resultDirty = false;
            page = 1;
            await load();
            emit('changed');
          })
        "
      />
    </SidePanel>
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
        <small>{{ entry.action }} · {{ visitDate(entry.created_at) }} · Québec</small>
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
    <button v-if="!listView" class="secondary" :disabled="busy" @click="close">
      Fermer les visites
    </button>
  </section>
</template>
