<script setup lang="ts">
import { ref, onMounted } from 'vue';
import PortalPhoneCdr from './PortalPhoneCdr.vue';
const props = defineProps<{
  space: string;
  request: (path: string, body?: any, method?: string) => Promise<any>;
}>();
const rows = ref<any[]>([]),
  page = ref(1),
  count = ref(0),
  busy = ref(false),
  error = ref(''),
  message = ref('');
const endpoint = () => `workspaces/${props.space}/phone-extensions/`;
async function load() {
  busy.value = true;
  error.value = '';
  rows.value = [];
  try {
    const data = await props.request(endpoint() + `?page=${page.value}`);
    rows.value = data.results.map((row: any) => ({ ...row, reason: '' }));
    count.value = data.count;
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function save(row: any, remove = false) {
  busy.value = true;
  error.value = '';
  try {
    await props.request(endpoint(), {
      membership_id: row.membership_id,
      extension: row.extension || undefined,
      ...(row.revision === null ? {} : { revision: row.revision }),
      remove,
      reason: row.reason,
    });
    message.value = 'Association locale enregistrée. Aucun appel lancé.';
    await load();
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
const directory = ref<any[]>([]),
  directoryError = ref(''),
  checked = ref(''),
  directoryPage = ref(1);
async function inspectDirectory() {
  busy.value = true;
  directoryError.value = '';
  directory.value = [];
  checked.value = '';
  try {
    const result = await props.request('phone-directory/', {});
    directory.value = result.results;
    checked.value = result.checked_at;
    directoryPage.value = 1;
  } catch (e: any) {
    directoryError.value = e.message;
  } finally {
    busy.value = false;
  }
}
const observation = ref<any>(null),
  statusError = ref('');
async function inspectStatus(row: any) {
  busy.value = true;
  statusError.value = '';
  observation.value = null;
  try {
    observation.value = await props.request(endpoint() + `${row.membership_id}/status/`, {});
  } catch (e: any) {
    statusError.value = e.message;
  } finally {
    busy.value = false;
  }
}
onMounted(load);
</script>
<template>
  <section>
    <h3>Postes Phonetico — association manuelle</h3>
    <p>
      Association locale uniquement, aucun appel. La consultation facultative de l’annuaire
      ci-dessous utilise exclusivement la fonction 343. Un poste par compte, unique sur ce
      déploiement. Vérifiez le numéro dans votre PBX. Pour un setter ou administrateur actif dans
      les deux espaces, la modification exige les droits administrateur dans les deux.
    </p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <article v-for="row in rows" :key="row.membership_id">
      <form @submit.prevent="save(row)">
        <strong>{{ row.username }}</strong>
        <p>
          {{
            row.eligible
              ? 'Setter ou administrateur actif'
              : 'Accès ou compte suspendu : retrait possible uniquement'
          }}
        </p>
        <label
          >Poste<input
            v-model="row.extension"
            pattern="[0-9]{1,10}"
            maxlength="10"
            :disabled="busy || !row.eligible" /></label
        ><label
          >Motif<input v-model="row.reason" required maxlength="1000" :disabled="busy" /></label
        ><button class="secondary" :disabled="busy || !row.eligible || !row.extension">
          Enregistrer</button
        ><button
          v-if="row.revision !== null"
          type="button"
          class="secondary"
          :disabled="busy || !row.reason.trim()"
          @click="save(row, true)"
        >
          Retirer l’association
        </button>
      </form>
      <button
        v-if="row.extension"
        class="secondary"
        :disabled="busy || !row.eligible"
        @click="inspectStatus(row)"
      >
        Consulter l’état observé du poste (lecture seule)
      </button>
    </article>
    <p v-if="!rows.length">Aucun setter visible.</p>
    <button
      class="secondary"
      :disabled="busy || page === 1"
      @click="
        page--;
        load();
      "
    >
      Précédent
    </button>
    Page {{ page }}
    <button
      class="secondary"
      :disabled="busy || page * 25 >= count"
      @click="
        page++;
        load();
      "
    >
      Suivant</button
    ><button class="secondary" :disabled="busy" @click="load">Actualiser</button>
    <section>
      <h4>État du poste — observation manuelle</h4>
      <p>
        Lecture 244 uniquement, réservée aux administrateurs des deux espaces. États confirmés : R =
        sonnerie, C = en communication, H = en attente ; aucune preuve de disponibilité ou de
        validité d’un numéro. Aucune action sur les appels existants.
      </p>
      <p v-if="statusError" role="alert">{{ statusError }}</p>
      <p v-if="observation">
        Poste {{ observation.extension }} ·
        {{ new Date(observation.checked_at).toLocaleString('fr-FR') }} ·
        {{ observation.observations }} observation(s) · code(s)
        {{
          observation.states?.map((item: any) => item.code + ' : ' + item.label).join(', ') ||
          observation.codes.join(', ') ||
          'aucun'
        }}
        · conclusion : Indéterminé. Une absence d’observation ne signifie pas que le poste est
        libre.
      </p>
    </section>
    <section>
      <h4>Consulter les postes NEWT (lecture seule)</h4>
      <p>
        Réservé aux administrateurs des deux espaces, car l’annuaire PBX est global. Aucun
        changement de compte, d’association ou de poste. La configuration serveur doit être activée
        explicitement. Le nom reçu du PBX est indicatif ; il ne prouve pas l’identité d’un
        utilisateur.
      </p>
      <button class="secondary" :disabled="busy" @click="inspectDirectory">
        Consulter l’annuaire NEWT
      </button>
      <p v-if="directoryError" role="alert">{{ directoryError }}</p>
      <p v-if="checked">
        {{ directory.length }} poste(s) · consulté le
        {{ new Date(checked).toLocaleString('fr-FR') }}
      </p>
      <p
        v-for="item in directory.slice((directoryPage - 1) * 25, directoryPage * 25)"
        :key="item.extension"
      >
        {{ item.extension }} · {{ item.name || 'Sans nom' }}
      </p>
      <template v-if="directory.length"
        ><button class="secondary" :disabled="busy || directoryPage === 1" @click="directoryPage--">
          Précédent
        </button>
        Page {{ directoryPage }}
        <button
          class="secondary"
          :disabled="busy || directoryPage * 25 >= directory.length"
          @click="directoryPage++"
        >
          Suivant
        </button></template
      >
    </section>
    <PortalPhoneCdr :request="request" />
  </section>
</template>
