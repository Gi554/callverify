<script setup lang="ts">
// Call guard rails: the hours when calls may be placed, and the numbers that must never be called.
import { ref, onMounted } from 'vue';
const props = defineProps<{
  space: string;
  request: (path: string, body?: any, method?: string) => Promise<any>;
}>();
const rules = ref<any>(null),
  list = ref<any[]>([]),
  count = ref(0),
  page = ref(1),
  search = ref(''),
  numbers = ref(''),
  reason = ref(''),
  busy = ref(false),
  error = ref(''),
  message = ref('');
const base = () => `workspaces/${props.space}/`;
async function loadRules() {
  rules.value = await props.request(base() + 'call-rules/');
}
async function loadList() {
  const data = await props.request(
    `${base()}call-exclusions/?page=${page.value}&search=${encodeURIComponent(search.value)}`,
  );
  list.value = data.results;
  count.value = data.count;
}
async function run(action: () => Promise<void>) {
  busy.value = true;
  error.value = message.value = '';
  try {
    await action();
  } catch (e: any) {
    error.value = e.message || 'Action impossible.';
  } finally {
    busy.value = false;
  }
}
const save = () =>
  run(async () => {
    const { allowed_now, message: _unused, ...body } = rules.value;
    void allowed_now;
    void _unused;
    rules.value = await props.request(base() + 'call-rules/', body, 'PATCH');
    message.value = 'Règles enregistrées.';
  });
const add = () =>
  run(async () => {
    const data = await props.request(base() + 'call-exclusions/', {
      numbers: numbers.value,
      reason: reason.value,
    });
    message.value =
      `${data.added} numéro(s) ajouté(s)` +
      (data.already_listed ? `, ${data.already_listed} déjà dans la liste` : '') +
      (data.invalid.length ? `. Numéros invalides ignorés : ${data.invalid.join(', ')}` : '.');
    numbers.value = reason.value = '';
    page.value = 1;
    await loadList();
  });
const remove = (row: any) =>
  run(async () => {
    if (!confirm('Retirer ' + row.number + ' de la liste d’exclusion ?')) return;
    await props.request(`${base()}call-exclusions/${row.id}/`, undefined, 'DELETE');
    await loadList();
  });
const find = () =>
  run(async () => {
    page.value = 1;
    await loadList();
  });
const turn = (step: number) =>
  run(async () => {
    page.value += step;
    await loadList();
  });
onMounted(() => run(async () => void (await Promise.all([loadRules(), loadList()]))));
</script>
<template>
  <section class="call-rules">
    <h2>Règles d’appel</h2>
    <p v-if="error" role="alert" class="rules-error">{{ error }}</p>
    <p v-if="message" role="status" class="rules-ok">{{ message }}</p>
    <form v-if="rules" class="rules-card" @submit.prevent="save">
      <h3>Heures d’appel autorisées</h3>
      <p class="rules-help">
        En dehors de ces heures, le CRM refuse tout appel, même lancé depuis une session d’appels.
        Maintenant :
        <strong>{{ rules.allowed_now ? 'appels autorisés' : 'appels interdits' }}</strong
        >.
      </p>
      <label class="rules-check"
        ><input v-model="rules.enforce_hours" type="checkbox" />Appliquer les heures d’appel</label
      >
      <div class="rules-grid">
        <label>Semaine : de <input v-model="rules.weekday_start" type="time" required /></label
        ><label>à <input v-model="rules.weekday_end" type="time" required /></label
        ><label>Week-end : de <input v-model="rules.weekend_start" type="time" required /></label
        ><label>à <input v-model="rules.weekend_end" type="time" required /></label>
      </div>
      <label
        >Fuseau horaire <input v-model="rules.timezone" placeholder="America/Montreal" required
      /></label>
      <button class="primary" :disabled="busy">Enregistrer les heures</button>
    </form>
    <section class="rules-card">
      <h3>Numéros à ne jamais appeler</h3>
      <p class="rules-help">
        Collez un ou plusieurs numéros (un par ligne ou séparés par une virgule). Un numéro de cette
        liste est refusé pour tous les setters, dans les deux espaces.
      </p>
      <form class="rules-add" @submit.prevent="add">
        <label
          >Numéros
          <textarea
            v-model="numbers"
            rows="4"
            placeholder="514 555 0101&#10;819 555 0102"
            required
          ></textarea>
        </label>
        <label
          >Motif (facultatif)
          <input v-model="reason" maxlength="200" placeholder="Demande du client" /></label
        ><button class="primary" :disabled="busy || !numbers.trim()">Ajouter à la liste</button>
      </form>
      <form class="rules-search" @submit.prevent="find">
        <input v-model="search" placeholder="Rechercher un numéro" aria-label="Rechercher" />
        <button class="secondary" :disabled="busy">Rechercher</button>
      </form>
      <p v-if="!list.length" class="rules-help">Aucun numéro dans la liste.</p>
      <ul v-else class="rules-list">
        <li v-for="row in list" :key="row.id">
          <strong>{{ row.number }}</strong>
          <span>{{ row.reason }}</span>
          <button class="secondary" :disabled="busy" @click="remove(row)">Retirer</button>
        </li>
      </ul>
      <div v-if="count > 25" class="rules-pages">
        <button class="secondary" :disabled="busy || page === 1" @click="turn(-1)">Précédent</button
        ><span>{{ count }} numéros · page {{ page }}</span
        ><button class="secondary" :disabled="busy || page * 25 >= count" @click="turn(1)">
          Suivant
        </button>
      </div>
    </section>
  </section>
</template>
<style scoped>
.call-rules {
  display: grid;
  gap: 16px;
}
.call-rules h2,
.call-rules h3 {
  margin: 0;
}
.rules-card {
  background: #fff;
  border: 1px solid #e3e8f1;
  border-radius: 14px;
  padding: 18px;
  display: grid;
  gap: 12px;
}
.rules-help {
  margin: 0;
  font-size: 13px;
  color: #5f6b80;
}
.rules-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}
.rules-card label {
  display: grid;
  gap: 4px;
  font-size: 12px;
  color: #5f6b80;
}
.rules-check {
  display: flex !important;
  align-items: center;
  gap: 8px !important;
  font-size: 14px !important;
}
.rules-add,
.rules-search {
  display: grid;
  gap: 10px;
}
.rules-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
}
.rules-list li {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
.rules-list li span {
  flex: 1 1 140px;
  color: #5f6b80;
  font-size: 13px;
}
.rules-pages {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
.rules-ok {
  margin: 0;
  color: #1c7a4a;
  font-size: 13px;
}
.rules-error {
  margin: 0;
  color: #b3261e;
  font-size: 13px;
}
</style>
