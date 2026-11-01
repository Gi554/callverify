<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';
import { Bell, CheckCircle2, AlertTriangle } from 'lucide-vue-next';
import IsolationPageHeader from './IsolationPageHeader.vue';
import SidePanel from './SidePanel.vue';
const props = defineProps<{
  workspace: string;
  request: (path: string, body?: any) => Promise<any>;
}>();
const data = ref<any>(null),
  kind = ref('missing_results'),
  page = ref(1),
  busy = ref(false),
  error = ref(''),
  selected = ref<any>(null),
  note = ref('');
let version = 0;
const date = (s: string) =>
  new Intl.DateTimeFormat('fr-CA', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'America/Toronto',
  }).format(new Date(s));
async function load() {
  const current = ++version;
  busy.value = true;
  error.value = '';
  try {
    const value = await props.request(
      'admin-alerts/?' + new URLSearchParams({ kind: kind.value, page: String(page.value) }),
    );
    if (current === version) data.value = value;
  } catch (e: any) {
    if (current === version) {
      data.value = null;
      error.value = e.message || 'Alertes indisponibles.';
    }
  } finally {
    if (current === version) busy.value = false;
  }
}
function choose(value: string) {
  kind.value = value;
  page.value = 1;
  load();
}
function open(row: any) {
  selected.value = row;
  note.value = '';
}
async function acknowledge() {
  busy.value = true;
  error.value = '';
  try {
    await props.request('admin-alerts/', {
      kind: selected.value.kind,
      id: selected.value.id,
      signature: selected.value.signature,
      note: note.value,
    });
    selected.value = null;
    await load();
  } catch (e: any) {
    error.value = e.message || 'Enregistrement impossible.';
  } finally {
    busy.value = false;
  }
}
onMounted(load);
onBeforeUnmount(() => version++);
</script>
<template>
  <div class="iso-page admin-alerts">
    <IsolationPageHeader
      title="Centre d’alertes"
      subtitle="Les points à suivre, les échéances et les anomalies potentielles de votre espace."
      :eyebrow="'ADMINISTRATION · ' + workspace.toUpperCase()"
      :busy="busy"
      @refresh="load"
    />
    <p v-if="error" role="alert" class="error">{{ error }}</p>
    <template v-if="data">
      <div class="alert-kinds">
        <button
          v-for="item in data.kinds"
          :key="item.kind"
          :class="['alert-kind', { active: kind === item.kind }]"
          :disabled="busy"
          :aria-pressed="kind === item.kind"
          @click="choose(item.kind)"
        >
          <Bell :size="17" /><span>{{ item.label }}</span
          ><strong>{{ item.count }}</strong>
        </button>
      </div>
      <section class="iso-panel">
        <header class="iso-panel-heading">
          <div>
            <h2>
              <AlertTriangle :size="19" />{{ data.kinds.find((k: any) => k.kind === kind)?.label }}
            </h2>
            <p>Contrôlé le {{ date(data.checked_at) }} · Heure du Québec</p>
          </div>
        </header>
        <p class="alert-explanation">
          Une prise en charge conserve l’alerte tant que sa cause existe. Si le dossier change, la
          nouvelle version demande une nouvelle vérification.
        </p>
        <article v-for="row in data.results" :key="row.signature" class="alert-row">
          <div>
            <strong>{{ row.title }}</strong>
            <p>
              Référence #{{ row.reference
              }}<span v-if="row.starts_at"> · {{ date(row.starts_at) }}</span
              ><span v-if="row.due_at"> · Échéance : {{ date(row.due_at) }}</span>
            </p>
            <small v-if="row.review"
              ><CheckCircle2 :size="13" />Prise en charge par le compte #{{
                row.review.actor_id
              }}
              le {{ date(row.review.created_at) }}</small
            ><small v-else>À examiner</small>
          </div>
          <button class="secondary" :disabled="busy" @click="open(row)">Consulter</button>
        </article>
        <p v-if="!data.results.length">Aucun élément actif dans cette catégorie.</p>
        <footer class="iso-pagination">
          <span>{{ data.count }} élément(s) · Page {{ page }}</span
          ><button
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
            :disabled="busy || page * 25 >= data.count"
            @click="
              page++;
              load();
            "
          >
            Suivant
          </button>
        </footer>
      </section></template
    >
    <SidePanel
      :open="!!selected"
      title="Examiner l’alerte"
      :eyebrow="'ALERTES · ' + workspace.toUpperCase()"
      :close-disabled="busy"
      @request-close="selected = null"
    >
      <template v-if="selected"
        ><h3>{{ selected.title }}</h3>
        <p>Référence #{{ selected.reference }}</p>
        <dl class="alert-details">
          <template v-for="(value, key) in selected.details" :key="key"
            ><dt>{{ key }}</dt>
            <dd>{{ typeof value === 'boolean' ? (value ? 'Oui' : 'Non') : value }}</dd></template
          >
        </dl>
        <p v-if="error" role="alert" class="error">{{ error }}</p>
        <section v-if="selected.review" class="iso-panel">
          <h3>Prise en charge enregistrée</h3>
          <p>Compte #{{ selected.review.actor_id }} · {{ date(selected.review.created_at) }}</p>
          <p>{{ selected.review.note }}</p>
        </section>
        <form v-else class="iso-panel" @submit.prevent="acknowledge">
          <label
            >Note de prise en charge<textarea
              v-model="note"
              required
              maxlength="1000"
              rows="4"
              :disabled="busy"
            />
          </label>
          <p>
            Cette action ne modifie ni le rendez-vous, ni la tâche, ni le paiement. Corrigez ensuite
            le dossier concerné dans son module habituel.
          </p>
          <button class="primary" :disabled="busy || !note.trim()">
            Marquer comme pris en charge
          </button>
        </form>
      </template></SidePanel
    >
  </div>
</template>
<style scoped>
.alert-kinds {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.alert-kind {
  display: flex;
  align-items: center;
  gap: 12px;
  border: 1px solid #dce4f2;
  background: #fff;
  border-radius: 16px;
  padding: 18px;
  text-align: left;
  color: #415575;
  transition:
    background 0.15s,
    border-color 0.15s;
}
.alert-kind span {
  flex: 1;
  font-size: 12px;
}
.alert-kind strong {
  font-size: 24px;
  color: #173454;
}
.alert-kind.active {
  background: #eef1ff;
  border-color: #8571ef;
}
.alert-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 18px 0;
  border-bottom: 1px solid #e5eaf3;
}
.alert-row p,
.alert-row small,
.alert-explanation {
  font-size: 12px;
  color: #65758e;
}
.alert-row small {
  display: flex;
  gap: 6px;
  align-items: center;
}
textarea {
  display: block;
  width: 100%;
  margin-top: 10px;
}
.alert-details {
  background: #f4f6fc;
  border-radius: 12px;
  padding: 16px;
  font-size: 12px;
  display: grid;
  grid-template-columns: 1fr;
  overflow-wrap: anywhere;
}
@media (max-width: 900px) {
  .alert-kinds {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 560px) {
  .alert-kinds {
    grid-template-columns: 1fr;
  }
  .alert-row {
    align-items: flex-start;
    flex-direction: column;
  }
  .alert-row button {
    width: 100%;
  }
}
</style>
