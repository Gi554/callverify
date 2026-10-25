<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
const props = defineProps<{
  request: (path: string, body?: any, method?: string) => Promise<any>;
  portal: (path: string, body?: any) => Promise<any>;
}>();
const emit = defineEmits<{ changed: [] }>();
type Person = { id: number; name: string };
type Setter = { id: number; name: string; assigned: number };
type Source = { id: number; filename: string; available: number };
const available = ref(0),
  setters = ref<Setter[]>([]),
  people = ref<Person[]>([]),
  sources = ref<Source[]>([]),
  setterId = ref(''),
  sourceId = ref(''),
  count = ref(100),
  busy = ref(false),
  error = ref(''),
  notice = ref('');
let requestId = crypto.randomUUID();
const free = computed(() => {
  const source = sources.value.find((row) => String(row.id) === sourceId.value);
  return source ? source.available : available.value;
});
const canGive = computed(
  () => !busy.value && !!setterId.value && count.value >= 1 && free.value > 0,
);
async function load() {
  error.value = '';
  try {
    const data = await props.request('lots/');
    available.value = data.available;
    setters.value = data.setters;
    sources.value = data.imports;
    const found: Person[] = [];
    for (let page = 1; page <= 8; page++) {
      const part = await props.portal(`assurance/participants/?role=setter&page=${page}`);
      found.push(...part.results);
      if (!part.next) break;
    }
    people.value = found;
    if (!setterId.value && found.length) setterId.value = String(found[0].id);
  } catch (e: any) {
    error.value = e.message || 'Impossible de charger les lots.';
  }
}
async function give() {
  if (!canGive.value) return;
  busy.value = true;
  error.value = notice.value = '';
  try {
    const attested = await props.portal('assurance/lot-proof/', {
      setter_id: Number(setterId.value),
    });
    const body: any = {
      request_id: requestId,
      proof: attested.proof,
      count: Math.floor(count.value),
    };
    if (sourceId.value) body.import_id = Number(sourceId.value);
    const data = await props.request('lots/', body);
    requestId = crypto.randomUUID();
    notice.value = data.assigned + ' prospect(s) attribué(s).';
    emit('changed');
    await load();
  } catch (e: any) {
    error.value = e.message || 'Attribution impossible.';
  } finally {
    busy.value = false;
  }
}
const assigned = (id: number) => setters.value.find((row) => row.id === id);
async function takeBack(setter: Person) {
  if (busy.value) return;
  if (!confirm('Reprendre les prospects non travaillés de ' + setter.name + ' ?')) return;
  busy.value = true;
  error.value = notice.value = '';
  try {
    const data = await props.request('lots/release/', {
      request_id: crypto.randomUUID(),
      setter_id: setter.id,
    });
    notice.value = data.released + ' prospect(s) repris.';
    emit('changed');
    await load();
  } catch (e: any) {
    error.value = e.message || 'Reprise impossible.';
  } finally {
    busy.value = false;
  }
}
onMounted(load);
</script>
<template>
  <section class="lots-panel" aria-label="Lots de prospects">
    <h2>Attribuer des prospects aux setters</h2>
    <p class="lots-help">
      Choisissez un setter et le nombre de prospects à lui donner : les premiers prospects non
      attribués lui sont confiés. Dès le premier lot attribué, chaque setter ne voit plus que les
      prospects de son lot. <strong>{{ available }}</strong> prospect(s) non attribué(s) et à
      traiter.
    </p>
    <p v-if="!people.length && !error" class="lots-help">Aucun setter Assurance actif.</p>
    <ul v-if="people.length" class="lots-setters">
      <li v-for="person in people" :key="person.id">
        <span>{{ person.name }}</span>
        <span class="lots-count">{{ assigned(person.id)?.assigned || 0 }} en cours</span>
        <button
          class="secondary"
          :disabled="busy || !assigned(person.id)"
          @click="takeBack(person)"
        >
          Reprendre
        </button>
      </li>
    </ul>
    <form v-if="people.length" class="lots-form" @submit.prevent="give">
      <label
        >Setter
        <select v-model="setterId">
          <option v-for="person in people" :key="person.id" :value="String(person.id)">
            {{ person.name }}
          </option>
        </select></label
      >
      <label
        >Nombre de prospects (les premiers)
        <input v-model.number="count" type="number" min="1" max="1000" inputmode="numeric"
      /></label>
      <label
        >Provenance
        <select v-model="sourceId">
          <option value="">Tous les imports</option>
          <option v-for="source in sources" :key="source.id" :value="String(source.id)">
            {{ source.filename }} ({{ source.available }})
          </option>
        </select></label
      >
      <button class="primary" type="submit" :disabled="!canGive">Attribuer le lot</button>
    </form>
    <p v-if="notice" class="lots-notice" role="status">{{ notice }}</p>
    <p v-if="error" class="lots-error" role="alert">{{ error }}</p>
  </section>
</template>
<style scoped>
.lots-panel {
  background: #fff;
  border: 1px solid #e3e8f1;
  border-radius: 14px;
  padding: 18px;
  margin-bottom: 18px;
  display: grid;
  gap: 12px;
}
.lots-panel h2 {
  margin: 0;
  font-size: 16px;
}
.lots-help {
  margin: 0;
  font-size: 13px;
  color: #5f6b80;
}
.lots-setters {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
}
.lots-setters li {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.lots-setters li > span:first-child {
  flex: 1 1 140px;
  font-weight: 600;
}
.lots-count {
  font-size: 13px;
  color: #5f6b80;
}
.lots-form {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px;
}
.lots-form label {
  display: grid;
  gap: 4px;
  font-size: 12px;
  color: #5f6b80;
  flex: 1 1 160px;
}
.lots-notice {
  margin: 0;
  color: #1c7a4a;
  font-size: 13px;
}
.lots-error {
  margin: 0;
  color: #b3261e;
  font-size: 13px;
}
</style>
