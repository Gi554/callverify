<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { ArrowUpRight, CheckCircle2, Link2, RefreshCw, Unplug } from 'lucide-vue-next';

type EventType = { uri: string; name: string; duration: number; scheduling_url: string };
type Connection = {
  configured: boolean;
  connected: boolean;
  revision: number;
  profile: { name: string; scheduling_url: string } | null;
  event_types: EventType[];
  selected_event_type: string;
  checked_at: string | null;
  booking_in_crm: boolean;
};
const props = defineProps<{ request: (path: string, body?: any) => Promise<any> }>();
const account = ref<Connection | null>(null);
const selected = ref('');
const busy = ref(false);
const error = ref('');
const message = ref('');
const synchronization = ref<any>(null);
const choice = computed(() =>
  account.value?.event_types.find((entry) => entry.uri === account.value?.selected_event_type),
);
function accept(value: Connection) {
  account.value = value;
  selected.value = value.selected_event_type;
}
async function load() {
  accept(await props.request('calendly/'));
  synchronization.value = await props.request('calendly/webhooks/');
}
async function activate() {
  await run(async () => {
    synchronization.value = await props.request('calendly/webhooks/', {
      revision: account.value!.revision,
    });
    message.value = 'Synchronisation Calendly activée pour vos réservations Orvia.';
    await load();
  });
}
async function run(action: () => Promise<void>) {
  busy.value = true;
  error.value = '';
  message.value = '';
  try {
    await action();
  } catch (e: any) {
    error.value = e.message;
    // A failed refresh can require reconnection; discard stale connection controls.
    account.value = null;
    try {
      await load();
    } catch {
      // Preserve the first useful error. Retry remains available.
    }
  } finally {
    busy.value = false;
  }
}
async function connect() {
  await run(async () => {
    const result = await props.request('calendly/start/', {});
    location.assign(result.authorization_url);
  });
}
async function refresh() {
  await run(async () => {
    accept(await props.request('calendly/refresh/', { revision: account.value!.revision }));
    message.value = 'Vos pages Calendly sont à jour.';
  });
}
async function save() {
  await run(async () => {
    accept(
      await props.request('calendly/selection/', {
        revision: account.value!.revision,
        event_type: selected.value,
      }),
    );
    message.value = 'Page de réservation préférée enregistrée.';
  });
}
async function disconnect() {
  if (!confirm('Retirer la connexion Calendly de votre compte Orvia ?')) return;
  await run(async () => {
    await props.request('calendly/disconnect/', { revision: account.value!.revision });
    await load();
    message.value =
      'Connexion retirée. Vous pouvez également révoquer Orvia dans les applications autorisées de votre compte Calendly.';
  });
}
onMounted(() => run(load));
</script>

