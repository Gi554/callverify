<script setup lang="ts">
import { ref } from 'vue';
import { ClipboardList } from 'lucide-vue-next';

type Session = {
  id: number;
  actor: string;
  subject: number;
  username: string;
  workspace: string;
  reason: string;
  started_at: string;
};
type Detail = {
  actions: {
    id: number;
    source: string;
    created_at: string;
    method: string;
    path: string;
    status: number | null;
  }[];
  ended_at: string | null;
  expires: number | null;
  truncated: boolean;
  business_unavailable: boolean;
  journal: boolean;
};
const props = defineProps<{ request: (path: string) => Promise<any> }>();
const sessions = ref<Session[]>();
const selected = ref<Session>();
const detail = ref<Detail>();
const busy = ref(false);
const error = ref('');
const page = ref(1);
const more = ref(false);
const spaces: Record<string, string> = {
  assurance: 'Assurance',
  isolation: 'Isolation',
  portal: 'Portail',
};
const date = new Intl.DateTimeFormat('fr-CA', {
  dateStyle: 'short',
  timeStyle: 'medium',
  timeZone: 'America/Toronto',
});

async function load(next = 1) {
  if (busy.value) return;
  busy.value = true;
  error.value = '';
  try {
    const result = await props.request(`platform/support/journal/?page=${next}`);
    sessions.value = result.results;
    more.value = !!result.next;
    page.value = next;
    selected.value = undefined;
    detail.value = undefined;
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'Journal indisponible.';
  } finally {
    busy.value = false;
  }
}
async function open(row: Session) {
  if (busy.value) return;
  selected.value = row;
  detail.value = undefined;
  busy.value = true;
  error.value = '';
  try {
    detail.value = await props.request(`platform/support/journal/${row.id}/`);
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'Détail indisponible.';
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <section class="support-journal" :aria-busy="busy">
    <header>
      <h2><ClipboardList :size="20" /> Sessions d’assistance</h2>
      <button type="button" class="secondary" :disabled="busy" @click="load(page)">
        {{ sessions ? 'Actualiser' : 'Afficher le journal' }}
      </button>
    </header>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="sessions && !sessions.length">Aucune session enregistrée.</p>
    <ul v-if="sessions?.length" class="support-list">
      <li v-for="row in sessions" :key="row.id">
        <div>
          <strong>{{ row.actor }} → {{ row.username || 'Compte #' + row.subject }}</strong>
          <span>{{ spaces[row.workspace] }} · {{ date.format(new Date(row.started_at)) }}</span>
          <p>{{ row.reason }}</p>
        </div>
        <button type="button" class="secondary" :disabled="busy" @click="open(row)">
          Voir les actions
        </button>
      </li>
    </ul>
    <nav v-if="page > 1 || more" aria-label="Pages des sessions">
      <button
        type="button"
        class="secondary"
        :disabled="busy || page === 1"
        @click="load(page - 1)"
      >
        Précédent
      </button>
      <span>Page {{ page }}</span>
      <button type="button" class="secondary" :disabled="busy || !more" @click="load(page + 1)">
        Suivant
      </button>
    </nav>
    <section v-if="selected && detail" class="support-detail">
      <h3>Actions pour {{ selected.username || 'le compte #' + selected.subject }}</h3>
      <p v-if="detail.ended_at">Session fermée le {{ date.format(new Date(detail.ended_at)) }}.</p>
      <p v-else-if="detail.expires">
        Expiration prévue le {{ date.format(new Date(detail.expires * 1000)) }}.
      </p>
      <p v-if="!detail.journal">
        Le détail des actions est disponible pour les sessions ouvertes depuis l’ajout de ce
        journal.
      </p>
      <p v-if="detail.business_unavailable" role="alert">
        Le journal de l’espace métier est temporairement indisponible.
      </p>
      <p v-if="detail.truncated">Seules les actions les plus récentes sont affichées.</p>
      <p v-if="detail.journal && !detail.actions.length && !detail.business_unavailable">
        Aucune action enregistrée.
      </p>
      <ul v-if="detail.actions.length" class="support-list">
        <li v-for="action in detail.actions" :key="action.source + '-' + action.id">
          <div>
            <strong>{{ action.method }} {{ action.path }}</strong>
            <span
              >{{ spaces[action.source] }} ·
              {{ action.status ? 'HTTP ' + action.status : 'Réponse indisponible' }}</span
            >
          </div>
          <time :datetime="action.created_at">{{ date.format(new Date(action.created_at)) }}</time>
        </li>
      </ul>
    </section>
  </section>
</template>

<style scoped>
.support-journal header,
.support-list li,
.support-journal nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}
.support-journal h2 {
  display: flex;
  align-items: center;
  gap: 8px;
}
.support-list {
  padding: 0;
  list-style: none;
}
.support-list li {
  border-bottom: 1px solid #dbe5f1;
  padding: 12px 0;
  overflow-wrap: anywhere;
}
.support-list span {
  display: block;
  color: #526479;
}
.support-list p {
  margin: 4px 0 0;
}
.support-journal nav {
  justify-content: flex-start;
}
.support-detail {
  margin-top: 1rem;
}
</style>
