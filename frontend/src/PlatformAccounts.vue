<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { Search, ShieldCheck, SlidersHorizontal, UsersRound } from 'lucide-vue-next';

type Account = {
  id: number;
  username: string;
  email: string;
  active: boolean;
  protected: boolean;
  memberships: { workspace: string; role: string; active: boolean }[];
};
const props = defineProps<{ request: (path: string, body?: unknown) => Promise<any> }>();
const emit = defineEmits<{ changed: [] }>();
const search = ref('');
const filter = ref('');
const page = ref(1);
const accounts = ref<Account[]>([]);
const hasNext = ref(false);
const busy = ref(false);
const error = ref('');
const notice = ref('');
const selected = ref<Account>();
const action = ref('');
const reason = ref('');
const workspace = ref('assurance');
const scoped = computed(() => ['grant_admin', 'suspend_admin'].includes(action.value));
const spaces: Record<string, string> = { assurance: 'Assurance', isolation: 'Isolation' };

async function load(next = 1) {
  const response = await props.request(
    `platform/accounts/?page=${next}&search=${encodeURIComponent(filter.value)}`,
  );
  accounts.value = response.results;
  page.value = next;
  hasNext.value = !!response.next;
}
async function run(work: () => Promise<void>) {
  if (busy.value) return;
  busy.value = true;
  error.value = '';
  try {
    await work();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'Action indisponible.';
  } finally {
    busy.value = false;
  }
}
function lookup() {
  void run(async () => {
    filter.value = search.value.trim();
    await load();
  });
}
function open(account: Account) {
  selected.value = account;
  action.value = '';
  reason.value = '';
  notice.value = '';
}
function apply() {
  const target = selected.value;
  if (!target || !action.value) return;
  void run(async () => {
    await props.request(`platform/accounts/${target.id}/actions/`, {
      action: action.value,
      reason: reason.value.trim(),
      ...(scoped.value ? { workspace: workspace.value } : {}),
    });
    selected.value = undefined;
    notice.value = 'Action appliquée et journalisée.';
    emit('changed');
    await load(page.value);
  });
}
onMounted(() => run(() => load()));
</script>

<template>
  <section class="account-panel" :aria-busy="busy">
    <header class="account-heading">
      <div class="account-title">
        <span class="heading-icon"><UsersRound :size="20" /></span>
        <div>
          <h2>Administrateurs et accès</h2>
          <p>Gérez les comptes et leurs droits par espace.</p>
        </div>
      </div>
      <form class="controls search" @submit.prevent="lookup">
        <label>
          <span>Rechercher un compte</span>
          <input v-model="search" type="search" placeholder="Identifiant ou e-mail" />
        </label>
        <button type="submit" class="secondary" :disabled="busy">
          <Search :size="16" /> Rechercher
        </button>
      </form>
    </header>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="notice" role="status">{{ notice }}</p>
    <p v-if="busy" role="status">Traitement en cours…</p>
    <p v-else-if="!accounts.length" class="empty">Aucun compte trouvé.</p>
    <ul class="accounts">
      <li v-for="account in accounts" :key="account.id">
        <div class="identity">
          <strong>{{ account.username }}</strong>
          <span class="badge" :class="account.active ? 'active' : 'suspended'">
            {{ account.active ? 'Compte actif' : 'Compte suspendu' }}
          </span>
        </div>
        <div class="grants">
          <span
            v-for="grant in account.memberships"
            :key="grant.workspace"
            class="badge"
            :class="!grant.active ? 'suspended' : grant.workspace"
          >
            {{ spaces[grant.workspace] }} ·
            {{ grant.role === 'administrator' ? 'Administrateur' : grant.role }}
            {{ grant.active ? '' : '· Accès suspendu' }}
          </span>
          <span v-if="!account.memberships.length" class="no-grants">Aucun accès par espace</span>
        </div>
        <span v-if="account.protected" class="badge protected"
          ><ShieldCheck :size="15" /> Compte protégé</span
        >
        <button v-else type="button" class="secondary" :disabled="busy" @click="open(account)">
          <SlidersHorizontal :size="15" /> Gérer
        </button>
      </li>
    </ul>
    <div v-if="page > 1 || hasNext" class="controls">
      <button
        type="button"
        class="secondary"
        :disabled="page <= 1 || busy"
        @click="run(() => load(page - 1))"
      >
        Précédent
      </button>
      <button
        type="button"
        class="secondary"
        :disabled="!hasNext || busy"
        @click="run(() => load(page + 1))"
      >
        Suivant
      </button>
    </div>
    <form v-if="selected" class="controls action-form" @submit.prevent="apply">
      <strong>{{ selected.username }}</strong>
      <label
        >Action<select v-model="action" required>
          <option disabled value="">Sélectionner</option>
          <option value="grant_admin">Attribuer ou réactiver un accès administrateur</option>
          <option value="suspend_admin">Suspendre un accès administrateur</option>
          <option value="revoke_sessions">Révoquer les sessions du compte</option>
          <option v-if="selected.active" value="suspend">
            Suspendre le compte dans tous les espaces
          </option>
          <option v-else value="reactivate">Réactiver le compte</option>
        </select></label
      >
      <label v-if="scoped"
        >Espace<select v-model="workspace">
          <option v-for="(label, key) in spaces" :key="key" :value="key">{{ label }}</option>
        </select></label
      >
      <label>Motif<input v-model="reason" required minlength="3" maxlength="500" /></label>
      <button type="submit" class="primary" :disabled="busy">Confirmer</button>
      <button type="button" class="secondary" :disabled="busy" @click="selected = undefined">
        Annuler
      </button>
    </form>
  </section>
</template>

<style scoped>
.account-panel {
  padding: clamp(16px, 3vw, 26px);
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
}
.account-heading,
.account-title,
.controls,
.grants {
  display: flex;
  align-items: end;
  flex-wrap: wrap;
  gap: 12px;
}
.account-heading {
  justify-content: space-between;
  align-items: center;
}
.account-title {
  align-items: center;
}
.account-title h2,
.account-title p {
  margin: 0;
}
.account-title p,
.no-grants {
  color: #526174;
  font-size: 0.88rem;
}
.heading-icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: #e7f3ed;
  color: #236452;
}
.accounts {
  list-style: none;
  padding: 0;
  margin: 18px 0 0;
  border-top: 1px solid #e2e8f0;
}
.accounts li {
  display: grid;
  grid-template-columns: minmax(170px, 1fr) minmax(170px, 1.5fr) auto;
  align-items: center;
  gap: 12px;
  padding: 14px 0;
  border-bottom: 1px solid #e2e8f0;
}
.identity {
  display: grid;
  justify-items: start;
  gap: 6px;
  overflow-wrap: anywhere;
}
.badge,
button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.badge {
  padding: 4px 9px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 650;
}
.active,
.assurance {
  color: #195746;
  background: #e7f3ed;
}
.isolation,
.protected {
  color: #503b87;
  background: #eee9fa;
}
.suspended {
  color: #8a4218;
  background: #fff1e5;
}
.controls label {
  display: grid;
  gap: 4px;
}
.action-form {
  margin-top: 14px;
  border-radius: 12px;
  background: #f6f4fb;
  padding: 14px;
}
.empty {
  color: #526174;
  padding: 14px;
  background: #f7f9fc;
  border-radius: 10px;
}
@media (max-width: 720px) {
  .accounts li {
    grid-template-columns: 1fr;
    justify-items: start;
  }
  .search,
  .search label {
    flex: 1 1 190px;
  }
}
</style>
