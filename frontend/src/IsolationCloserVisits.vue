<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { CalendarDays, Clock3, Users, Sparkles, ArrowUpRight } from 'lucide-vue-next';
import IsolationPageHeader from './IsolationPageHeader.vue';
import IsolationVisitCard from './IsolationVisitCard.vue';
import SidePanel from './SidePanel.vue';
import IsolationC2Snapshot from './IsolationC2Snapshot.vue';
const props = defineProps<{
  request: (path: string, body?: any) => Promise<any>;
  summary?: any;
  username?: string;
}>();
const emit = defineEmits<{ changed: [] }>();
const filter = ref('all');
function changeFilter(value: string) {
  filter.value = value;
  page.value = 1;
  run(load);
}
const rows = ref<any[]>([]),
  count = ref(0),
  page = ref(1),
  busy = ref(false),
  error = ref(''),
  selected = ref<any>(null),
  history = ref<any[]>([]),
  historyPage = ref(1),
  historyCount = ref(0);
const performed = ref(''),
  closed = ref(''),
  note = ref(''),
  reason = ref(''),
  dirty = ref(false);
let requestId = crypto.randomUUID();
function changed() {
  dirty.value = true;
  requestId = crypto.randomUUID();
}
function date(row: any) {
  return new Intl.DateTimeFormat('fr-FR', {
    timeZone: 'America/Toronto',
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(row.starts_at));
}
function close() {
  if (busy.value) return;
  if (!dirty.value || window.confirm('Quitter sans enregistrer le résultat ?')) {
    selected.value = null;
    dirty.value = false;
  }
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
  const data = await props.request(
    `closer-visits/?page=${page.value}${filter.value === 'upcoming' ? '&period=upcoming' : filter.value === 'due' ? '&result_due=true' : ''}`,
  );
  rows.value = data.results;
  count.value = data.count;
}
async function loadHistory() {
  const data = await props.request(
    `closer-visits/${selected.value.id}/history/?page=${historyPage.value}`,
  );
  history.value = data.results;
  historyCount.value = data.count;
}
async function open(row: any) {
  await run(async () => {
    selected.value = await props.request(`closer-visits/${row.id}/`);
    const result = selected.value.result;
    performed.value = result ? (result.performed ? 'yes' : 'no') : '';
    closed.value = result?.closed === true ? 'yes' : result?.closed === false ? 'no' : '';
    note.value = result?.note || '';
    reason.value = '';
    dirty.value = false;
    requestId = crypto.randomUUID();
    historyPage.value = 1;
    await loadHistory();
  });
}
async function save() {
  await run(async () => {
    await props.request(`closer-visits/${selected.value.id}/result/`, {
      request_id: requestId,
      revision: selected.value.revision,
      performed: performed.value === 'yes',
      closed: closed.value === 'yes',
      note: note.value,
      reason: reason.value,
    });
    dirty.value = false;
    selected.value = await props.request(`closer-visits/${selected.value.id}/`);
    requestId = crypto.randomUUID();
    reason.value = '';
    await loadHistory();
    await load();
    emit('changed');
  });
}
onMounted(() => run(load));
</script>
<template>
  <section class="iso-page iso-closer-home">
    <IsolationPageHeader
      title="Mes visites, en un regard"
      subtitle="Consultez les fiches clients et renseignez le résultat des visites."
      :eyebrow="username ? 'BONJOUR ' + username + ' · ISOLATION' : 'MON ESPACE · REPRÉSENTANT'"
      :busy="busy"
      @refresh="run(load)"
    />
    <div class="iso-metrics">
      <button class="iso-metric purple" @click="changeFilter('all')">
        <div>
          <span>Visites attribuées</span><strong>{{ summary?.visits ?? count }}</strong
          ><small>Vos rencontres, votre suivi</small>
        </div>
        <span class="iso-metric-icon"><Users :size="25" /></span>
      </button>
      <button class="iso-metric blue" @click="changeFilter('upcoming')">
        <div>
          <span>Rendez-vous à venir</span><strong>{{ summary?.upcoming ?? '—' }}</strong
          ><small>À préparer sereinement</small>
        </div>
        <span class="iso-metric-icon"><CalendarDays :size="25" /></span>
      </button>
      <button class="iso-metric peach" @click="changeFilter('due')">
        <div>
          <span>Résultats à compléter</span><strong>{{ summary?.results_due ?? '—' }}</strong
          ><small>Gardez l’équipe dans la boucle</small>
        </div>
        <span class="iso-metric-icon"><Clock3 :size="25" /></span>
      </button>
    </div>
    <section class="iso-closer-banner">
      <div>
        <span class="iso-quick-icon"><Sparkles :size="23" /></span>
        <div>
          <h2>Chaque rencontre fait avancer un dossier.</h2>
          <p>Un retour après votre visite, et toute l’équipe sait quelle suite donner.</p>
        </div>
      </div>
      <button class="secondary" :disabled="busy" @click="changeFilter('due')">
        Compléter mes résultats <ArrowUpRight :size="16" />
      </button>
    </section>
    <section class="iso-panel">
      <header class="iso-panel-heading">
        <div>
          <h2>
            Mon carnet de visites <span class="iso-counter">{{ count }}</span>
          </h2>
          <p>Les coordonnées et la qualification sont à portée de main.</p>
        </div>
        <span class="iso-toolbar-note">Heure du Québec</span>
      </header>
      <div class="iso-filter-tabs">
        <button
          v-for="tab in [
            { id: 'all', label: 'Toutes mes visites' },
            { id: 'upcoming', label: 'À venir' },
            { id: 'due', label: 'À compléter' },
          ]"
          :key="tab.id"
          :class="{ active: filter === tab.id }"
          :aria-pressed="filter === tab.id"
          :disabled="busy"
          @click="changeFilter(tab.id)"
        >
          {{ tab.label }}
        </button>
      </div>
    </section>
    <p v-if="error && !selected" role="alert">{{ error }}</p>
    <div v-if="rows.length" class="iso-visits-grid">
      <IsolationVisitCard
        v-for="row in rows"
        :key="row.id"
        :visit="row"
        :busy="busy"
        action-label="Ouvrir la visite"
        @open="open(row)"
      />
    </div>
    <div v-else class="iso-empty">
      <span class="iso-empty-icon"><CalendarDays :size="27" /></span
      ><strong>{{
        busy
          ? 'Chargement de vos visites…'
          : filter === 'due'
            ? 'Vos résultats sont à jour'
            : 'Aucune visite pour le moment'
      }}</strong>
      <p>
        {{
          filter === 'due'
            ? 'Les comptes rendus à compléter apparaîtront ici après vos rendez-vous.'
            : 'Les visites qui vous sont attribuées apparaîtront dans cet espace.'
        }}
      </p>
    </div>
    <footer class="iso-pagination">
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
      :open="!!selected"
      :title="
        selected?.c2_snapshot?.fields?.full_name ||
        selected?.prospect?.name ||
        'Compte rendu de visite'
      "
      eyebrow="ISOLATION · CLOSER"
      :close-disabled="busy"
      @request-close="close"
      ><section v-if="selected" class="iso-detail">
        <p v-if="error" role="alert">{{ error }}</p>
        <p>{{ date(selected) }} · Heure du Québec</p>
        <p>Closer : {{ selected.closer?.name }} · Setter : {{ selected.original_setter.name }}</p>
        <IsolationC2Snapshot :snapshot="selected.c2_snapshot" />
        <form
          v-if="selected.status === 'scheduled' && Date.parse(selected.ends_at) <= Date.now()"
          @submit.prevent="save"
          @input="changed"
          @change="changed"
        >
          <fieldset :disabled="busy">
            <label
              >Rendez-vous tenu<select
                v-model="performed"
                required
                @change="closed = performed === 'no' ? 'no' : ''"
              >
                <option value="">Choisir</option>
                <option value="yes">Oui</option>
                <option value="no">Non</option>
              </select></label
            ><label
              >Vente conclue<select v-model="closed" required :disabled="performed !== 'yes'">
                <option value="">Choisir</option>
                <option value="yes">Oui</option>
                <option value="no">Non</option>
              </select></label
            ><label>Notes facultatives<textarea v-model="note" maxlength="3000"></textarea></label
            ><label v-if="selected.result"
              >Motif de la correction<textarea
                v-model="reason"
                required
                maxlength="1000"
              ></textarea></label
            ><button class="primary" :disabled="!performed || !closed">
              {{ selected.result ? 'Enregistrer la correction' : 'Enregistrer le résultat' }}
            </button>
          </fieldset>
        </form>
        <p v-else>
          {{
            selected.status === 'cancelled'
              ? 'Cette visite est annulée.'
              : 'Le résultat sera disponible après la fin du rendez-vous.'
          }}
        </p>
        <h3>Historique des résultats closer</h3>
        <article v-for="entry in history" :key="entry.id">
          <small
            >{{
              new Date(entry.created_at).toLocaleString('fr-CA', { timeZone: 'America/Toronto' })
            }}
            · Closer {{ entry.actor_id }}</small
          >
          <p>
            Tenue : {{ entry.after.performed ? 'Oui' : 'Non' }} · Vente :
            {{ entry.after.closed ? 'Oui' : 'Non' }}
          </p>
          <p>{{ entry.after.note }}</p>
          <p v-if="entry.reason">Motif : {{ entry.reason }}</p>
          <p v-if="entry.before">
            Avant correction : {{ entry.before.performed ? 'tenue' : 'non tenue' }} · vente
            {{
              entry.before.closed === null
                ? 'non renseignée'
                : entry.before.closed
                  ? 'conclue'
                  : 'non conclue'
            }}
            · {{ entry.before.note }}
          </p>
        </article>
        <p v-if="!history.length">Aucun résultat closer enregistré.</p>
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
          Suivant
        </button>
      </section></SidePanel
    >
  </section>
</template>
