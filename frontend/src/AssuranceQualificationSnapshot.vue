<script setup lang="ts">
defineProps<{ snapshot: any }>();
function value(field: any, data: any) {
  const result = data?.[field.key];
  if (
    result === null ||
    result === undefined ||
    result === '' ||
    (Array.isArray(result) && !result.length)
  )
    return 'Non renseigné';
  if (field.type === 'boolean') return result ? 'Oui' : 'Non';
  if (field.type === 'choice') return field.choices[result] || result;
  if (field.type === 'multiple')
    return result.map((key: string) => field.choices[key] || key).join(', ');
  return result;
}
const contactLabels: Record<string, string> = {
  name: 'Nom et prénom',
  phone: 'Téléphone',
  email: 'Courriel',
};
</script>
<template>
  <section class="booking-qualification">
    <h3>Qualification transmise au conseiller</h3>
    <p v-if="!snapshot?.version">
      Aucune copie de qualification conservée pour ce rendez-vous antérieur.
    </p>
    <template v-else
      ><p>
        Informations à la réservation ·
        {{
          new Date(snapshot.captured_at).toLocaleString('fr-FR', { timeZone: 'America/Toronto' })
        }}
        · Montréal
      </p>
      <dl>
        <div v-for="(item, key) in snapshot.contact" :key="key">
          <dt>{{ contactLabels[key] || key }}</dt>
          <dd>{{ item || 'Non renseigné' }}</dd>
        </div>
        <div v-for="field in snapshot.fields" :key="field.key">
          <dt>{{ field.label }}</dt>
          <dd>{{ value(field, snapshot.qualification) }}</dd>
        </div>
      </dl></template
    >
  </section>
</template>
<style scoped>
.booking-qualification {
  margin: 24px 0;
  padding: 20px;
  background: #f5f1fb;
  border: 1px solid #e9e0f3;
  border-radius: 14px;
}
.booking-qualification h3 {
  font-size: 15px !important;
  color: #8d7aa5;
  margin: 0 0 10px;
}
.booking-qualification > p {
  font-size: 11px;
  color: #a093af;
  line-height: 1.8;
}
.booking-qualification dl {
  margin: 20px 0 0;
}
.booking-qualification dl > div {
  display: grid;
  grid-template-columns: 1fr 1.3fr;
  gap: 15px;
  font-size: 12px;
  padding: 12px 0;
  border-top: 1px solid #e7e0ef;
  line-height: 1.8;
}
.booking-qualification dt {
  color: #a08ead;
}
.booking-qualification dd {
  margin: 0;
  color: #8b759e;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
@media (max-width: 550px) {
  .booking-qualification dl > div {
    grid-template-columns: 1fr;
    gap: 5px;
  }
}
</style>
