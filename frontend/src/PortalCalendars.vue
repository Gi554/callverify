<script setup lang="ts">
import { ref, onMounted } from 'vue';
import {
  ArrowRight,
  CalendarDays,
  Check,
  Clock3,
  Link2,
  RefreshCw,
  ShieldCheck,
  Unplug,
} from 'lucide-vue-next';
import googleLogo from './assets/calendar/google-calendar.png';
import outlookLogo from './assets/calendar/microsoft-outlook.png';
import { bookingInterval } from './booking-time';
import PortalCalendly from './PortalCalendly.vue';
const providers = [
  {
    id: 'google',
    name: 'Google Calendar',
    account: 'Votre compte Google',
    logo: googleLogo,
    description:
      'Retrouvez vos rendez-vous Orvia dans votre agenda Google et tenez compte de vos créneaux occupés.',
  },
  {
    id: 'microsoft',
    name: 'Microsoft Outlook',
    account: 'Outlook et Microsoft 365',
    logo: outlookLogo,
    description:
      'Reliez votre agenda Outlook pour organiser vos rendez-vous professionnels au même endroit.',
  },
];
const props = defineProps<{
  request: (path: string, body?: any) => Promise<any>;
  workspace?: string;
  simple?: boolean;
}>();
const zone = ref('America/Toronto');
const loaded = ref(false);
const rows = ref<any[]>([]),
  busy = ref(false),
  error = ref(''),
  message = ref(''),
  start = ref(''),
  end = ref(''),
  periods = ref<any[]>([]),
  checkedSpace = ref(''),
  history = ref<Record<string, any>>({}),
  password = ref(''),
  ack = ref(false);
