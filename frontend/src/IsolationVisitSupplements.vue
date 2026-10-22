<script setup lang="ts">
import { ref, onMounted } from 'vue';
const props = defineProps<{
  visitId: number;
  role: string;
  request: (path: string, body?: any, method?: string) => Promise<any>;
}>();
const rows = ref<any[]>([]),
  page = ref(1),
  count = ref(0),
  note = ref(''),
  busy = ref(false),
  error = ref('');
let requestId = crypto.randomUUID();
function changed() {
  requestId = crypto.randomUUID();
}
async function load() {
  busy.value = true;
  error.value = '';
  try {
    const data = await props.request(`visits/${props.visitId}/supplements/?page=${page.value}`);
    rows.value = data.results;
    count.value = data.count;
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function save() {
  busy.value = true;
  error.value = '';
  try {
    await props.request(`visits/${props.visitId}/supplements/`, {
      request_id: requestId,
      note: note.value,
    });
    note.value = '';
    requestId = crypto.randomUUID();
    page.value = 1;
    await load();
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
onMounted(load);
</script>
<template>
  <section>
    <h4>Compléments au résultat</h4>
    <p>
      Le résultat initial reste conservé. Chaque complément ajoute une précision distincte à
      l’historique.
    </p>
    <p v-if="error" role="alert">{{ error }}</p>
    <form v-if="role === 'client'" @submit.prevent="save">
      <label
        >Ajouter une précision<textarea
          v-model="note"
          maxlength="3000"
          required
          :disabled="busy"
          @input="changed"
        ></textarea></label
      ><button class="primary" :disabled="busy">Enregistrer le complément</button>
    </form>
    <article v-for="row in rows" :key="row.id">
      <small
        >{{ new Date(row.created_at).toLocaleString('fr-FR') }} · client
        {{ row.author_client_id }}</small
      >
      <p style="white-space: pre-wrap">{{ row.note }}</p>
    </article>
    <p>{{ count }} complément(s) · page {{ page }}</p>
    <button
      class="secondary"
      :disabled="busy || page === 1"
      @click="
        page--;
        load();
      "
    >
      Précédent</button
    ><button
      class="secondary"
      :disabled="busy || page * 25 >= count"
      @click="
        page++;
        load();
      "
    >
      Suivant</button
    ><button class="secondary" :disabled="busy" @click="load">Actualiser les compléments</button>
  </section>
</template>
