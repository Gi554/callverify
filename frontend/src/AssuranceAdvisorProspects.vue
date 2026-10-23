<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { Search, Users, CalendarCheck, ArrowRight, RefreshCw } from 'lucide-vue-next';
import SidePanel from './SidePanel.vue';
import AssuranceAdvisorAppointment from './AssuranceAdvisorAppointment.vue';
import { loadQuotas, type AdvisorQuota } from './advisor-quota';
const props = defineProps<{
  request: (path: string, body?: any, method?: string) => Promise<any>;
  portal: (path: string, body?: any) => Promise<any>;
  username: string;
}>();
const rows = ref<any[]>([]),
  totals = ref({ assigned: 0, attended: 0, absent: 0 });
const quota = ref<AdvisorQuota | null>(null),
  quotaError = ref('');
const page = ref(1),
  count = ref(0),
  search = ref(''),
  busy = ref(false),
  error = ref('');
const selected = ref<any>(null),
  detailBusy = ref(false);
const detail = ref<InstanceType<typeof AssuranceAdvisorAppointment> | null>(null);
async function load() {
  busy.value = true;
  error.value = '';
  quotaError.value = '';
  try {
    const data = await props.request(
      `advisor-prospects/?page=${page.value}&search=${encodeURIComponent(search.value)}`,
    );
    rows.value = data.results;
    count.value = data.count;
    totals.value = data.totals;
    try {
      const quotas = await loadQuotas(props.portal, props.request);
      quota.value = [...quotas.values()].find((row) => row.name === props.username) || null;
    } catch (e: any) {
      quota.value = null;
      quotaError.value = e.message;
    }
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
function close() {
  if (detailBusy.value || (detail.value && !detail.value.close())) return;
  selected.value = null;
  void load();
}
function searchRows() {
  page.value = 1;
  void load();
}
function move(offset: number) {
  page.value += offset;
  void load();
}
onMounted(load);
</script>
<template>
  <section class="advisor-prospects">
    <header>
      <div>
        <span class="eyebrow">MON PORTEFEUILLE</span>
        <h1>Mes prospects</h1>
        <p>Les clients qui vous sont attribués et le suivi de vos rendez-vous tenus.</p>
      </div>
      <button :disabled="busy" @click="load"><RefreshCw :size="16" />Actualiser</button>
    </header>
    <p v-if="error" role="alert">{{ error }}</p>
    <div class="prospect-counters">
      <article>
        <Users :size="22" /><span>Prospects attribués</span><strong>{{ totals.assigned }}</strong
        ><small>Clients distincts dans votre portefeuille</small>
      </article>
      <article class="mint">
        <CalendarCheck :size="22" /><span>Rendez-vous tenus</span
        ><strong>{{ totals.attended }}</strong
        ><small>{{ totals.absent }} absence(s), sans décompte</small>
      </article>
      <article class="lavender">
        <ArrowRight :size="22" /><span>Restant sur l’objectif</span
        ><strong>{{ quota?.remaining ?? '—' }}</strong
        ><small>{{
          quota?.quota != null
            ? `Objectif fixé : ${quota.quota} · Décompté : ${quota.attended}`
            : quotaError
              ? 'Décompte indisponible'
              : 'Objectif non défini par l’administration'
        }}</small>
      </article>
    </div>
    <p class="count-rule">
      Seuls les rendez-vous déclarés tenus diminuent l’objectif. Une réservation, une absence ou une
      annulation ne le consomme pas. Le décompte porte sur tous vos rendez-vous, sans filtre de
      période.
    </p>
    <form class="prospect-search" @submit.prevent="searchRows">
      <label
        ><Search :size="17" /><input
          v-model="search"
          aria-label="Rechercher mes prospects"
          placeholder="Nom, téléphone ou courriel" /></label
      ><button :disabled="busy">Rechercher</button><span>{{ count }} résultat(s)</span>
    </form>
    <div class="prospect-table">
      <table>
        <thead>
          <tr>
            <th>Prospect</th>
            <th>Téléphone</th>
            <th>Courriel</th>
            <th>Rendez-vous tenus</th>
            <th>Dossier</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
            <td>
              <strong>{{ row.name }}</strong>
            </td>
            <td>{{ row.phone }}</td>
            <td>{{ row.email || 'Non renseigné' }}</td>
            <td>
              <span :class="['attendance', { done: row.attended > 0 }]">{{ row.attended }}</span>
            </td>
            <td>
              <button v-if="row.appointment_id" @click="selected = row">
                Ouvrir la fiche <ArrowRight :size="14" /></button
              ><span v-else class="muted">Aucun rendez-vous attribué</span>
            </td>
          </tr>
          <tr v-if="!rows.length && !busy">
            <td colspan="5">
              {{
                search
                  ? 'Aucun prospect ne correspond à cette recherche.'
                  : 'Aucun prospect ne vous est encore attribué.'
              }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <footer>
      <span>{{ count }} prospect(s) · page {{ page }}</span
      ><button :disabled="busy || page === 1" @click="move(-1)">Précédent</button
      ><button :disabled="busy || page * 25 >= count" @click="move(1)">Suivant</button>
    </footer>
    <SidePanel
      :open="!!selected"
      :title="selected?.name || 'Fiche client'"
      eyebrow="MON PROSPECT"
      :close-disabled="detailBusy"
      @request-close="close"
      ><AssuranceAdvisorAppointment
        v-if="selected"
        :key="selected.appointment_id"
        ref="detail"
        :appointment-id="selected.appointment_id"
        :request="request"
        @busy="detailBusy = $event"
    /></SidePanel>
  </section>
</template>
<style scoped>
.advisor-prospects {
  color: #27384f;
  padding: 24px;
}
.advisor-prospects header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 18px;
  margin-bottom: 24px;
}
.advisor-prospects h1 {
  margin: 8px 0;
}
.advisor-prospects header p,
.advisor-prospects .muted {
  color: #718099;
}
.advisor-prospects .eyebrow {
  font-size: 11px;
  font-weight: 700;
  color: #7c68c8;
  letter-spacing: 2px;
}
.advisor-prospects button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 10px 14px;
  border: 1px solid #dbe3f0;
  border-radius: 9px;
  background: white;
  color: #3058a0;
  cursor: pointer;
}
.advisor-prospects button:disabled {
  opacity: 0.4;
  cursor: default;
}
.prospect-counters {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}
.prospect-counters article {
  display: grid;
  gap: 10px;
  padding: 24px;
  border-radius: 18px;
  background: #eaf1ff;
}
.prospect-counters article.mint {
  background: #e7f5ee;
}
.prospect-counters article.lavender {
  background: #f0eafb;
}
.prospect-counters strong {
  font-size: 34px;
}
.prospect-counters small {
  color: #64758c;
}
.count-rule {
  margin: 20px 0;
  font-size: 12px;
  line-height: 1.7;
  color: #6b7d94;
}
.advisor-prospects .prospect-search {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 18px;
}
.prospect-search label {
  display: flex;
  gap: 9px;
  align-items: center;
  background: white;
  border: 1px solid #dbe3f0;
  border-radius: 9px;
  padding: 0 13px;
}
.advisor-prospects .prospect-search input {
  border: 0;
  padding: 12px 0;
  min-width: 240px;
  background: transparent;
}
.prospect-search span {
  margin-left: auto;
  color: #718099;
}
.prospect-table {
  overflow-x: auto;
  border: 1px solid #e2e8f1;
  border-radius: 12px;
  background: white;
}
.prospect-table table {
  width: 100%;
  border-collapse: collapse;
}
.prospect-table th {
  text-align: left;
  background: #f7f9fd;
  color: #6c7d92;
  font-weight: 500;
}
.prospect-table td,
.prospect-table th {
  padding: 16px;
  border-bottom: 1px solid #eef1f6;
}
.attendance {
  display: inline-block;
  min-width: 30px;
  text-align: center;
  padding: 6px;
  border-radius: 8px;
  background: #f1f3f8;
}
.attendance.done {
  color: #277454;
  background: #e4f5ec;
}
.advisor-prospects footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
}
.advisor-prospects footer span {
  margin-right: auto;
  color: #718099;
}
@media (max-width: 760px) {
  .prospect-counters {
    grid-template-columns: 1fr;
  }
  .advisor-prospects .prospect-search {
    flex-wrap: wrap;
  }
  .prospect-search label,
  .advisor-prospects .prospect-search input {
    min-width: 0;
    width: 100%;
  }
}
</style>
