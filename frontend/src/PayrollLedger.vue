<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { Wallet, Target, ReceiptText, Plus, History } from 'lucide-vue-next';
import StatKpi from './StatKpi.vue';
import SidePanel from './SidePanel.vue';
import IsolationPageHeader from './IsolationPageHeader.vue';
const props = defineProps<{
  workspace: string;
  role: string;
  request: (path: string, body?: any) => Promise<any>;
  portal: (path: string, body?: any) => Promise<any>;
}>();
const admin = computed(() => props.role === 'administrator');
const now = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'America/Toronto',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
}).format(new Date());
const from = ref(now.slice(0, 8) + '01'),
  to = ref(now),
  rows = ref<any[]>([]),
  agent = ref(''),
  detail = ref<any>(null),
  busy = ref(false),
  error = ref(''),
  message = ref('');
const panel = ref(''),
  editingTerm = ref<any>(null),
  dirty = ref(false),
  reason = ref('');
const term = ref({
  starts_on: now,
  ends_on: now,
  cadence: 'week',
  target: 10,
  attendance_cad: '',
  bonus_cad: '0',
  conditions: '',
});
const payment = ref({ amount_cad: '', paid_on: now, reference: '', note: '' });
const paymentsPage = ref(1),
  adjustmentsPage = ref(1);
let requestId = crypto.randomUUID();
const cad = (value: any) =>
  value == null
    ? '—'
    : new Intl.NumberFormat('fr-CA', { style: 'currency', currency: 'CAD' }).format(Number(value));