async function load() {
  rows.value = (await props.request('calendar/')).connections.filter(
    (row: any) => !props.workspace || row.workspace === props.workspace,
  );
  for (const row of rows.value) {
    try {
      history.value[row.workspace] = await props.request(`calendar/${row.workspace}/sync/`);
    } catch {
      history.value[row.workspace] = null;
    }
  }
  loaded.value = true;
}
async function run(action: () => Promise<void>) {
  busy.value = true;
  error.value = '';
  try {
    await action();
  } catch (e: any) {
    error.value = e.message;
    periods.value = [];
    checkedSpace.value = '';
  } finally {
    busy.value = false;
  }
}
async function connect(row: any, provider: string) {
  await run(async () => {
    const result = await props.request(`calendar/${row.workspace}/start/`, { provider });
    location.assign(result.authorization_url);
  });
}
async function disconnect(row: any) {
  await run(async () => {
    await props.request(`calendar/${row.workspace}/disconnect/`, { revision: row.revision });
    message.value =
      'Connexion retirée d’Orvia. Vous pouvez aussi révoquer le consentement dans votre compte Google ou Microsoft.';
    periods.value = [];
    checkedSpace.value = '';
    await load();
  });
}
async function check(row: any) {
  await run(async () => {
    checkedSpace.value = '';
    periods.value = [];
    const result = await props.request(`calendar/${row.workspace}/busy/`, {
      starts_at: props.simple
        ? bookingInterval(start.value, zone.value, 15).starts_at
        : start.value,
      ends_at: props.simple ? bookingInterval(end.value, zone.value, 15).starts_at : end.value,
    });
    periods.value = result.busy;
    checkedSpace.value = row.workspace;
  });
}
async function toggle(row: any) {
  await run(async () => {
    await props.request(`calendar/${row.workspace}/sync-config/`, {
      revision: row.revision,
      enabled: !row.auto_sync,
    });
    await load();
  });
}
async function sync(row: any) {
  await run(async () => {
    const result = await props.request(`calendar/${row.workspace}/sync/`, {});
    message.value = 'Vérification terminée : ' + countText(result.counts);
    await load();
  });
}
async function withdraw(row: any) {
  if (
    !confirm(
      'Retirer les événements Orvia de cet agenda et arrêter leur synchronisation ? Les rendez-vous CRM sont conservés.',
    )
  )
    return;
  await run(async () => {
    const result = await props.request(`calendar/${row.workspace}/withdraw/`, { confirm: true });
    message.value =
      'Retrait : ' + countText(result.counts) + '. Vérifiez les erreurs avant de déconnecter.';
    await load();
  });
}
async function detach(row: any) {
  await run(async () => {
    try {
      await props.request(`calendar/${row.workspace}/detach/`, {
        current_password: password.value,
        revision: row.revision,
        confirm_external_cleanup: ack.value,
      });
      message.value =
        'Nettoyage manuel confirmé. Connexion locale retirée ; aucun événement distant supprimé par cette action.';
      ack.value = false;
      await load();
    } finally {
      password.value = '';
    }
  });
}
async function page(row: any, url: string) {
  await run(async () => {
    const parsed = new URL(url, location.origin);
    history.value[row.workspace] = await props.request(
      `calendar/${row.workspace}/sync/${parsed.search}`,
    );
  });
}
const states: Record<string, string> = {
  synced: 'Synchronisé',
  pending: 'À reprendre',
  error: 'Erreur',
  removed: 'Retiré',
  abandoned: 'Nettoyage manuel confirmé',
};
const errors: Record<string, string> = {
  slot_busy: 'Créneau occupé',
  event_changed: 'Événement modifié dans l’agenda : vérification manuelle requise',
  event_has_attendees: 'Participants ajoutés : action automatique bloquée',
  uncertain_create: 'Création non confirmée : vérifiez l’agenda, aucun nouvel envoi automatique',
  provider_unavailable: 'Fournisseur indisponible',
  source_unavailable: 'Rendez-vous CRM indisponible',
  source_changed: 'Rendez-vous modifié pendant la synchronisation',
  past_source: 'Rendez-vous passé',
};
function countText(counts: Record<string, number>) {
  return (
    Object.entries(counts)
      .map(([key, n]) => `${states[key] || key} : ${n}`)
      .join(', ') || 'Aucun rendez-vous à traiter'
  );
}
onMounted(() => run(load));
</script>
<template>
  <section class="calendar-hub" :aria-busy="busy">
    <div class="calendar-hero">
      <div class="hero-copy">
        <span class="calendar-eyebrow"><Link2 :size="14" /> VOTRE AGENDA PERSONNEL</span>
        <h2>Vos agendas.<span> Bien connectés.</span></h2>
        <p>
          Connectez votre agenda pour que vos réservations Orvia trouvent leur place dans votre
          journée.
        </p>
        <span class="hero-privacy"
          ><ShieldCheck :size="15" /> Vos événements personnels restent privés</span
        >
      </div>
      <div class="hero-art" aria-hidden="true">
        <span class="orbit orbit-one"></span><span class="orbit orbit-two"></span>
        <div class="mini-calendar">
          <div class="mini-calendar-top"><span></span><span></span></div>
          <CalendarDays :size="43" :stroke-width="1.4" /><span>Votre agenda Orvia</span>
        </div>
        <span class="floating-logo google"><img :src="googleLogo" alt="" /></span>
        <span class="floating-logo outlook"><img :src="outlookLogo" alt="" /></span>
        <span class="art-check"><Check :size="18" /></span>
      </div>
    </div>
    <div class="connection-heading">
      <div>
        <h3>Choisissez votre agenda</h3>
        <p>Un agenda principal par espace. Vous gardez le contrôle.</p>
      </div>
      <button class="calendar-refresh" :disabled="busy" @click="run(load)">
        <RefreshCw :size="15" :class="{ spinning: busy }" />Actualiser
      </button>
    </div>
    <p v-if="error" role="alert" class="calendar-feedback error">{{ error }}</p>
    <p v-if="message" role="status" class="calendar-feedback success">{{ message }}</p>
    <p v-if="busy && !loaded" role="status" class="calendar-empty">Chargement de vos connexions…</p>
    <p v-if="loaded && !rows.length" class="calendar-empty">
      Votre rôle actuel ne possède pas d’agenda à connecter.
    </p>
    <div v-for="row in rows" :key="row.workspace" class="workspace-calendars">
      <div class="workspace-label">
        <span :class="row.workspace"></span>Espace
        {{ row.workspace === 'assurance' ? 'Assurance' : 'Isolation'
        }}<small>{{ row.connected ? '1 agenda connecté' : 'Aucun agenda connecté' }}</small>
      </div>
      <div class="provider-grid">
        <section
          v-for="provider in providers"
          :key="provider.id"
          class="provider-card"
          :class="{
            connected: row.connected && row.provider === provider.id,
            unavailable: !row.configured[provider.id],
          }"
        >
          <div class="provider-top">
            <span class="provider-logo"><img :src="provider.logo" alt="" /></span
            ><span
              class="provider-status"
              :class="{ linked: row.connected && row.provider === provider.id }"
              ><span></span
              >{{
                row.connected && row.provider === provider.id
                  ? 'Connecté'
                  : row.configured[provider.id]
                    ? 'Non connecté'
                    : 'À venir'
              }}</span
            >
          </div>
          <h4>{{ provider.name }}</h4>
          <span class="provider-account">{{ provider.account }}</span>
          <p>{{ provider.description }}</p>
          <div class="provider-benefit"><Check :size="15" /> Créneaux occupés pris en compte</div>
          <div class="provider-benefit">
            <Check :size="15" /> Publication des rendez-vous, à votre choix
          </div>
          <button
            class="provider-connect"
            :disabled="busy || !row.configured[provider.id] || row.connected"
            @click="connect(row, provider.id)"
          >
            <Check v-if="row.connected && row.provider === provider.id" :size="17" />
            {{
              row.connected && row.provider === provider.id
                ? 'Agenda connecté'
                : !row.configured[provider.id]
                  ? 'Disponible prochainement'
                  : row.connected
                    ? 'Autre agenda déjà connecté'
                    : `Connecter ${provider.name}`
            }}
            <ArrowRight v-if="!row.connected && row.configured[provider.id]" :size="17" />
          </button>
          <span class="provider-footnote">{{
            !row.configured[provider.id]
              ? 'La connexion à ce service n’est pas encore activée.'
              : row.connected && row.provider === provider.id
                ? 'Agenda principal · Synchronisation ' +
                  (row.auto_sync ? 'activée' : 'non activée')
                : row.connected
                  ? 'Retirez les événements et déconnectez l’agenda actuel pour changer.'
                  : 'Vous choisissez le compte à autoriser.'
          }}</span>
        </section>
      </div>
      <div v-if="!row.connected" class="connection-steps" aria-label="Les étapes de connexion">
        <div>
          <span>1</span>
          <p><strong>Connectez votre compte</strong>Autorisez l’accès à votre agenda.</p>
        </div>
        <div>
          <span>2</span>
          <p>
            <strong>Définissez vos horaires</strong>Choisissez vos plages de rendez-vous{{
              simple ? ' dans « Mes disponibilités »' : ''
            }}.
          </p>
        </div>
        <div>
          <span>3</span>
          <p><strong>Activez la publication</strong>Retrouvez les rendez-vous dans votre agenda.</p>
        </div>
      </div>
      <div v-if="row.connected" class="connected-tools">
        <div class="connected-heading">
          <div>
            <span class="calendar-eyebrow">VOTRE CONNEXION</span>
            <h3>Gérez votre agenda connecté</h3>
          </div>
          <button class="calendar-disconnect" :disabled="busy" @click="disconnect(row)">
            <Unplug :size="15" />Déconnecter
          </button>
        </div>
        <form class="availability-check" @submit.prevent="check(row)">
          <fieldset :disabled="busy">
            <legend><Clock3 :size="17" />Vérifier une période <span>31 jours maximum</span></legend>
            <label v-if="simple"
              >Fuseau de consultation<select v-model="zone">
                <option value="America/Toronto">Toronto / Montréal</option>
                <option value="America/Vancouver">Vancouver</option>
                <option value="America/Edmonton">Edmonton</option>
                <option value="America/Winnipeg">Winnipeg</option>
                <option value="America/Halifax">Halifax</option>
                <option value="America/St_Johns">Saint-Jean</option>
              </select></label
            >
            <label
              >{{ simple ? 'Début de la période' : 'Début ISO 8601 avec décalage'
              }}<input
                v-model="start"
                :type="simple ? 'datetime-local' : 'text'"
                placeholder="2026-12-01T00:00:00-05:00"
                required
            /></label>
            <label
              >{{ simple ? 'Fin de la période' : 'Fin ISO 8601 avec décalage'
              }}<input
                v-model="end"
                :type="simple ? 'datetime-local' : 'text'"
                placeholder="2026-12-02T00:00:00-05:00"
                required
            /></label>
            <button class="calendar-action">Vérifier les disponibilités</button>
          </fieldset>
        </form>
        <section v-if="checkedSpace === row.workspace" class="busy-results" aria-live="polite">
          <p>
            Consultation réussie : {{ periods.length }} période(s) occupée(s). Cette consultation ne
            réserve rien et ne vérifie pas les autres agendas.
          </p>
          <p v-for="(period, index) in periods" :key="index">
            {{ new Date(period.start).toLocaleString('fr-FR', simple ? { timeZone: zone } : {}) }} →
            {{ new Date(period.end).toLocaleString('fr-FR', simple ? { timeZone: zone } : {}) }}
            {{ simple ? zone : '' }}
          </p>
        </section>
      </div>
      <section v-if="row.provider" class="sync-settings">
        <div class="sync-heading">
          <span class="sync-icon"><RefreshCw :size="20" /></span>
          <div>
            <h4>Vos rendez-vous Orvia dans votre agenda</h4>
            <span class="sync-status" :class="{ enabled: row.auto_sync }">{{
              row.auto_sync
                ? 'Publication automatique activée'
                : 'Publication automatique désactivée'
            }}</span>
          </div>
        </div>
        <p>
          Synchronisation {{ row.auto_sync ? 'activée' : 'arrêtée' }}. Le CRM reste la référence.
          Les changements sont publiés par le worker serveur ou le bouton ci-dessous. Un conflit
          externe ne supprime pas le rendez-vous interne.
        </p>
        <div class="sync-actions">
          <button
            v-if="row.connected"
            class="calendar-action"
            :disabled="busy"
            @click="toggle(row)"
          >
            {{ row.auto_sync ? 'Arrêter la synchronisation' : 'Activer la synchronisation' }}
          </button>
          <button
            v-if="row.connected"
            class="calendar-outline"
            :disabled="busy || !row.auto_sync"
            @click="sync(row)"
          >
            Synchroniser maintenant
          </button>
        </div>
        <details class="sync-history" v-if="history[row.workspace]">
          <summary>
            Historique de synchronisation
            <span>{{ history[row.workspace].count }} événement(s)</span>
          </summary>
          <section>
            <p v-if="!history[row.workspace].count">Aucun événement publié.</p>
            <p v-for="event in history[row.workspace].results" :key="event.source_id">
              Rendez-vous {{ event.source_id }} · {{ states[event.status] || event.status }}
              <span v-if="event.error_code"
                >· {{ errors[event.error_code] || 'Vérification nécessaire' }}</span
              >
              ·
              {{
                event.checked_at
                  ? new Date(event.checked_at).toLocaleString('fr-FR')
                  : 'Non vérifié'
              }}
            </p>
            <button
              class="secondary"
              :disabled="busy || !history[row.workspace].previous"
              @click="page(row, history[row.workspace].previous)"
            >
              Précédent
            </button>
            <button
              class="secondary"
              :disabled="busy || !history[row.workspace].next"
              @click="page(row, history[row.workspace].next)"
            >
              Suivant
            </button>
          </section>
        </details>
        <details class="advanced-settings">
          <summary>Changer d’agenda ou résoudre un problème de connexion</summary>
          <p>
            Avant de changer de compte, retirez les événements Orvia publiés dans l’agenda actuel.
            Vos rendez-vous restent dans le CRM.
          </p>
          <button
            v-if="row.connected"
            class="calendar-outline"
            :disabled="busy"
            @click="withdraw(row)"
          >
            Retirer les événements Orvia de cet agenda
          </button>
          <h4>Récupération après nettoyage manuel</h4>
          <p>
            Si le fournisseur refuse l’accès ou si une création reste incertaine, vérifiez et
            supprimez vous-même les anciens événements Orvia chez Google/Microsoft. Cette
            confirmation efface la connexion locale et arrête la synchronisation ; elle ne supprime
            aucun événement distant.
          </p>
          <form @submit.prevent="detach(row)">
            <fieldset :disabled="busy">
              <label
                ><input v-model="ack" type="checkbox" required />J’ai vérifié et retiré les anciens
                événements Orvia dans l’agenda externe.</label
              >
              <label
                >Mot de passe actuel<input
                  v-model="password"
                  type="password"
                  autocomplete="current-password"
                  required
              /></label>
              <button class="secondary">Confirmer le nettoyage manuel et déconnecter</button>
            </fieldset>
          </form>
        </details>
      </section>
    </div>
    <PortalCalendly v-if="rows.some((row) => row.workspace === 'assurance')" :request="request" />
    <details class="calendar-privacy">
      <summary>
        <ShieldCheck :size="18" /><span>Votre agenda vous appartient</span
        ><span class="privacy-more">Confidentialité et fonctionnement</span>
      </summary>
      <p>
        Événements privés, sans participant ni invitation. La publication ne garantit pas une
        réservation atomique : un autre événement peut être ajouté entre les contrôles. Les
        modifications dans Google/Microsoft ne mettent pas à jour le CRM. Aucun intitulé privé
        externe n’est affiché.
      </p>
    </details>
  </section>
