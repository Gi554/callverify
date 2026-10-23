<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { Plus, Trash2, Info } from 'lucide-vue-next';
import AssurancePipelineSettings from './AssurancePipelineSettings.vue';
import { keyFromLabel, uniqueKey } from './settings-key';
const props = defineProps<{
  request: (path: string, body?: any, method?: string) => Promise<any>;
}>();
const tab = ref<'pipeline' | 'fields'>('pipeline');
const fields = ref<any[]>([]),
  saved = ref(''),
  revision = ref(0),
  reason = ref(''),
  busy = ref(false),
  error = ref(''),
  message = ref('');
const types: Record<string, string> = {
  text: 'Texte',
  boolean: 'Case à cocher',
  date: 'Date',
  choice: 'Liste de choix',
};
const payload = () =>
  fields.value.map(({ key, label, type, required, active, advisor_visible, choicesText }) => ({
    key,
    label,
    type,
    required,
    active,
    advisor_visible,
    choices:
      type === 'choice'
        ? choicesText
            .split('\n')
            .map((v: string) => v.trim())
            .filter(Boolean)
        : [],
  }));
const dirty = computed(() => JSON.stringify(payload()) !== saved.value);
async function load() {
  busy.value = true;
  error.value = '';
  try {
    const result = await props.request('contact-fields/');
    fields.value = result.fields.map((row: any) => ({
      ...row,
      advisor_visible: row.advisor_visible === true,
      choicesText: row.choices.join('\n'),
      existing: true,
    }));
    revision.value = result.revision;
    saved.value = JSON.stringify(payload());
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
// New fields get their key from the label; existing keys, types and choices never change.
// The input event fires before v-model updates the label, hence the explicit value.
function relabel(field: any, label: string) {
  if (field.existing) return;
  const taken = fields.value.filter((other) => other !== field).map((other) => other.key);
  field.key = uniqueKey(keyFromLabel(label, 'champ'), taken);
}
function add() {
  fields.value.push({
    key: '',
    label: '',
    type: 'text',
    required: false,
    active: true,
    advisor_visible: false,
    choices: [],
    choicesText: '',
    existing: false,
  });
}
async function save() {
  busy.value = true;
  error.value = '';
  message.value = '';
  try {
    await props.request('contact-fields/', {
      revision: revision.value,
      reason: reason.value,
      fields: payload(),
    });
    reason.value = '';
    await load();
    message.value = 'Champs enregistrés.';
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
onMounted(load);
</script>
<template>
  <section class="business-settings">
    <div class="settings-tabs" role="tablist" aria-label="Paramètres métier">
      <button
        type="button"
        role="tab"
        :aria-selected="tab === 'pipeline'"
        :class="{ 'is-active': tab === 'pipeline' }"
        @click="tab = 'pipeline'"
      >
        Statuts du pipeline
      </button>
      <button
        type="button"
        role="tab"
        :aria-selected="tab === 'fields'"
        :class="{ 'is-active': tab === 'fields' }"
        @click="tab = 'fields'"
      >
        Champs personnalisés
      </button>
    </div>
    <AssurancePipelineSettings v-if="tab === 'pipeline'" :request="request" />
    <section v-else class="settings-block">
      <p class="settings-hint">
        Informations propres à votre activité, ajoutées à chaque fiche prospect. Un champ reste
        interne sauf s’il est rendu visible au conseiller.
      </p>
      <p v-if="error" role="alert" class="settings-error">{{ error }}</p>
      <p v-if="message" role="status" class="settings-message">{{ message }}</p>
      <form @submit.prevent="save">
        <ol class="settings-list">
          <li v-for="(field, index) in fields" :key="index" :class="{ inactive: !field.active }">
            <span class="position">{{ index + 1 }}</span>
            <div class="settings-main">
              <div class="settings-row">
                <input
                  v-model="field.label"
                  :aria-label="`Libellé du champ ${index + 1}`"
                  placeholder="Libellé du champ"
                  maxlength="100"
                  required
                  :disabled="busy"
                  @input="relabel(field, ($event.target as HTMLInputElement).value)"
                /><select
                  v-model="field.type"
                  :aria-label="`Type du champ ${index + 1}`"
                  :disabled="busy || field.existing"
                >
                  <option v-for="(label, value) in types" :key="value" :value="value">
                    {{ label }}
                  </option>
                </select>
              </div>
              <textarea
                v-if="field.type === 'choice'"
                v-model="field.choicesText"
                :aria-label="`Choix du champ ${index + 1}`"
                placeholder="Un choix par ligne"
                :readonly="field.existing"
                required
                :disabled="busy"
              ></textarea>
              <small class="settings-key">{{ field.key || 'clé générée depuis le libellé' }}</small>
              <div class="settings-toggles">
                <label class="switch"
                  ><input v-model="field.required" type="checkbox" :disabled="busy" /><span
                    >Obligatoire</span
                  ></label
                ><label class="switch"
                  ><input v-model="field.active" type="checkbox" :disabled="busy" /><span>{{
                    field.active ? 'Actif' : 'Archivé'
                  }}</span></label
                ><label class="switch"
                  ><input v-model="field.advisor_visible" type="checkbox" :disabled="busy" /><span
                    >Visible au conseiller</span
                  ></label
                >
              </div>
            </div>
            <div class="settings-order">
              <button
                v-if="!field.existing"
                type="button"
                class="icon"
                aria-label="Retirer ce nouveau champ"
                @click="fields.splice(index, 1)"
              >
                <Trash2 :size="15" />
              </button>
            </div>
          </li>
          <li v-if="!fields.length && !busy" class="settings-empty">
            Aucun champ personnalisé pour le moment.
          </li>
        </ol>
        <button
          type="button"
          class="secondary settings-add"
          :disabled="busy || fields.length >= 30"
          @click="add"
        >
          <Plus :size="15" />Ajouter un champ
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
      <details class="settings-notes">
        <summary><Info :size="15" />À savoir</summary>
        <p>
          « Visible au conseiller » publie le libellé et la valeur actuelle sur tous les dossiers
          auxquels il a accès ; il ne peut pas les modifier. Décocher ou archiver retire cette
          lecture pour les prochaines consultations.
        </p>
        <p>
          La clé, le type et les choix d’un champ existant sont conservés : archivez-le plutôt que
          de le recréer. Les obligations s’appliquent à l’enregistrement des champs métier, sans
          bloquer les imports bruts.
        </p>
      </details>
    </section>
  </section>
</template>
<style scoped>
.business-settings {
  display: grid;
  gap: 16px;
}
.settings-tabs {
  display: inline-flex;
  justify-self: start;
  padding: 3px;
  border-radius: 10px;
  background: #eef1f6;
}
.settings-tabs button {
  border: 0;
  border-radius: 8px;
  background: none;
  color: #5b6b82;
  padding: 9px 16px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.settings-tabs button.is-active {
  background: white;
  color: #1f2f45;
  box-shadow: 0 1px 4px #1f2f4518;
}
.business-settings :deep(.settings-block) {
  display: grid;
  gap: 12px;
}
.business-settings :deep(.settings-block form) {
  display: grid;
  gap: 12px;
}
.business-settings :deep(.settings-hint) {
  margin: 0;
  color: #6b7686;
  font-size: 13px;
}
.business-settings :deep(.settings-error) {
  color: #b42318;
}
.business-settings :deep(.settings-message) {
  color: #23784a;
}
.business-settings :deep(.settings-list) {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.business-settings :deep(.settings-list > li) {
  display: grid;
  grid-template-columns: 28px 1fr auto auto;
  align-items: start;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid #e3e7ee;
  border-radius: 12px;
  background: white;
}
.business-settings :deep(.settings-list > li.inactive) {
  background: #f8f9fb;
}
.business-settings :deep(.settings-list > li.inactive input:not([type='checkbox'])) {
  color: #6b7686;
}
.business-settings :deep(.position) {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #eef1f6;
  color: #5b6b82;
  font-size: 12px;
  font-weight: 700;
}
.business-settings :deep(.settings-main) {
  display: grid;
  gap: 6px;
  min-width: 0;
}
.business-settings :deep(.settings-row) {
  display: grid;
  grid-template-columns: 1fr 180px;
  gap: 8px;
}
.business-settings :deep(.settings-main input:not([type='checkbox'])),
.business-settings :deep(.settings-main select),
.business-settings :deep(.settings-main textarea),
.business-settings :deep(.settings-save input) {
  padding: 9px 10px;
  border: 1px solid #dfe4ec;
  border-radius: 8px;
  background: white;
}
.business-settings :deep(.settings-key) {
  color: #8a96a8;
  font-family: ui-monospace, monospace;
  font-size: 11px;
}
.business-settings :deep(.settings-toggles) {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 18px;
}
.business-settings :deep(.switch) {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #3d4b60;
  white-space: nowrap;
}
.business-settings :deep(.switch input) {
  appearance: none;
  position: relative;
  width: 34px;
  height: 20px;
  margin: 0;
  flex: none;
  min-width: 34px;
  min-height: 20px;
  max-height: none;
  padding: 0;
  border: 0;
  box-shadow: none;
  border-radius: 99px;
  background: #cfd6e0;
  cursor: pointer;
  transition: background 0.15s;
}
.business-settings :deep(.switch input::after) {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: white;
  transition: transform 0.15s;
}
.business-settings :deep(.switch input:checked) {
  background: #23784a;
}
.business-settings :deep(.switch input:checked::after) {
  transform: translateX(14px);
}
.business-settings :deep(.switch input:disabled) {
  opacity: 0.5;
  cursor: not-allowed;
}
.business-settings :deep(.settings-order) {
  display: flex;
  gap: 4px;
}
.business-settings :deep(button.icon) {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border: 1px solid #dfe4ec;
  border-radius: 8px;
  background: white;
  color: #5b6b82;
  cursor: pointer;
}
.business-settings :deep(button.icon:disabled) {
  opacity: 0.4;
  cursor: not-allowed;
}
.business-settings :deep(.settings-add) {
  display: inline-flex;
  align-items: center;
  justify-self: start;
  gap: 6px;
}
.business-settings :deep(.settings-empty) {
  display: block;
  color: #6b7686;
  text-align: center;
}
.business-settings :deep(.settings-save) {
  position: sticky;
  bottom: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border: 1px solid #e3e7ee;
  border-radius: 12px;
  background: #f8f9fb;
  color: #6b7686;
  font-size: 13px;
}
.business-settings :deep(.settings-save.dirty) {
  border-color: #f4c38b;
  background: #fffaf3;
  color: #8a4b0c;
}
.business-settings :deep(.settings-save input) {
  flex: 1 1 260px;
}
.settings-notes {
  padding: 12px 16px;
  border-radius: 12px;
  background: #f6f8fb;
  color: #5b6b82;
  font-size: 13px;
}
.settings-notes summary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-weight: 600;
  color: #1f2f45;
}
@media (max-width: 700px) {
  .business-settings :deep(.settings-list > li) {
    grid-template-columns: 28px 1fr;
  }
  .business-settings :deep(.settings-row) {
    grid-template-columns: 1fr;
  }
}
</style>