const date = (value: string) =>
  new Intl.DateTimeFormat('fr-CA', {
    timeZone: 'America/Toronto',
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
const criteria = () => new URLSearchParams({ from: from.value, to: to.value }).toString();
async function run(action: () => Promise<void>) {
  if (busy.value) return;
  busy.value = true;
  error.value = '';
  try {
    await action();
  } catch (e: any) {
    error.value = e.message || 'Opération indisponible.';
  } finally {
    busy.value = false;
  }
}
async function load() {
  const data = await props.request('payroll/?' + criteria());
  rows.value = data.results;
  if (!rows.value.some((row) => String(row.agent_id) === agent.value))
    agent.value = rows.value.length ? String(rows.value[0].agent_id) : '';
  await loadDetail();
}
async function chooseAgent() {
  paymentsPage.value = 1;
  adjustmentsPage.value = 1;
  await loadDetail();
}
async function loadDetail() {
  detail.value = null;
  if (agent.value)
    detail.value = await props.request(
      `payroll/${agent.value}/?${criteria()}&payments_page=${paymentsPage.value}&adjustments_page=${adjustmentsPage.value}`,
    );
}
function close() {
  if (!busy.value && (!dirty.value || confirm('Abandonner les informations non enregistrées ?'))) {
    panel.value = '';
    dirty.value = false;
  }
}
function openTerms(row?: any) {
  editingTerm.value = row || null;
  reason.value = '';
  term.value = row
    ? {
        starts_on: row.starts_on,
        ends_on: row.ends_on,
        cadence: row.cadence,
        target: row.target,
        attendance_cad: row.attendance_cad,
        bonus_cad: row.bonus_cad,
        conditions: row.conditions,
      }
    : {
        starts_on: now,
        ends_on: now,
        cadence: 'week',
        target: 10,
        attendance_cad: '',
        bonus_cad: '0',
        conditions: '',
      };
  dirty.value = false;
  panel.value = 'terms';
}
function openPayment() {
  payment.value = { amount_cad: '', paid_on: now, reference: '', note: '' };
  requestId = crypto.randomUUID();
  dirty.value = false;
  panel.value = 'payment';
}
async function saveTerms() {
  await run(async () => {
    let proof: string | undefined;
    if (props.workspace === 'isolation')
      proof = (
        await props.portal('isolation/compensation-proof/', { setter_id: Number(agent.value) })
      ).proof;
    await props.request(
      `payroll/${agent.value}/terms/${editingTerm.value ? editingTerm.value.id + '/' : ''}`,
      {
        ...term.value,
        bonus_cad: props.workspace === 'assurance' ? '0' : term.value.bonus_cad,
        reason: reason.value,
        revision: editingTerm.value?.revision || 0,
        ...(proof ? { proof } : {}),
      },
    );
    panel.value = '';
    dirty.value = false;
    message.value = 'Conditions enregistrées. Les montants déjà acquis conservent leur tarif.';
    await load();
  });
}
async function savePayment() {
  await run(async () => {
    await props.request(`payroll/${agent.value}/payments/`, {
      ...payment.value,
      revision: detail.value.revision,
      request_id: requestId,
    });
    panel.value = '';
    dirty.value = false;
    message.value = 'Paiement enregistré dans le registre. Aucun virement effectué par Orvia.';
    await load();
  });
}
onMounted(() => run(load));
</script>
<template>
  <section class="payroll-ledger iso-page">
    <IsolationPageHeader
      :title="admin ? 'Rémunérations et paiements' : 'Mes gains et mon objectif'"
      :eyebrow="(workspace === 'isolation' ? 'ISOLATION' : 'ASSURANCE') + ' · RÉMUNÉRATION CAD'"
      subtitle="Les résultats validés, les conditions applicables et les règlements, au même endroit."
      :busy="busy"
      @refresh="run(load)"
    />
    <p v-if="error && !panel" role="alert">
      {{ error }} <button class="secondary" :disabled="busy" @click="run(load)">Réessayer</button>
    </p>
    <p v-if="message" role="status" class="iso-notice">{{ message }}</p>
    <section class="iso-panel">
      <header class="iso-panel-heading">
        <div>
          <h2>
            <Wallet :size="19" />
            {{ admin ? 'Le suivi de vos agents' : 'Votre activité rémunérée' }}
          </h2>
          <p>Heure du Québec · Les comptes Assurance et Isolation restent séparés.</p>
        </div>
      </header>
      <form class="payroll-filters" @submit.prevent="run(load)">
        <label v-if="admin"
          >Agent<select v-model="agent" :disabled="busy" @change="run(chooseAgent)">
            <option v-if="!rows.length" value="">Aucun agent connu</option>
            <option v-for="row in rows" :key="row.agent_id" :value="String(row.agent_id)">
              {{ row.agent_name }}
            </option>
          </select></label
        ><label>Du<input v-model="from" type="date" required :disabled="busy" /></label
        ><label>Au<input v-model="to" type="date" required :disabled="busy" /></label
        ><button class="primary" :disabled="busy">Calculer la période</button>
      </form>
      <p v-if="!rows.length && !busy" class="iso-empty">
        Aucun setter connu dans cet espace. Affectez un setter avant de définir ses conditions.
      </p>
    </section>
    <template v-if="detail">
      <div class="payroll-kpis">
        <StatKpi
          label="Généré sur la période"
          :value="cad(detail.period.amount_cad)"
          :hint="detail.period.attendance + ' présence(s) validée(s)'"
        /><StatKpi label="Généré depuis le début" :value="cad(detail.generated_cad)" /><StatKpi
          label="Déjà payé, cumul"
          :value="cad(detail.paid_cad)"
        /><StatKpi label="Reste à payer, cumul" :value="cad(detail.to_pay_cad)" />
      </div>
      <section v-if="workspace === 'isolation'" class="iso-panel">
        <p>
          Présences sur la période : <strong>{{ detail.period.attendance }}</strong> ·
          {{ cad(detail.period.attendance_amount_cad) }}. Ventes rémunérables :
          <strong>{{ detail.period.sales }}</strong> · Primes :
          {{ cad(detail.period.sale_bonus_cad) }}.
        </p>
      </section>
      <p v-if="Number(detail.to_regularize_cad) > 0" class="iso-notice" role="alert">
        Correction après paiement : {{ cad(detail.to_regularize_cad) }} à régulariser. Les paiements
        précédents sont conservés.
      </p>
      <p v-if="detail.unpriced" class="iso-notice">
        {{ detail.unpriced }} composante(s) rémunérable(s) sans tarif conservé. Ces montants ne sont
        pas inventés et ne sont pas inclus dans le total connu.
      </p>
      <section class="iso-panel">
        <header class="iso-panel-heading">
          <div>
            <h2>
              <Target :size="19" />
              {{ detail.goal?.cadence === 'mandate' ? 'Mon mandat' : 'Objectif en cours' }}
            </h2>
            <p>Les absences ne font pas avancer l’objectif.</p>
          </div>
          <button v-if="admin" class="secondary" :disabled="busy" @click="openTerms()">
            <Plus :size="15" />Définir des conditions
          </button>
        </header>
        <template v-if="detail.goal"
          ><div class="payroll-goal">
            <strong>{{ detail.goal.completed }} / {{ detail.goal.target }}</strong
            ><span>présences validées · {{ detail.goal.remaining }} restantes</span
            ><progress
              :value="Math.min(detail.goal.completed, detail.goal.target)"
              :max="Math.max(1, detail.goal.target)"
            ></progress>
          </div>
          <p>
            Du {{ detail.goal.from }} au {{ detail.goal.to }} ·
            {{ cad(detail.goal.attendance_cad) }} par présence<span
              v-if="workspace === 'isolation'"
            >
              + {{ cad(detail.goal.bonus_cad) }} par vente conclue</span
            >.
          </p>
          <p v-if="detail.goal.conditions">{{ detail.goal.conditions }}</p></template
        >
        <p v-else>
          Aucun objectif ou mandat applicable aujourd’hui. Les tarifs historiques déjà conservés
          restent pris en compte.
        </p>
        <details>
          <summary>Conditions et périodes enregistrées ({{ detail.terms.length }})</summary>
          <article v-for="row in detail.terms" :key="row.id" class="payroll-history">
            <strong
              >{{ row.starts_on }} → {{ row.ends_on }} ·
              {{ row.cadence === 'week' ? 'Hebdomadaire' : 'Mandat' }}</strong
            >
            <p>
              Objectif : {{ row.target }} · Présence : {{ cad(row.attendance_cad)
              }}<span v-if="workspace === 'isolation'"> · Prime : {{ cad(row.bonus_cad) }}</span>
            </p>
            <p>{{ row.conditions }}</p>
            <button
              v-if="admin && row.editable"
              class="secondary"
              :disabled="busy"
              @click="openTerms(row)"
            >
              Modifier cette période future
            </button>
          </article>
          <p v-if="!detail.terms.length">Aucune période enregistrée.</p>
        </details>
      </section>
      <section class="iso-panel">
        <header class="iso-panel-heading">
          <div>
            <h2><ReceiptText :size="19" />Paiements enregistrés</h2>
            <p>
              Registre des règlements effectués hors Orvia. Aucun transfert bancaire depuis le CRM.
            </p>
          </div>
          <button
            v-if="admin"
            class="primary"
            :disabled="busy || Number(detail.to_pay_cad) <= 0"
            @click="openPayment()"
          >
            Enregistrer un paiement
          </button>
        </header>
        <div class="payroll-table">
          <table>
            <thead>
              <tr>
                <th>Date de paiement</th>
                <th>Montant CAD</th>
                <th>Référence</th>
                <th>Enregistré par</th>
                <th>Enregistré le</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in detail.payments" :key="row.id">
                <td>{{ row.paid_on }}</td>
                <td>{{ cad(row.amount_cad) }}</td>
                <td>
                  {{ row.reference }}<small v-if="row.note">{{ row.note }}</small>
                </td>
                <td>Compte #{{ row.actor_id }}</td>
                <td>{{ date(row.created_at) }}</td>
              </tr>
              <tr v-if="!detail.payments.length">
                <td colspan="5">Aucun paiement enregistré.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
      <footer class="iso-pagination">
        <span>{{ detail.payments_count }} paiement(s)</span
        ><button
          class="secondary"
          :disabled="busy || paymentsPage === 1"
          @click="
            paymentsPage--;
            run(loadDetail);
          "
        >
          Paiements précédents</button
        ><button
          class="secondary"
          :disabled="busy || paymentsPage * 25 >= detail.payments_count"
          @click="
            paymentsPage++;
            run(loadDetail);
          "
        >
          Paiements suivants
        </button>
      </footer>
      <section class="iso-panel">
        <header class="iso-panel-heading">
          <div>
            <h2><History :size="19" />Ajustements après correction</h2>
            <p>Une correction conserve les unités de tarif et les paiements dans l’historique.</p>
          </div>
        </header>
        <article v-for="row in detail.adjustments" :key="row.id" class="payroll-history">
          <strong>{{ cad(row.delta_cad) }} · {{ date(row.created_at) }}</strong>
          <p>{{ cad(row.before_cad) }} → {{ cad(row.after_cad) }} · {{ row.reason }}</p>
          <small>Compte #{{ row.actor_id || 'système' }}</small>
        </article>
        <p v-if="!detail.adjustments.length">Aucun ajustement enregistré.</p>
        <footer class="iso-pagination">
          <span>{{ detail.adjustments_count }} ajustement(s)</span
          ><button
            class="secondary"
            :disabled="busy || adjustmentsPage === 1"
            @click="
              adjustmentsPage--;
              run(loadDetail);
            "
          >
            Ajustements précédents</button
          ><button
            class="secondary"
            :disabled="busy || adjustmentsPage * 25 >= detail.adjustments_count"
            @click="
              adjustmentsPage++;
              run(loadDetail);
            "
          >
            Ajustements suivants
          </button>
        </footer>
      </section>
      <p class="payroll-definition">
        {{ detail.definition }} Les règlements et le solde sont cumulés ; le filtre de période porte
        uniquement sur les gains et présences.
      </p>
    </template>
    <SidePanel
      :open="!!panel"
      :title="panel === 'terms' ? 'Conditions de rémunération' : 'Enregistrer un paiement effectué'"
      eyebrow="RÉMUNÉRATION · CAD"
      :close-disabled="busy"
      @request-close="close"
    >
      <form
        v-if="panel === 'terms'"
        class="iso-detail iso-form"
        @input="dirty = true"
        @change="dirty = true"
        @submit.prevent="saveTerms"
      >
        <p v-if="error" role="alert">{{ error }}</p>
        <fieldset :disabled="busy">
          <label
            >Début de validité<input
              v-model="term.starts_on"
              type="date"
              :min="now"
              required /></label
          ><label
            >Fin de validité<input
              v-model="term.ends_on"
              type="date"
              :min="term.starts_on"
              required /></label
          ><label
            >Objectif<select v-model="term.cadence">
              <option value="week">Par semaine (lundi–dimanche)</option>
              <option value="mandate">Pour tout le mandat</option>
            </select></label
          ><label
            >Nombre de présences validées attendu<input
              v-model.number="term.target"
              type="number"
              min="0"
              max="100000"
              step="1"
              required /></label
          ><label
            >Montant par présence validée (CAD)<input
              v-model="term.attendance_cad"
              type="number"
              min="0"
              step="0.01"
              required /></label
          ><label v-if="workspace === 'isolation'"
            >Prime supplémentaire par vente (CAD)<input
              v-model="term.bonus_cad"
              type="number"
              min="0"
              step="0.01"
              required /></label
          ><label
            >Conditions particulières<textarea
              v-model="term.conditions"
              maxlength="2000"
            ></textarea></label
          ><label
            >Motif de création ou modification<textarea
              v-model="reason"
              maxlength="1000"
              required
            ></textarea>
          </label>
          <p>
            Les conditions déjà applicables sont conservées. Une période future ne doit pas
            chevaucher une autre.
          </p>
          <button class="primary">Enregistrer les conditions</button
          ><button class="secondary" type="button" @click="close">Annuler</button>
        </fieldset>
      </form>
      <form
        v-if="panel === 'payment'"
        class="iso-detail iso-form"
        @input="dirty = true"
        @submit.prevent="savePayment"
      >
        <p v-if="error" role="alert">{{ error }}</p>
        <fieldset :disabled="busy">
          <p>
            Solde payable connu : {{ cad(detail?.to_pay_cad) }}. Cette action constate un paiement
            déjà effectué.
          </p>
          <label
            >Montant payé (CAD)<input
              v-model="payment.amount_cad"
              type="number"
              min="0.01"
              :max="detail?.to_pay_cad"
              step="0.01"
              required /></label
          ><label
            >Date du paiement<input
              v-model="payment.paid_on"
              type="date"
              :max="now"
              required /></label
          ><label
            >Référence unique pour cet agent<input
              v-model="payment.reference"
              maxlength="150"
              required /></label
          ><label>Note<textarea v-model="payment.note" maxlength="1000"></textarea></label
          ><button class="primary">Confirmer l’enregistrement</button
          ><button class="secondary" type="button" @click="close">Annuler</button>
        </fieldset>
      </form>
    </SidePanel>
  </section>
</template>
<style scoped>
.payroll-ledger {
  margin: 0 0 24px;
  min-width: 0;
}
.payroll-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  align-items: end;
}
.payroll-filters label {
  display: grid;
  gap: 7px;
  font-size: 12px;
  flex: 1;
  min-width: 140px;
}
.payroll-filters input,
.payroll-filters select {
  min-height: 40px;
  width: 100%;
  box-sizing: border-box;
  border: 1px solid #dfe5f1;
  border-radius: 10px;
  padding: 10px;
  background: #fbfcff;
  color: #344560;
}
.payroll-kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.payroll-kpis > :nth-child(1) {
  background: #eaf2fe;
}
.payroll-kpis > :nth-child(2) {
  background: #f1eafa;
}
.payroll-kpis > :nth-child(3) {
  background: #eaf6f1;
}
.payroll-kpis > :nth-child(4) {
  background: #fff1df;
}
.payroll-goal {
  display: grid;
  gap: 8px;
  margin: 16px 0;
}
.payroll-goal strong {
  font-size: 32px;
}
.payroll-goal progress {
  width: 100%;
  accent-color: #785de6;
  height: 12px;
}
.payroll-history {
  padding: 16px 0;
  border-bottom: 1px solid #edf0f6;
}
.payroll-table {
  overflow: auto;
  max-width: 100%;
}
.payroll-table table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.payroll-table th,
.payroll-table td {
  text-align: left;
  padding: 13px;
  border-bottom: 1px solid #edf0f6;
  vertical-align: top;
}
.payroll-table th {
  background: #f5f7fc;
  font-size: 11px;
  color: #758097;
}
.payroll-table small {
  display: block;
  margin-top: 5px;
}
.payroll-definition {
  font-size: 11px !important;
  color: #8992a5 !important;
  line-height: 1.6;
}
.iso-panel-heading h2 {
  display: flex;
  gap: 8px;
  align-items: center;
}
.iso-detail fieldset {
  display: grid;
  gap: 14px;
  border: 0;
  padding: 0;
}
.iso-panel details {
  margin-top: 18px;
  font-size: 12px;
}
.iso-panel summary {
  cursor: pointer;
  font-weight: 600;
}
@media (max-width: 1000px) {
  .payroll-kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 600px) {
  .payroll-filters {
    gap: 10px;
  }
  .iso-panel-heading {
    flex-wrap: wrap;
  }
  .payroll-table table {
    min-width: 650px;
  }
}
</style>
