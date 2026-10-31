<script setup lang="ts">
import { onMounted, ref } from 'vue';
import SidePanel from './SidePanel.vue';
const props = defineProps<{ request: (path: string, body?: any) => Promise<any> }>();
const value = ref<any>(null),
  draft = ref<any>(null),
  reason = ref(''),
  busy = ref(false),
  error = ref('');
async function load() {
  try {
    value.value = await props.request('isolation-reminder-policy/');
  } catch (e: any) {
    error.value = e.message;
  }
}
function edit() {
  draft.value = JSON.parse(JSON.stringify(value.value));
  reason.value = '';
}
function close() {
  if (
    !busy.value &&
    ((!reason.value && JSON.stringify(draft.value) === JSON.stringify(value.value)) ||
      window.confirm('Abandonner les modifications de relance ?'))
  )
    draft.value = null;
}
async function save() {
  busy.value = true;
  error.value = '';
  try {
    value.value = await props.request('isolation-reminder-policy/', {
      ...draft.value,
      reason: reason.value,
    });
    draft.value = null;
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
    <h3>Relance du rÃ©sultat de visite</h3>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="value">
      {{
        value.enabled
          ? `Un rappel aprÃ¨s ${value.delay_hours} h sans rÃ©sultat complet, aprÃ¨s la fin de visite.`
          : 'Relance dÃ©sactivÃ©e.'
      }}
    </p>
    <button class="secondary" :disabled="busy || !value" @click="edit">
      RÃ©gler la relance client</button
    ><SidePanel
      :open="!!draft"
      title="Relance du rÃ©sultat de visite"
      :close-disabled="busy"
      @request-close="close"
      ><form v-if="draft" @submit.prevent="save">
        <p v-if="error" role="alert">{{ error }}</p>
        <label><input v-model="draft.enabled" type="checkbox" />Activer les relances</label
        ><label
          >DÃ©lai aprÃ¨s la fin de visite (heures)<input
            v-model.number="draft.delay_hours"
            type="number"
            min="1"
            max="720"
            required /></label
        ><label
          >Motif obligatoire<textarea v-model="reason" required maxlength="1000"></textarea>
        </label>
        <p>
          Une seule relance par occurrence. Aucune absence ni vente nâ€™est dÃ©duite dâ€™un
          silence.
        </p>
        <button class="primary" :disabled="busy || !reason.trim()">Enregistrer</button>
      </form></SidePanel
    >
  </section>
</template>
<style scoped>
section,
form {
  display: grid;
  gap: 14px;
}
label {
  display: grid;
  gap: 6px;
}
[role='alert'] {
  color: #b42318;
}
p {
  font-size: 13px;
  color: #68758a;
  line-height: 1.6;
}
</style>
