<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import PortalInvitations from './PortalInvitations.vue';
import PortalPhoneExtensions from './PortalPhoneExtensions.vue';
import PortalAccessHistory from './PortalAccessHistory.vue';
const activeSection = ref('users');
const sections = [
  { key: 'users', label: 'Utilisateurs' },
  { key: 'invitations', label: 'Invitations' },
  { key: 'phone', label: 'Postes téléphoniques' },
  { key: 'history', label: 'Journal des accès' },
];
import { UserPlus, Pause, Play, Save, ChevronLeft, ChevronRight } from 'lucide-vue-next';
const props = defineProps<{
  spaces: string[];
  username: string;
  request: (path: string, body?: any, method?: string) => Promise<any>;
}>();
const space = ref(props.spaces[0] || ''),
  search = ref(''),
  page = ref(1),
  rows = ref<any[]>([]),
  count = ref(0),
  busy = ref(false),
  error = ref(''),
  message = ref(''),
  adding = ref(false);
const form = ref({
  username: '',
  email: '',
  password: '',
  role: 'setter',
  existing: false,
  prospect_quota: '' as string | number,
});
const roles = () =>
  space.value === 'assurance'
    ? ['administrator', 'setter', 'advisor']
    : ['administrator', 'setter', 'client', 'closer'];