</template>
<style scoped>
.calendar-hub {
  color: #20334e;
  --calendar-blue: #2864e8;
}
.calendar-hub p {
  margin: 0;
  color: #697991;
  line-height: 1.65;
}
.calendar-hub h2,
.calendar-hub h3,
.calendar-hub h4 {
  margin: 0;
}
.calendar-hub button {
  font: inherit;
  cursor: pointer;
  transition:
    background 0.18s,
    box-shadow 0.18s,
    transform 0.18s;
}
.calendar-hub button:disabled {
  cursor: default;
  opacity: 0.6;
}
.calendar-hub button:focus-visible,
.calendar-hub summary:focus-visible {
  outline: 3px solid #8aafff;
  outline-offset: 4px;
}
.calendar-hero {
  position: relative;
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: center;
  padding: 24px 32px;
  border-radius: 22px;
  background: radial-gradient(ellipse at 95% 5%, #365c98 0, transparent 55%),
    linear-gradient(120deg, #102332, #1c365c);
  overflow: hidden;
}
.hero-copy {
  position: relative;
  z-index: 1;
  max-width: 580px;
}
.calendar-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1.8px;
}
.hero-copy .calendar-eyebrow {
  color: #b7ccf5;
}
.calendar-hero h2 {
  color: white;
  font-size: clamp(25px, 2.3vw, 35px);
  line-height: 1.22;
  letter-spacing: -1px;
  margin: 13px 0 12px;
}
.calendar-hero h2 span {
  color: #b6d0ff;
}
.calendar-hero p {
  font-size: 13px;
  color: #cfdbec;
  max-width: 480px;
}
.hero-privacy {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin-top: 19px;
  color: #b9d9d0;
  font-size: 11px;
}
.hero-art {
  position: relative;
  flex: 0 0 270px;
  height: 154px;
  margin-right: 24px;
}
.orbit {
  position: absolute;
  width: 230px;
  height: 230px;
  border: 1px solid #ffffff13;
  border-radius: 50%;
  inset: -19px auto auto 20px;
}
.orbit-two {
  width: 320px;
  height: 320px;
  inset: -64px auto auto -25px;
}
.mini-calendar {
  position: absolute;
  left: 70px;
  top: 28px;
  width: 150px;
  height: 150px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 11px;
  border-radius: 20px;
  background: #ffffff;
  box-shadow: 0 20px 45px #08142744;
  color: #5e72d9;
  transform: rotate(-7deg);
  overflow: hidden;
}
.mini-calendar-top {
  height: 30px;
  width: 100%;
  background: #edf1ff;
  display: flex;
  gap: 12px;
  align-items: center;
  padding-left: 16px;
}
.mini-calendar-top span {
  height: 5px;
  width: 5px;
  border-radius: 50%;
  background: #b6c3e4;
}
.mini-calendar > span {
  color: #71809a;
  font-size: 10px;
}
.floating-logo {
  position: absolute;
  display: grid;
  place-items: center;
  width: 64px;
  height: 64px;
  background: #fff;
  border: 1px solid #edf1fa;
  border-radius: 17px;
  box-shadow: 0 12px 28px #08142730;
}
.floating-logo img {
  width: 39px;
  height: 39px;
  object-fit: contain;
}
.floating-logo.google {
  left: 15px;
  top: 19px;
  transform: rotate(8deg);
}
.floating-logo.outlook {
  right: 0;
  bottom: 0;
  transform: rotate(8deg);
}
.art-check {
  position: absolute;
  left: 45px;
  bottom: 1px;
  background: #b7f0d9;
  color: #1f7660;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  border: 4px solid #213c60;
}
.connection-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin: 27px 0 18px;
}
.calendar-hub .connection-heading h3 {
  font-size: 19px;
  letter-spacing: -0.4px;
  margin-bottom: 5px;
}
.connection-heading p {
  font-size: 12px;
}
.calendar-hub .calendar-refresh {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: white;
  border: 1px solid #dfe5f0;
  color: #5d708e;
  border-radius: 10px;
  padding: 10px 13px;
  font-size: 12px;
}
.calendar-feedback {
  padding: 13px 17px;
  border-radius: 12px;
  margin-bottom: 16px !important;
  font-size: 13px;
}
.calendar-feedback.error {
  color: #a13745;
  background: #fff0f1;
  border: 1px solid #f1ccd3;
}
.calendar-feedback.success {
  color: #256a51;
  background: #edf9f2;
  border: 1px solid #c9ebda;
}
.calendar-empty {
  padding: 28px;
  text-align: center;
  background: #f4f7fc;
  border-radius: 14px;
}
.workspace-calendars {
  margin: 0 0 24px;
  padding: 0;
  border: 0;
  background: transparent;
  box-shadow: none;
}
.workspace-label {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #526880;
  font-weight: 600;
  font-size: 11px;
  margin-bottom: 12px;
}
.workspace-label > span {
  width: 6px;
  height: 6px;
  background: #7971d5;
  border-radius: 50%;
}
.workspace-label > span.isolation {
  background: #35ac87;
}
.workspace-label small {
  font-size: 10px;
  font-weight: 400;
  color: #8290a3;
  margin-left: auto;
}
.provider-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}
.provider-card {
  position: relative;
  min-width: 0;
  padding: 24px;
  border: 1px solid #dfe6f1;
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 5px 22px #1e3e7110;
  transition:
    box-shadow 0.2s,
    border-color 0.2s;
}
.provider-card:hover {
  border-color: #bccdef;
  box-shadow: 0 9px 25px #1e3e7115;
}
.provider-card.connected {
  border-color: #7bc7aa;
  background: linear-gradient(135deg, white 70%, #f0faf5);
}
.provider-card.unavailable {
  background: #f9faff;
  box-shadow: none;
}
.provider-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 17px;
}
.provider-logo {
  display: grid;
  place-items: center;
  width: 60px;
  height: 60px;
  border: 1px solid #e8edf5;
  border-radius: 16px;
  background: #fff;
}
.provider-logo img {
  width: 38px;
  height: 38px;
  object-fit: contain;
}
.provider-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  color: #697991;
  background: #f1f4f9;
  padding: 6px 10px;
  border-radius: 30px;
}
.provider-status > span {
  width: 5px;
  height: 5px;
  background: #91a0b6;
  border-radius: 50%;
}
.provider-status.linked {
  color: #267854;
  background: #e5f6ed;
}
.provider-status.linked > span {
  background: #2caa73;
}
.calendar-hub .provider-card h4 {
  font-size: 19px;
  letter-spacing: -0.4px;
  font-weight: 700;
  margin-bottom: 4px;
}
.provider-account {
  display: block;
  color: #8290a6;
  font-size: 11px;
}
.provider-card > p {
  font-size: 12px;
  margin: 15px 0;
  max-width: 470px;
}
.provider-benefit {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #566b89;
  font-size: 11px;
  margin-top: 8px;
}
.provider-benefit svg {
  color: #689b8d;
  flex-shrink: 0;
}
.calendar-hub button.provider-connect {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  background: var(--calendar-blue);
  color: white;
  border: 1px solid transparent;
  border-radius: 10px;
  padding: 12px 14px;
  margin-top: 23px;
  font-size: 12px;
  font-weight: 600;
  min-height: 44px;
}
.calendar-hub button.provider-connect:not(:disabled):hover {
  background: #1850c4;
  box-shadow: 0 4px 12px #2864e82b;
  transform: translateY(-1px);
}
.calendar-hub button.provider-connect:disabled {
  background: #eaf0f8;
  color: #667994;
  opacity: 1;
}
.calendar-hub .connected button.provider-connect:disabled {
  background: #e6f5ed;
  color: #287657;
}
.provider-footnote {
  display: block;
  text-align: center;
  color: #8a96a8;
  font-size: 10px;
  margin-top: 10px;
  line-height: 1.5;
}
.connection-steps {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 22px;
  padding: 23px 5px 3px;
}
.connection-steps > div {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}
.connection-steps > div > span {
  display: grid;
  place-items: center;
  background: #edf1fc;
  color: #6679b5;
  border-radius: 50%;
  width: 25px;
  height: 25px;
  flex-shrink: 0;
  font-weight: 600;
  font-size: 11px;
}
.connection-steps p {
  font-size: 10px;
  line-height: 1.65;
}
.connection-steps strong {
  display: block;
  color: #4e607b;
  font-size: 11px;
  font-weight: 600;
  margin-bottom: 3px;
}
.connected-tools,
.sync-settings {
  margin-top: 20px;
  padding: 22px;
  background: #fff;
  border: 1px solid #e1e7f0;
  border-radius: 16px;
}
.connected-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 22px;
}
.connected-heading .calendar-eyebrow {
  color: #8293af;
  font-size: 9px;
}
.calendar-hub .connected-heading h3 {
  font-size: 17px;
  margin-top: 6px;
}
.calendar-hub .calendar-disconnect {
  display: inline-flex;
  gap: 7px;
  align-items: center;
  color: #91616a;
  background: #fff;
  border: 1px solid #eadce0;
  border-radius: 9px;
  padding: 9px 12px;
  font-size: 11px;
}
.calendar-hub fieldset {
  min-width: 0;
  border: 0;
  margin: 0;
  padding: 0;
}
.availability-check fieldset {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: flex-end;
}
.availability-check legend {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 16px;
}
.availability-check legend span {
  color: #8a97ab;
  font-size: 10px;
  font-weight: 400;
  margin-left: 4px;
}
.calendar-hub label {
  color: #657792;
  font-size: 11px;
  margin: 0;
  flex: 1 1 180px;
}
.calendar-hub input,
.calendar-hub select {
  color: #304b70;
  background: #fafbff;
  border: 1px solid #dfe6f0;
  border-radius: 9px;
  padding: 10px;
  margin-top: 7px;
  font-size: 12px;
}
.calendar-hub input:focus,
.calendar-hub select:focus {
  border-color: #779df0;
  box-shadow: 0 0 0 3px #edf3ff;
}
.calendar-hub .calendar-action,
.calendar-hub .calendar-outline {
  display: inline-flex;
  justify-content: center;
  align-items: center;
  gap: 7px;
  padding: 11px 14px;
  border-radius: 9px;
  font-size: 12px;
  border: 1px solid transparent;
  background: var(--calendar-blue);
  color: white;
}
.calendar-hub .calendar-outline {
  background: white;
  color: #5a7293;
  border-color: #dfe6f0;
}
.busy-results {
  padding: 14px 17px;
  background: #f0f6ff;
  border-radius: 10px;
  margin-top: 16px;
  font-size: 12px;
}
.sync-heading {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 13px;
}
.calendar-hub .sync-heading h4 {
  font-size: 15px;
}
.sync-icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: #eeebff;
  color: #7b68c4;
}
.sync-status {
  display: block;
  margin-top: 5px;
  font-size: 11px;
  color: #8995a8;
}
.sync-status.enabled {
  color: #26805e;
}
.sync-settings > p {
  font-size: 12px;
}
.sync-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 17px 0;
}
.calendar-hub .sync-history,
.calendar-hub .advanced-settings {
  border-top: 1px solid #e8edf5;
  padding: 15px 0 0;
  margin-top: 15px;
  font-size: 12px;
}
.calendar-hub summary {
  cursor: pointer;
  color: #4f6685;
  line-height: 1.6;
}
.sync-history summary span {
  color: #8c99ac;
  font-size: 10px;
  margin-left: 8px;
}
.sync-history section {
  padding-top: 12px;
}
.sync-history section p {
  padding: 9px 0;
  border-bottom: 1px solid #f0f3f8;
}
.sync-history button {
  margin: 10px 7px 0 0;
}
.advanced-settings p {
  margin: 13px 0;
}
.advanced-settings h4 {
  margin: 19px 0 7px;
  font-size: 13px;
}
.advanced-settings label {
  display: block;
  margin-bottom: 12px;
}
.advanced-settings input[type='checkbox'] {
  width: auto;
  margin: 0 8px 0 0;
  accent-color: var(--calendar-blue);
}
.calendar-hub .calendar-privacy {
  padding: 17px 20px;
  border: 1px solid #dfe9ee;
  background: #f4f9f8;
  border-radius: 12px;
}
.calendar-privacy summary {
  display: flex;
  gap: 9px;
  align-items: center;
  list-style: none;
  color: #4d766e;
  font-size: 12px;
}
.calendar-privacy summary::-webkit-details-marker {
  display: none;
}
.privacy-more {
  margin-left: auto;
  color: #7b938e;
  font-size: 10px;
}
.privacy-more::after {
  content: ' +';
  font-size: 15px;
}
.calendar-privacy[open] .privacy-more::after {
  content: ' −';
}
.calendar-privacy p {
  font-size: 11px;
  padding-top: 13px;
}
.spinning {
  animation: calendar-spin 1s linear infinite;
}
@keyframes calendar-spin {
  to {
    transform: rotate(360deg);
  }
}
@media (max-width: 800px) {
  .calendar-hero {
    padding: 26px;
  }
  .hero-art {
    flex-basis: 220px;
    margin-right: -15px;
    transform: scale(0.85);
  }
  .provider-card {
    padding: 20px;
  }
  .connection-steps {
    gap: 14px;
  }
}
@media (max-width: 600px) {
  .calendar-hero {
    padding: 24px;
  }
  .hero-art {
    display: none;
  }
  .hero-copy {
    max-width: none;
  }
  .provider-grid,
  .connection-steps {
    grid-template-columns: 1fr;
  }
  .connection-heading {
    align-items: flex-start;
  }
  .connection-heading h3 {
    font-size: 17px;
  }
  .calendar-hub .calendar-refresh {
    font-size: 11px;
    padding: 9px;
  }
  .connected-heading {
    align-items: flex-start;
  }
  .privacy-more {
    display: none;
  }
  .availability-check fieldset {
    flex-direction: column;
    align-items: stretch;
  }
  .availability-check label {
    flex: auto;
  }
  .availability-check legend {
    flex-wrap: wrap;
  }
  .sync-settings,
  .connected-tools {
    padding: 17px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .calendar-hub *,
  .calendar-hub *::after {
    animation: none !important;
    transition: none !important;
  }
}
</style>
