<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { ArrowUp, ArrowDown, Plus, Trash2 } from 'lucide-vue-next';
import { keyFromLabel, uniqueKey } from './settings-key';
const props = defineProps<{
  request: (path: string, body?: any, method?: string) => Promise<any>;
}>();
const stages = ref<any[]>([]),
  saved = ref(''),
  revision = ref(0),
  reason = ref(''),
  busy = ref(false),
  error = ref(''),
  message = ref('');
const payload = () => stages.value.map(({ key, label, active }) => ({ key, label, active }));
const dirty = computed(() => JSON.stringify(payload()) !== saved.value);
async function load() {
  busy.value = true;
  error.value = '';
  try {
    const data = await props.request('pipeline/');
    stages.value = data.stages.map((s: any) => ({ ...s, existing: true }));
    revision.value = data.revision;
    saved.value = JSON.stringify(payload());
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
// New statuses get their stable key from the label; existing keys never change.
// The input event fires before v-model updates the label, hence the explicit value.
function relabel(stage: any, label: string) {
  if (stage.existing) return;
  const taken = stages.value.filter((other) => other !== stage).map((other) => other.key);
  stage.key = uniqueKey(keyFromLabel(label, 'statut'), taken);
}
function add() {
  stages.value.push({ key: '', label: '', active: true, existing: false });
}
async function save() {
  busy.value = true;
  error.value = '';
  message.value = '';
  try {
    await props.request('pipeline/', {
      revision: revision.value,
      reason: reason.value,
      stages: payload(),
    });
    reason.value = '';
    await load();
    message.value = 'Pipeline enregistré.';
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
function move(index: number, delta: number) {
  const row = stages.value.splice(index, 1)[0];
  stages.value.splice(index + delta, 0, row);
}
onMounted(load);
</script>
<template>
  <section class="settings-block">
    <p class="settings-hint">
      L’ordre définit les colonnes du tableau des prospects. Archiver un statut conserve les fiches
      et leur historique ; le statut initial des imports reste actif.
    </p>
    <p v-if="error" role="alert" class="settings-error">{{ error }}</p>
    <p v-if="message" role="status" class="settings-message">{{ message }}</p>
    <form @submit.prevent="save">
      <ol class="settings-list">
        <li v-for="(stage, index) in stages" :key="index" :class="{ inactive: !stage.active }">
          <span class="position">{{ index + 1 }}</span>
          <div class="settings-main">
            <input
              v-model="stage.label"
              :aria-label="`Libellé du statut ${index + 1}`"
              placeholder="Libellé du statut"
              maxlength="100"
              required
              :disabled="busy"
              @input="relabel(stage, ($event.target as HTMLInputElement).value)"
            />
            <small class="settings-key">{{ stage.key || 'clé générée depuis le libellé' }}</small>
          </div>
          <label
            class="switch"
            :title="stage.key === 'to_contact' ? 'Statut initial des imports' : ''"
            ><input
              v-model="stage.active"
              type="checkbox"
              :disabled="busy || stage.key === 'to_contact'"
            /><span>{{ stage.active ? 'Actif' : 'Archivé' }}</span></label
          >
          <div class="settings-order">
            <button
              type="button"
              class="icon"
              :aria-label="`Monter ${stage.label || 'ce statut'}`"
              :disabled="busy || index === 0"
              @click="move(index, -1)"
            >
              <ArrowUp :size="15" /></button
            ><button
              type="button"
              class="icon"
              :aria-label="`Descendre ${stage.label || 'ce statut'}`"
              :disabled="busy || index === stages.length - 1"
              @click="move(index, 1)"
            >
              <ArrowDown :size="15" /></button
            ><button
              v-if="!stage.existing"
              type="button"
              class="icon"
              aria-label="Retirer ce nouveau statut"
              @click="stages.splice(index, 1)"
            >
              <Trash2 :size="15" />
            </button>
          </div>
        </li>
      </ol>
      <button
        type="button"
        class="secondary settings-add"
        :disabled="busy || stages.length >= 30"
        @click="add"
      >
        <Plus :size="15" />Ajouter un statut
      </button>
      <footer class="settings-save" :class="{ dirty }">
        <span>{{ dirty ? 'Modifications non enregistrées' : 'Aucune modification' }}</span>
        <template v-if="dirty"
          ><input
            v-model="reason"
            aria-label="Motif de la modification"
            placeholder="Motif de la modification (obligatoire)"
            maxlength="1000"
            required
            :disabled="busy"
          /><button type="button" class="secondary" :disabled="busy" @click="load">Annuler</button
          ><button class="primary" :disabled="busy">Enregistrer</button></template
        >
      </footer>
    </form>
  </section>
</template>