const labels: Record<string, string> = {
  administrator: 'Administrateur',
  setter: 'Setter',
  advisor: 'Conseiller',
  client: 'Client',
  closer: 'Closer',
};
const base = () => `workspaces/${space.value}/users/`;
async function load() {
  busy.value = true;
  error.value = '';
  try {
    const data = await props.request(
      base() + `?search=${encodeURIComponent(search.value)}&page=${page.value}`,
    );
    rows.value = data.results;
    count.value = data.count;
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function update(row: any, changes: any) {
  busy.value = true;
  error.value = '';
  message.value = '';
  try {
    await props.request(base() + row.id + '/', changes, 'PATCH');
    message.value = 'Accès mis à jour.';
    await load();
  } catch (e: any) {
    const detail = e.message;
    await load();
    error.value = detail;
  } finally {
    busy.value = false;
  }
}
function close() {
  adding.value = false;
  form.value = {
    username: '',
    email: '',
    password: '',
    role: 'setter',
    existing: false,
    prospect_quota: '' as string | number,
  };
}
async function create() {
  busy.value = true;
  error.value = '';
  try {
    const { prospect_quota, ...values } = form.value;
    const body: Record<string, any> = values.existing
      ? { username: values.username, role: values.role, existing: true }
      : values;
    // Assurance advisors carry the number of prospects owed to their client.
    if (values.role === 'advisor') body.prospect_quota = Number(prospect_quota);
    await props.request(base(), body);
    close();
    page.value = 1;
    search.value = '';
    await load();
    message.value = 'Utilisateur associé à cet espace.';
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
watch(space, () => {
  page.value = 1;
  close();
  message.value = '';
  load();
});
onMounted(load);
</script>
<template>
  <section class="access-panel">
    <header class="access-heading">
      <div>
        <h1>Administration</h1>
        <p>Gérez les utilisateurs et les accès de votre espace.</p>
      </div>
      <button
        v-if="activeSection === 'users'"
        class="primary"
        :disabled="busy"
        @click="adding = true"
      >
        <UserPlus :size="17" />Ajouter un utilisateur
      </button>
    </header>
    <nav class="access-navigation" aria-label="Rubriques de l’administration">
      <button
        v-for="section in sections"
        :key="section.key"
        :aria-current="activeSection === section.key ? 'page' : undefined"
        :disabled="busy"
        @click="
          activeSection = section.key;
          close();
          message = '';
          error = '';
        "
      >
        {{ section.label }}
      </button>
    </nav>
    <p v-if="error" role="alert" class="error">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <div class="access-toolbar">
      <label
        >Espace administré<select v-model="space" :disabled="busy">
          <option v-for="item in spaces" :key="item" :value="item">
            {{ item === 'assurance' ? 'Assurance' : 'Isolation' }}
          </option>
        </select></label
      >
      <form
        v-if="activeSection === 'users'"
        @submit.prevent="
          page = 1;
          load();
        "
      >
        <label
          >Rechercher un utilisateur<input
            v-model="search"
            placeholder="Identifiant ou e-mail" /></label
        ><button class="secondary" :disabled="busy">Rechercher</button>
      </form>
    </div>
    <template v-if="activeSection === 'users'">
      <div class="card table-scroll">
        <table>
          <thead>
            <tr>
              <th>Utilisateur</th>
              <th>Rôle dans cet espace</th>
              <th>État</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="row.id">
              <td>
                <strong>{{ row.username }}</strong
                ><small>{{ row.email || 'Aucun e-mail' }}</small
                ><small v-if="row.username === username">Votre compte</small>
              </td>
              <td>
                <select
                  v-model="row.role"
                  :disabled="busy || row.username === username"
                  :aria-label="'Rôle de ' + row.username"
                >
                  <option v-for="role in roles()" :key="role" :value="role">
                    {{ labels[role] }}
                  </option>
                </select>
                <label v-if="row.role === 'advisor'" class="access-quota"
                  >Prospects à fournir<input
                    v-model.number="row.prospect_quota"
                    type="number"
                    min="1"
                    max="100000"
                    inputmode="numeric"
                    :disabled="busy"
                    :aria-label="'Prospects à fournir pour ' + row.username"
                /></label>
              </td>
              <td>
                <span
                  :class="[
                    'access-status',
                    row.active && row.account_active ? 'enabled' : 'disabled',
                  ]"
                  >{{
                    !row.account_active ? 'Compte désactivé' : row.active ? 'Actif' : 'Suspendu'
                  }}</span
                >
              </td>
              <td>
                <div class="access-actions">
                  <button
                    class="secondary"
                    :disabled="busy || row.username === username"
                    @click="
                      update(
                        row,
                        row.role === 'advisor'
                          ? { role: row.role, prospect_quota: row.prospect_quota || null }
                          : { role: row.role },
                      )
                    "
                    :aria-label="'Enregistrer le rôle de ' + row.username"
                  >
                    <Save :size="16" />Enregistrer</button
                  ><button
                    class="secondary"
                    :disabled="busy || row.username === username"
                    @click="update(row, { active: !row.active })"
                  >
                    <Pause v-if="row.active" :size="16" /><Play v-else :size="16" />{{
                      row.active ? 'Suspendre' : 'Réactiver'
                    }}
                  </button>
                </div>
              </td>
            </tr>
            <tr v-if="!rows.length">
              <td colspan="4">{{ busy ? 'Chargement…' : 'Aucun utilisateur trouvé.' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="access-pagination">
        <span>{{ count }} utilisateur(s) · page {{ page }}</span
        ><button
          class="secondary"
          :disabled="busy || page === 1"
          @click="
            page--;
            load();
          "
        >
          <ChevronLeft :size="16" />Précédent</button
        ><button
          class="secondary"
          :disabled="busy || page * 25 >= count"
          @click="
            page++;
            load();
          "
        >
          Suivant<ChevronRight :size="16" />
        </button>
      </div>
      <p class="subtle">
        Votre propre accès est protégé. Après une suspension, un accès métier déjà délivré peut
        rester valable pendant deux minutes.
      </p>
      <section v-if="adding" class="card access-form" aria-label="Ajouter un utilisateur">
        <h2>Ajouter à {{ space === 'assurance' ? 'Assurance' : 'Isolation' }}</h2>
        <form @submit.prevent="create">
          <label
            >Type d’ajout<select
              v-model="form.existing"
              :disabled="busy"
              @change="
                form.password = '';
                form.email = '';
              "
            >
              <option :value="false">Créer un nouveau compte</option>
              <option :value="true">Associer un compte existant</option>
            </select></label
          ><label
            >Identifiant<input
              v-model="form.username"
              required
              maxlength="150"
              autocomplete="off" /></label
          ><template v-if="!form.existing"
            ><label
              >E-mail (facultatif)<input
                v-model="form.email"
                type="email"
                autocomplete="off" /></label
            ><label
              >Mot de passe initial (12 caractères minimum)<input
                v-model="form.password"
                type="password"
                minlength="12"
                maxlength="256"
                required
                autocomplete="new-password" /></label></template
          ><label
            >Rôle<select v-model="form.role">
              <option v-for="role in roles()" :key="role" :value="role">{{ labels[role] }}</option>
            </select></label
          ><label v-if="form.role === 'advisor'"
            >Nombre de prospects à fournir<input
              v-model="form.prospect_quota"
              type="number"
              min="1"
              max="100000"
              required
              inputmode="numeric"
          /></label>
          <p class="subtle">
            L’association d’un compte existant conserve ses autres accès et son mot de passe.
          </p>
          <div class="access-actions">
            <button class="primary" :disabled="busy">Ajouter</button
            ><button type="button" class="secondary" :disabled="busy" @click="close">
              Annuler
            </button>
          </div>
        </form>
      </section>
    </template>
    <div v-else class="access-section">
      <PortalAccessHistory
        v-if="activeSection === 'history'"
        :key="space"
        :space="space"
        :request="request"
      /><PortalPhoneExtensions
        v-else-if="activeSection === 'phone'"
        :key="'phone-' + space"
        :space="space"
        :request="request"
      /><PortalInvitations
        v-else-if="activeSection === 'invitations'"
        :key="space"
        :space="space"
        :request="request"
      />
    </div>
  </section>
</template>
<style scoped>
.access-quota {
  display: grid;
  gap: 4px;
  margin-top: 8px;
  font-size: 12px;
  color: #475467;
}
.access-quota input {
  max-width: 130px;
}
.access-panel {
  margin-top: 35px;
}
.access-toolbar,
.access-toolbar form,
.access-pagination,
.access-actions {
  display: flex;
  gap: 12px;
  align-items: end;
  flex-wrap: wrap;
}
.access-toolbar {
  justify-content: space-between;
  margin: 25px 0;
}
.access-panel select {
  padding: 12px;
  border: 1px solid #dedfce;
  border-radius: 10px;
  background: #fff;
  color: #303d20;
}
.access-panel small {
  display: block;
  color: #858b77;
  margin-top: 6px;
}
.access-panel td {
  padding: 18px;
}
.access-pagination {
  justify-content: end;
  align-items: center;
  margin: 20px 0;
}
.access-pagination span {
  margin-right: auto;
  color: #777f65;
}
.access-status {
  padding: 6px 10px;
  border-radius: 8px;
  font-size: 12px;
}
.enabled {
  background: #eaf1db;
  color: #49601b;
}
.disabled {
  background: #fbe9df;
  color: #99532d;
}
.access-form {
  padding: 28px;
  margin-top: 28px;
  max-width: 600px;
}
.access-form form {
  display: grid;
  gap: 18px;
}
.access-panel button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
@media (max-width: 650px) {
  .access-toolbar form {
    width: 100%;
  }
  .access-toolbar form label {
    flex: 1;
  }
}
</style>
<style scoped>
.access-panel {
  margin: 0;
  background: #fff;
  min-height: 70vh;
}
.access-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 24px;
}
.access-heading h1 {
  font-size: 22px;
  letter-spacing: -0.4px;
  margin: 0;
  color: #253347;
}
.access-heading p {
  font-size: 13px;
  color: #718096;
  margin: 8px 0 0;
}
.access-navigation {
  display: flex;
  gap: 24px;
  padding: 0 24px;
  border-bottom: 1px solid #dfe5ed;
  overflow-x: auto;
}
.access-navigation button {
  white-space: nowrap;
  border: 0;
  border-bottom: 3px solid transparent;
  background: none;
  color: #65758b;
  padding: 16px 0;
  font-size: 13px;
  cursor: pointer;
}
.access-navigation button[aria-current] {
  color: #187fc2;
  border-bottom-color: #187fc2;
  font-weight: 600;
}
.access-toolbar {
  margin: 0;
  padding: 22px 24px;
  background: #f2f6fa;
  border-bottom: 1px solid #e1e8ef;
  align-items: center;
}
.access-toolbar form {
  align-items: end;
}
.access-panel select {
  border-color: #dbe3ec;
  border-radius: 5px;
  color: #34445b;
  padding: 10px 12px;
}
.access-panel .table-scroll {
  border: 0;
  border-radius: 0;
  box-shadow: none;
  margin: 0;
}
.access-panel td {
  padding: 16px 24px;
}
.access-panel small {
  color: #738196;
}
.access-status {
  border-radius: 16px;
  white-space: nowrap;
}
.enabled {
  background: #e6f5ed;
  color: #24744c;
}
.disabled {
  background: #fff0e6;
  color: #a15b26;
}
.access-pagination {
  margin: 0;
  padding: 18px 24px;
  border-bottom: 1px solid #e5ebf1;
  font-size: 12px;
}
.access-panel > p {
  margin: 16px 24px;
  font-size: 12px;
}
.access-form {
  margin: 24px;
  max-width: 680px;
  border-color: #dbe3ec;
  border-radius: 8px;
}
.access-section {
  padding: 24px;
}
.access-actions {
  align-items: center;
  gap: 8px;
}
@media (max-width: 720px) {
  .access-heading {
    align-items: start;
    flex-direction: column;
    padding: 18px;
  }
  .access-navigation {
    padding: 0 18px;
    gap: 20px;
  }
  .access-toolbar,
  .access-section {
    padding: 18px;
  }
  .access-form {
    margin: 18px;
  }
  .access-panel td {
    padding: 12px;
  }
  .access-pagination {
    padding: 16px;
    flex-wrap: wrap;
  }
}
</style>
