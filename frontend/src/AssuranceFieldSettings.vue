<script setup lang="ts">
import { ref, onMounted } from 'vue';
import AssurancePipelineSettings from './AssurancePipelineSettings.vue';
const props = defineProps<{
  request: (path: string, body?: any, method?: string) => Promise<any>;
}>();
const fields = ref<any[]>([]),
  revision = ref(0),
  reason = ref(''),
  busy = ref(false),
  error = ref(''),
  message = ref('');
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
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
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
      fields: fields.value.map(
        ({ key, label, type, required, active, advisor_visible, choicesText }) => ({
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
        }),
      ),
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
  <AssurancePipelineSettings :request="request" />
  <section>
    <h3>Champs personnalisables Assurance</h3>
    <p>
      Chaque champ reste interne par défaut. Cocher « Visible au conseiller » publie son libellé et
      sa valeur actuelle sur tous les dossiers auxquels le conseiller a accès ; décocher ou archiver
      retire cette lecture pour les prochaines requêtes. Le conseiller ne peut pas modifier ces
      valeurs. Une clé existante, son type et ses choix sont conservés ; désactivez le champ pour
      l’archiver. Les obligations s’appliquent à l’enregistrement des champs métier, sans bloquer
      les imports bruts.
    </p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <form @submit.prevent="save">
      <fieldset v-for="(field, index) in fields" :key="index">
        <legend>Champ {{ index + 1 }}</legend>
        <label
          >Clé (lettres minuscules, chiffres, underscore)<input
            v-model="field.key"
            :readonly="field.existing"
            pattern="[a-z][a-z0-9_]{0,39}"
            required
            maxlength="40" /></label
        ><label>Libellé<input v-model="field.label" required maxlength="100" /></label
        ><label
          >Type<select v-model="field.type" :disabled="field.existing">
            <option value="text">Texte</option>
            <option value="boolean">Case à cocher</option>
            <option value="date">Date</option>
            <option value="choice">Liste de choix</option>
          </select></label
        ><label v-if="field.type === 'choice'"
          >Un choix par ligne<textarea
            v-model="field.choicesText"
            :readonly="field.existing"
            required
          ></textarea></label
        ><label
          ><input v-model="field.required" type="checkbox" />Obligatoire lors de la saisie
          métier</label
        ><label><input v-model="field.active" type="checkbox" />Actif</label
        ><label
          ><input v-model="field.advisor_visible" type="checkbox" />Visible au conseiller sur ses
          dossiers autorisés</label
        ><button
          v-if="!field.existing"
          type="button"
          class="secondary"
          @click="fields.splice(index, 1)"
        >
          Retirer ce nouveau champ
        </button>
      </fieldset>
      <button type="button" class="secondary" :disabled="busy || fields.length >= 30" @click="add">
        Ajouter un champ</button
      ><label
        >Motif de modification<textarea
          v-model="reason"
          required
          maxlength="1000"
        ></textarea></label
      ><button class="primary" :disabled="busy">Enregistrer la configuration</button
      ><button type="button" class="secondary" :disabled="busy" @click="load">Recharger</button>
    </form>
  </section>
</template>
<style scoped>
fieldset {
  display: grid;
  gap: 12px;
  margin: 20px 0;
  padding: 18px;
  border: 1px solid #dedfce;
}
select,
textarea {
  padding: 12px;
  border: 1px solid #dedfce;
  border-radius: 8px;
}
input[type='checkbox'] {
  width: auto;
}
form {
  display: grid;
  gap: 16px;
}
</style>
