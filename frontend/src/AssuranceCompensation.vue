<script setup lang="ts">
import { ref, onMounted } from 'vue';
import SidePanel from './SidePanel.vue';
const props = defineProps<{
  request: (path: string, body?: any) => Promise<any>;
  portal: (path: string, body?: any) => Promise<any>;
}>();
const from = ref(''),
  to = ref(''),
  result = ref<any>(null),
  calls = ref<any>(null),
  busy = ref(false),
  error = ref(''),
  callError = ref(''),
  message = ref(''),
  page = ref(1);
const selected = ref<any>(null),
  mode = ref(''),
  amount = ref(''),
  reason = ref(''),
  detail = ref<any>(null),
  detailPage = ref(1);
const cad = (value: string | null) =>
  value === null
    ? 'Non défini'
    : new Intl.NumberFormat('fr-CA', { style: 'currency', currency: 'CAD' }).format(Number(value));
const day = (value: any) => String(value).slice(0, 10);
const when = (value: string) =>
  new Intl.DateTimeFormat('fr-CA', {
    timeZone: 'America/Toronto',
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
const query = () => (from.value && to.value ? `from=${from.value}&to=${to.value}` : '');
const appliedQuery = () => `from=${day(result.value.from)}&to=${day(result.value.to)}`;
function callCount(id: number) {
  return calls.value ? calls.value.results.find((r: any) => r.user_id === id)?.calls || 0 : '—';
}
async function load() {
  busy.value = true;
  error.value = '';
  callError.value = '';
  try {
    const data = await props.request(`compensation/?${query()}&page=${page.value}`);
    result.value = data;
    from.value = day(data.from);
    to.value = day(data.to);
    calls.value = null;
    try {
      calls.value = await props.portal(`assurance/call-statistics/?${query()}`);
    } catch (e: any) {
      callError.value = 'Appels indisponibles : ' + e.message;
    }
  } catch (e: any) {
    result.value = null;
    calls.value = null;
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
function moveWeek(offset: number) {
  if (busy.value) return;
  const shift = (stamp: string) => {
    const d = new Date(stamp + 'T12:00:00Z');
    d.setUTCDate(d.getUTCDate() + offset * 7);
    return d.toISOString().slice(0, 10);
  };
  from.value = shift(from.value);
  to.value = shift(to.value);
  page.value = 1;
  void load();
}
function openRate(row: any) {
  selected.value = row;
  mode.value = 'rate';
  amount.value = row.rate_cad ?? '';
  reason.value = '';
  error.value = '';
}
function rateChanged() {
  return amount.value === ''
    ? selected.value?.rate_cad !== null
    : selected.value?.rate_cad === null ||
        Number(amount.value) !== Number(selected.value?.rate_cad);
}
function close() {
  if (busy.value) return;
  if (
    mode.value === 'rate' &&
    (reason.value || rateChanged()) &&
    !window.confirm('Fermer sans enregistrer votre saisie ?')
  )
    return;
  selected.value = null;
}
async function saveRate() {
  busy.value = true;
  error.value = '';
  try {
    await props.request(`compensation/${selected.value.setter_id}/rate/`, {
      amount_cad: amount.value === '' ? null : amount.value,
      revision: selected.value.rate_revision,
      reason: reason.value,
    });
    selected.value = null;
    message.value = 'Tarif enregistré. Les montants déjà valorisés sont conservés.';
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
  if (!selected.value) await load();
}
async function valueMissing() {
  if (!reason.value.trim() || selected.value.rate_cad === null) return;
  if (
    !window.confirm(
      `Appliquer le tarif enregistré de ${cad(selected.value.rate_cad)} aux présences sans tarif de cette période ? Les anciens montants restent conservés.`,
    )
  )
    return;
  busy.value = true;
  error.value = '';
  try {
    const data = await props.request(`compensation/${selected.value.setter_id}/value/`, {
      starts_on: day(result.value.from),
      ends_on: day(result.value.to),
      rate_revision: selected.value.rate_revision,
      reason: reason.value,
    });
    selected.value = null;
    message.value = `${data.valued} présence(s) valorisée(s).`;
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
  if (!selected.value) await load();
}
async function openDetails(row: any, targetPage = 1) {
  selected.value = row;
  mode.value = 'details';
  detailPage.value = targetPage;
  detail.value = null;
  reason.value = '';
  busy.value = true;
  error.value = '';
  try {
    detail.value = await props.request(
      `compensation/${row.setter_id}/details/?${appliedQuery()}&page=${targetPage}`,
    );
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function exportCsv() {
  busy.value = true;
  error.value = '';
  try {
    const callData = await props.portal(`assurance/call-statistics/?${appliedQuery()}`);
    const data = await props.request(`compensation/?${appliedQuery()}&page=1`);
    if (data.count > 5000) throw new Error('Export limité à 5 000 setters.');
    const rows = [...data.results];
    for (let p = 2; rows.length < data.count; p++) {
      const next = await props.request(`compensation/?${appliedQuery()}&page=${p}`);
      if (!next.results.length) break;
      rows.push(...next.results);
    }
    const values = [
      [
        'Setter ID',
        'Setter',
        'Appels Orvia poste joint',
        'Pris',
        'Transmis externes',
        'À venir',
        'Honorés',
        'Non honorés',
        'Validés pour rémunération',
        'Sans tarif',
        'Montant CAD',
        'Tarif actuel CAD',
        'Du Québec',
        'Au Québec',
      ],
      ...rows.map((r: any) => [
        r.setter_id,
        r.setter_name,
        callData.results.find((c: any) => c.user_id === r.setter_id)?.calls || 0,
        r.booked,
        r.transmitted,
        r.upcoming,
        r.attended,
        r.absent,
        r.payable,
        r.unpriced,
        r.amount_cad,
        r.rate_cad ?? 'Non défini',
        day(data.from),
        day(data.to),
      ]),
    ];
    const cell = (v: any) => {
      let s = String(v);
      if (/^[\s]*[=+@-]/.test(s)) s = "'" + s;
      return '"' + s.replaceAll('"', '""') + '"';
    };
    const blob = new Blob(['\ufeff' + values.map((r) => r.map(cell).join(';')).join('\r\n')], {
      type: 'text/csv;charset=utf-8',
    });
    const url = URL.createObjectURL(blob),
      a = document.createElement('a');
    a.href = url;
    a.download = `suivi-setters-${day(data.from)}-${day(data.to)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
onMounted(load);
</script>
<template>
  <section class="compensation">
    <header>
      <div>
        <h2>Suivi et rémunération des setters</h2>
        <p>Présences validées · Dollar canadien · Heure du Québec</p>
      </div>
      <button class="secondary" :disabled="busy || !result" @click="exportCsv">Exporter CSV</button>
    </header>
    <form
      class="period"
      @submit.prevent="
        page = 1;
        load();
      "
    >
      <button type="button" class="secondary" :disabled="busy || !result" @click="moveWeek(-1)">
        ← 7 jours
      </button>
      <label>Du<input v-model="from" type="date" required :disabled="busy || !!selected" /></label
      ><label
        >Au inclus<input v-model="to" type="date" required :disabled="busy || !!selected"
      /></label>
      <button class="primary" :disabled="busy">Afficher</button
      ><button
        type="button"
        class="secondary"
        :disabled="busy"
        @click="
          from = '';
          to = '';
          page = 1;
          load();
        "
      >
        Cette semaine</button
      ><button type="button" class="secondary" :disabled="busy || !result" @click="moveWeek(1)">
        7 jours →
      </button>
    </form>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <p v-if="callError" role="alert">
      {{ callError }}. Aucun zéro n’est déduit de cette indisponibilité.
    </p>
    <template v-if="result">
      <div class="totals">
        <article>
          <strong>{{ calls?.totals.calls ?? '—' }}</strong
          ><span>Appels Orvia · poste joint</span>
        </article>
        <article>
          <strong>{{ result.totals.payable }}</strong
          ><span>Présences validées</span>
        </article>
        <article>
          <strong>{{ cad(result.totals.amount_cad) }}</strong
          ><span>Montant valorisé</span>
        </article>
        <article>
          <strong>{{ result.totals.unpriced }}</strong
          ><span>Présences à valoriser</span>
        </article>
      </div>
      <p class="definition">{{ result.definition }}</p>
      <p class="definition">
        {{ calls?.definition }} Les appels totaux incluent les administrateurs ; le tableau détaille
        les setters connus du métier.
      </p>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Setter</th>
              <th>Appels Orvia</th>
              <th>Pris</th>
              <th>Transmis</th>
              <th>À venir</th>
              <th>Honorés</th>
              <th>Non honorés</th>
              <th>Validés rémunération</th>
              <th>Sans tarif</th>
              <th>Montant CAD</th>
              <th>Tarif actuel</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in result.results" :key="row.setter_id">
              <td>
                {{ row.setter_name }}<small>#{{ row.setter_id }}</small>
              </td>
              <td>{{ callCount(row.setter_id) }}</td>
              <td>{{ row.booked }}</td>
              <td>{{ row.transmitted }}</td>
              <td>{{ row.upcoming }}</td>
              <td>{{ row.attended }}</td>
              <td>{{ row.absent }}</td>
              <td>{{ row.payable }}</td>
              <td>{{ row.unpriced }}</td>
              <td>{{ cad(row.amount_cad) }}</td>
              <td>{{ cad(row.rate_cad) }}</td>
              <td>
                <button class="secondary" :disabled="busy" @click="openDetails(row)">Détail</button
                ><button class="secondary" :disabled="busy" @click="openRate(row)">
                  Tarif / valoriser
                </button>
              </td>
            </tr>
            <tr v-if="!result.results.length">
              <td colspan="12">Aucun setter affecté ou rendez-vous enregistré.</td>
            </tr>
          </tbody>
        </table>
      </div>
      <nav aria-label="Pages setters">
        <span>{{ result.count }} setter(s) · page {{ page }}</span
        ><button
          class="secondary"
          :disabled="busy || !result.previous"
          @click="
            page--;
            load();
          "
        >
          Précédent</button
        ><button
          class="secondary"
          :disabled="busy || !result.next"
          @click="
            page++;
            load();
          "
        >
          Suivant
        </button>
      </nav>
    </template>
    <SidePanel
      :open="!!selected"
      :title="selected?.setter_name || 'Setter'"
      eyebrow="ASSURANCE · RÉMUNÉRATION"
      :close-disabled="busy"
      @request-close="close"
    >
      <p v-if="error" role="alert">{{ error }}</p>
      <form v-if="selected && mode === 'rate'" class="rate-form" @submit.prevent="saveRate">
        <h3>Tarif par rendez-vous validé</h3>
        <p>
          Les présences futures utilisent ce tarif. Les montants déjà enregistrés restent conservés.
          Une absence ne génère aucune rémunération.
        </p>
        <label
          >Montant CAD (vide = non défini)<input
            v-model="amount"
            type="number"
            step="0.01"
            min="0"
            max="9999999.99"
            :disabled="busy" /></label
        ><label
          >Motif obligatoire<textarea
            v-model="reason"
            maxlength="1000"
            required
            :disabled="busy"
          ></textarea></label
        ><button class="primary" :disabled="busy || !reason.trim()">Enregistrer le tarif</button>
        <hr />
        <h3>Présences antérieures sans tarif</h3>
        <p>
          {{ selected.unpriced }} présence(s) sur la période {{ day(result.from) }} →
          {{ day(result.to) }}. Tarif actuellement enregistré : {{ cad(selected.rate_cad) }}. Cette
          action applique ce tarif, sans remplacer un ancien montant.
        </p>
        <button
          type="button"
          class="secondary"
          :disabled="
            busy ||
            !reason.trim() ||
            !selected.unpriced ||
            selected.rate_cad === null ||
            rateChanged()
          "
          @click="valueMissing"
        >
          Valoriser au tarif enregistré
        </button>
      </form>
      <template v-if="mode === 'details' && detail"
        ><p>
          Du {{ day(result.from) }} au {{ day(result.to) }} · heures du Québec. Aucun paiement n’est
          déclenché.
        </p>
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Rendez-vous</th>
                <th>Conseiller</th>
                <th>Présence</th>
                <th>Tarif conservé CAD</th>
                <th>Montant retenu CAD</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in detail.results" :key="row.id">
                <td>
                  #{{ row.id }}<small>{{ when(row.starts_at) }}</small>
                </td>
                <td>{{ row.advisor_name }}</td>
                <td>
                  {{
                    row.status === 'cancelled'
                      ? 'Annulé'
                      : row.performed === true
                        ? 'Validé'
                        : row.performed === false
                          ? 'Non honoré / non effectué'
                          : 'En attente'
                  }}
                </td>
                <td>
                  {{ cad(row.unit_rate_cad)
                  }}<small v-if="row.valued_at"
                    >Valorisé le {{ when(row.valued_at) }} · tarif v{{ row.rate_revision }}</small
                  >
                </td>
                <td>{{ row.payable ? cad(row.amount_cad) : 'Non rémunérable' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <nav>
          <button
            class="secondary"
            :disabled="busy || !detail.previous"
            @click="openDetails(selected, detailPage - 1)"
          >
            Précédent</button
          ><span>{{ detail.count }} rendez-vous · page {{ detailPage }}</span
          ><button
            class="secondary"
            :disabled="busy || !detail.next"
            @click="openDetails(selected, detailPage + 1)"
          >
            Suivant
          </button>
        </nav></template
      >
    </SidePanel>
  </section>
</template>
<style scoped>
.compensation {
  display: grid;
  gap: 20px;
  min-width: 0;
}
header,
.period,
nav {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  justify-content: space-between;
}
h2,
h3,
p {
  margin: 0;
}
header p,
.definition {
  color: #778299;
  font-size: 12px;
  line-height: 1.6;
}
.period {
  justify-content: flex-start;
  align-items: end;
}
label {
  display: grid;
  gap: 6px;
}
.totals {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}
article {
  border: 1px solid #e8e3f4;
  border-radius: 16px;
  padding: 20px;
  background: #faf8ff;
  display: grid;
  gap: 8px;
}
article strong {
  font-size: 24px;
  color: #5e47d6;
}
article span {
  font-size: 12px;
}
.table-scroll {
  overflow: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
td,
th {
  text-align: left;
  padding: 12px;
  border-bottom: 1px solid #e9edf5;
}
th {
  background: #f6f7fb;
  white-space: nowrap;
}
td small {
  display: block;
  color: #778299;
  margin-top: 5px;
}
td button {
  margin: 3px;
  white-space: nowrap;
}
.rate-form {
  display: grid;
  gap: 16px;
}
.rate-form p {
  font-size: 13px;
  line-height: 1.6;
}
[role='alert'] {
  color: #b42318;
}
[role='status'] {
  color: #067647;
}
</style>
