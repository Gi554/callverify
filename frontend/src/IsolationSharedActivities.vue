<script setup lang="ts">
import { ref, onMounted } from 'vue';
const props = defineProps<{
  visitId: number;
  prospectId: number;
  role: string;
  request: (path: string, body?: any, method?: string) => Promise<any>;
}>();
const rows = ref<any[]>([]),
  page = ref(1),
  count = ref(0),
  revision = ref(0),
  busy = ref(false),
  error = ref(''),
  reason = ref(''),
  selected = ref<any>(null);
const statuses: Record<string, string> = {
  to_contact: 'À contacter',
  in_progress: 'En cours',
  callback: 'À rappeler',
  interested: 'Intéressé',
  not_interested: 'Non intéressé',
  unreachable: 'Non joint',
};
async function load() {
  const data = await props.request(`visits/${props.visitId}/activities/?page=${page.value}`);
  rows.value = data.results;
  count.value = data.count;
  if (props.role !== 'client')
    revision.value = (await props.request(`work-queue/${props.prospectId}/`)).revision;
}
async function run(action: () => Promise<void>) {
  busy.value = true;
  error.value = '';
  try {
    await action();
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function save() {
  await run(async () => {
    await props.request(`visits/${props.visitId}/activities/`, {
      activity_id: selected.value.id,
      revision: revision.value,
      visible: !selected.value.shared,
      reason: reason.value,
    });
    selected.value = null;
    reason.value = '';
    await load();
  });
}
onMounted(() => run(load));
</script>
<template>
  <section>
    <h4>Observations partagées avec le client</h4>
    <p v-if="role !== 'client'">
      Les observations restent internes par défaut. La publication partage le texte et la
      qualification affichés, avec l’identifiant de leur auteur, pour ce client sur toutes ses
      visites du même dossier. Le retrait bloque les prochaines consultations, sans effacer les
      copies déjà lues.
    </p>
    <p v-else>
      Seules les observations publiées pour vous sont affichées. Les résultats techniques des
      numéros ne sont pas modifiés par ces observations.
    </p>
    <p v-if="error" role="alert">{{ error }}</p>
    <button class="secondary" :disabled="busy" @click="run(load)">Actualiser</button>
    <article v-for="row in rows" :key="row.id">
      <small
        >{{ new Date(row.created_at).toLocaleString('fr-FR') }} ·
        {{ row.author_role === 'setter' ? 'Setter' : 'Administrateur' }} central n°
        {{ row.author_portal_id }} · {{ row.kind === 'note' ? 'Note' : 'Qualification' }}</small
      >
      <p style="white-space: pre-wrap">{{ row.body }}</p>
      <p v-if="row.changes.after">
        {{ statuses[row.changes.before.status] || row.changes.before.status }} →
        {{ statuses[row.changes.after.status] || row.changes.after.status }} · Rappel :
        {{
          row.changes.after.callback_at
            ? new Date(row.changes.after.callback_at).toLocaleString('fr-FR')
            : 'Aucun'
        }}
      </p>
      <p v-if="row.changes.before?.callback_at">
        Ancien rappel : {{ new Date(row.changes.before.callback_at).toLocaleString('fr-FR') }}
      </p>
      <template v-if="role !== 'client'"
        ><p>{{ row.shared ? 'Publié pour ce client' : 'Interne' }}</p>
        <button
          class="secondary"
          :disabled="busy"
          @click="
            selected = row;
            reason = '';
          "
        >
          {{ row.shared ? 'Retirer le partage' : 'Publier pour ce client' }}
        </button></template
      >
    </article>
    <p v-if="!rows.length">Aucune observation accessible.</p>
    <p>{{ count }} observation(s) · page {{ page }}</p>
    <button
      class="secondary"
      :disabled="busy || page === 1"
      @click="
        run(async () => {
          page--;
          await load();
        })
      "
    >
      Précédent</button
    ><button
      class="secondary"
      :disabled="busy || page * 25 >= count"
      @click="
        run(async () => {
          page++;
          await load();
        })
      "
    >
      Suivant
    </button>
    <form v-if="selected && role !== 'client'" @submit.prevent="save">
      <p>
        {{
          selected.shared
            ? 'Retirer cette observation du portail client ?'
            : 'Confirmer la publication de cette observation au client de la visite ?'
        }}
      </p>
      <label
        >Motif obligatoire<textarea
          v-model="reason"
          required
          maxlength="1000"
          :disabled="busy"
        ></textarea></label
      ><button class="primary" :disabled="busy">Confirmer</button
      ><button class="secondary" type="button" :disabled="busy" @click="selected = null">
        Annuler
      </button>
    </form>
  </section>
</template>
