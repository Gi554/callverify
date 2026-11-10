<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

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
    <h2>Administrateurs et accès</h2>
    <form class="controls" @submit.prevent="lookup">
      <label
        >Rechercher un compte<input v-model="search" placeholder="Identifiant ou e-mail"
      /></label>
      <button type="submit" class="secondary" :disabled="busy">Rechercher</button>
    </form>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="notice" role="status">{{ notice }}</p>
    <p v-if="busy" role="status">Traitement en cours…</p>
    <p v-else-if="!accounts.length">Aucun compte trouvé.</p>
    <ul class="accounts">
      <li v-for="account in accounts" :key="account.id">
        <div>
          <strong>{{ account.username }}</strong>
          <span>{{ account.active ? 'Compte actif' : 'Compte suspendu' }}</span>
          <span v-for="grant in account.memberships" :key="grant.workspace">
            {{ spaces[grant.workspace] }} ·
            {{ grant.role === 'administrator' ? 'Administrateur' : grant.role }}
            {{ grant.active ? '' : '· Accès suspendu' }}
          </span>
        </div>
        <span v-if="account.protected">Compte système protégé</span>
        <button v-else type="button" class="secondary" :disabled="busy" @click="open(account)">
          Gérer
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
  padding: 20px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
}
.controls,
.accounts li {
  display: flex;
  align-items: end;
  flex-wrap: wrap;
  gap: 12px;
}
.accounts {
  padding: 0;
}
.accounts li {
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid #e2e8f0;
}
.accounts li div {
  display: grid;
  gap: 3px;
}
.controls label {
  display: grid;
  gap: 4px;
}
.action-form {
  margin-top: 14px;
}
</style>
