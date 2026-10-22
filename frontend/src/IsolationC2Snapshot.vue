<script setup lang="ts">
defineProps<{ snapshot: any }>()
const labels: Record<string, string> = {
  full_name: 'Nom et prénom',
  phone: 'Téléphone',
  address: 'Adresse complète',
  city: 'Ville',
  postal_code: 'Code postal',
  attic_accessible: 'Grenier accessible',
  monthly_electricity: 'Électricité mensuelle ($)',
  construction_year: 'Année de construction',
  age: 'Âge du client',
}
function value(v: any) {
  return v === true
    ? 'Oui'
    : v === false
      ? 'Non'
      : v === null || v === undefined || v === ''
        ? 'Non renseigné'
        : v
}
</script>
<!-- prettier-ignore -->
<template><details class="c2-copy"><summary>Formulaire C2 transmis avec la visite</summary><template v-if="snapshot?.fields"><p>Copie du {{new Date(snapshot.captured_at).toLocaleString('fr-FR')}} · Campagne {{snapshot.campaign_id}}</p><dl><div v-for="(label,key) in labels" :key="key"><dt>{{label}}</dt><dd>{{value(snapshot.fields[key])}}</dd></div></dl><small>La copie conserve les informations à la réservation. Le créneau actuel est celui de la visite.</small></template><p v-else>Aucun C2 conservé pour cette ancienne visite.</p></details></template>
<style scoped>
.c2-copy {
  border: 1px solid #e4e7f1;
  border-radius: 12px;
  padding: 16px;
  margin: 16px 0;
  font-size: 12px;
}
.c2-copy summary {
  cursor: pointer;
  font-weight: 600;
  color: #62529c;
}
.c2-copy dl {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.c2-copy dt {
  color: #7c8297;
  font-size: 11px;
}
.c2-copy dd {
  margin: 5px 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.c2-copy p,
.c2-copy small {
  color: #767e91;
  line-height: 1.6;
}
</style>