<template>
  <section class="calendly-panel" :aria-busy="busy" aria-labelledby="calendly-title">
    <div class="calendly-heading">
      <div class="calendly-icon"><Link2 :size="25" /></div>
      <div>
        <span class="eyebrow">VOTRE COMPTE, VOTRE AGENDA</span>
        <h3 id="calendly-title">Calendly</h3>
        <p>Reliez votre compte personnel et choisissez votre page de réservation.</p>
      </div>
      <span class="connection-state" :class="{ connected: account?.connected }">
        <CheckCircle2 v-if="account?.connected" :size="14" />
        {{ account?.connected ? 'Connecté' : 'Non connecté' }}
      </span>
    </div>
    <p v-if="error" role="alert" class="calendly-error">{{ error }}</p>
    <p v-if="message" role="status" class="calendly-message">{{ message }}</p>
    <p v-if="busy" role="status">Chargement de Calendly…</p>
    <template v-if="account">
      <template v-if="account.connected">
        <p v-if="!account.booking_in_crm">
          Reconnectez Calendly pour autoriser les créneaux et la réservation depuis Orvia.
        </p>
        <button
          v-if="!account.booking_in_crm"
          type="button"
          :disabled="busy || !account.configured"
          @click="connect"
        >
          Autoriser la réservation Calendly
        </button>
        <div class="calendly-account">
          <strong>{{ account.profile?.name }}</strong>
          <a
            v-if="account.profile"
            :href="account.profile.scheduling_url"
            target="_blank"
            rel="noopener noreferrer"
          >
            Voir mon profil Calendly <ArrowUpRight :size="15" />
          </a>
        </div>
        <form class="calendly-selection" @submit.prevent="save">
          <label for="calendly-event-type">Page de réservation préférée</label>
          <div class="selection-controls">
            <select id="calendly-event-type" v-model="selected" :disabled="busy">
              <option value="">Aucune page sélectionnée</option>
              <option v-for="entry in account.event_types" :key="entry.uri" :value="entry.uri">
                {{ entry.name }} · {{ entry.duration }} min
              </option>
            </select>
            <button
              type="submit"
              class="calendly-primary"
              :disabled="busy || selected === account.selected_event_type"
            >
              Enregistrer
            </button>
          </div>
        </form>
        <p v-if="!account.event_types.length" class="calendly-note">
          Aucune page personnelle active trouvée. Créez ou activez une page individuelle dans
          Calendly, puis actualisez. Les pages d’équipe ne sont pas proposées ici.
        </p>
        <a
          v-if="choice"
          class="booking-link"
          :href="choice.scheduling_url"
          target="_blank"
          rel="noopener noreferrer"
        >
          Ouvrir {{ choice.name }} sur Calendly <ArrowUpRight :size="16" />
        </a>
        <div class="calendly-actions">
          <button type="button" :disabled="busy || !account.configured" @click="refresh">
            <RefreshCw :size="15" /> Actualiser mes pages
          </button>
          <button type="button" :disabled="busy" @click="disconnect">
            <Unplug :size="15" /> Déconnecter
          </button>
          <small v-if="account.checked_at">
            Vérifié le {{ new Date(account.checked_at).toLocaleString('fr-CA') }}
          </small>
        </div>
      </template>
      <div v-else class="calendly-connect">
        <p>
          Vous gardez votre compte et votre forfait Calendly. Cette connexion ne vous ajoute pas à
          l’abonnement de l’équipe Orvia.
        </p>
        <button
          type="button"
          class="calendly-primary"
          :disabled="busy || !account.configured"
          @click="connect"
        >
          <Link2 :size="16" /> Connecter mon Calendly
        </button>
        <small v-if="!account.configured">L’activation Calendly est en attente côté Orvia.</small>
      </div>
      <div v-if="account.connected && synchronization" class="calendly-sync">
        <strong>Synchronisation des rendez-vous</strong>
        <p>
          {{
            synchronization.state === 'active'
              ? 'Active : les réservations Orvia, annulations et reports sont suivis automatiquement.'
              : 'Activez la synchronisation avant de réserver depuis Orvia.'
          }}
        </p>
        <button
          type="button"
          :disabled="busy || !synchronization.configured || !account.booking_in_crm"
          @click="activate"
        >
          {{
            synchronization.state === 'active'
              ? 'Vérifier la synchronisation'
              : 'Activer la synchronisation'
          }}
        </button>
        <p v-if="!synchronization.configured">
          L’activation de la synchronisation est en attente côté Orvia.
        </p>
        <p v-if="synchronization.pending" role="status">
          {{ synchronization.pending }} notification(s) en cours de traitement.
        </p>
        <p v-if="synchronization.needs_review" role="alert">
          {{ synchronization.needs_review }} mise(s) à jour à vérifier avec l’administration.
        </p>
      </div>
      <p class="calendly-note">
        Votre page peut être ouverte dans un nouvel onglet. La réservation depuis une fiche Orvia
        transmet le nom et le courriel du prospect à Calendly ; sa qualification reste dans Orvia.
        La synchronisation active suit les réservations liées à Orvia, leurs annulations et leurs
        reports. Déconnecter Calendly arrête ce suivi ; les rendez-vous déjà créés restent
        conservés.
      </p>
    </template>
    <button v-else-if="!busy" type="button" @click="run(load)">Réessayer</button>
  </section>
</template>

<style scoped>
.calendly-panel {
  margin-top: 24px;
  padding: 26px;
  border: 1px solid #dce5f5;
  border-radius: 22px;
  background: linear-gradient(120deg, #f1f6ff, #fff 65%);
  color: #20334e;
}
.calendly-heading,
.calendly-account,
.calendly-actions,
.selection-controls {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}
.calendly-icon {
  display: grid;
  place-items: center;
  background: #006bff;
  color: white;
  width: 52px;
  height: 52px;
  border-radius: 17px;
}
.eyebrow {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: #56739e;
}
h3 {
  margin: 3px 0;
  font-size: 24px;
}
p {
  line-height: 1.65;
  margin: 6px 0 16px;
}
.connection-state {
  margin-left: auto;
  background: #e9eef8;
  border-radius: 30px;
  padding: 8px 12px;
  font-size: 12px;
}
.connection-state.connected {
  background: #e1f6ec;
  color: #16704d;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.calendly-account {
  margin: 18px 0;
}
a,
button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}
a {
  color: #1559ce;
}
button {
  min-height: 40px;
  padding: 10px 15px;
  border: 1px solid #d7e2f4;
  border-radius: 12px;
  background: white;
  color: #24436c;
  cursor: pointer;
}
button.calendly-primary {
  background: #006bff;
  border-color: #006bff;
  color: white;
}
button:disabled {
  opacity: 0.5;
  cursor: default;
}
label {
  display: block;
  font-weight: 600;
  margin-bottom: 9px;
}
select {
  flex: 1 1 260px;
  width: 100%;
  min-width: 0;
  min-height: 42px;
  padding: 9px 12px;
  border: 1px solid #d7e2f4;
  border-radius: 10px;
  background: white;
  color: inherit;
}
.calendly-actions {
  margin-top: 20px;
}
.booking-link {
  margin-top: 16px;
  font-weight: 600;
}
small,
.calendly-note {
  font-size: 12px;
  color: #556b8a;
}
.calendly-connect small {
  display: block;
  margin-top: 10px;
}
.calendly-note {
  border-top: 1px solid #e0e8f4;
  margin: 22px 0 0;
  padding-top: 16px;
}
.calendly-error {
  color: #aa3141;
}
.calendly-message {
  color: #16704d;
}
:is(button, a, select):focus-visible {
  outline: 3px solid #8eb8ff;
  outline-offset: 3px;
}
@media (max-width: 600px) {
  .calendly-panel {
    padding: 18px;
  }
  .connection-state {
    margin-left: 0;
  }
}
</style>
