<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import SidePanel from './SidePanel.vue';
const props = defineProps<{
  request: (path: string, body?: any) => Promise<any>;
  portal: (path: string, body?: any) => Promise<any>;
}>();
const today = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'America/Toronto',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
}).format(new Date());
const mode = ref('week'),
  week = ref(today),
  from = ref(today),
  to = ref(today),
  page = ref(1);
const result = ref<any>(null),
  busy = ref(false),
  error = ref(''),
  message = ref(''),
  applied = ref('');
const setters = ref<any[]>([]),
  setter = ref(''),
  rosterError = ref('');
const selected = ref<any>(null),
  panelMode = ref('rate'),
  attendance = ref(''),
  bonus = ref(''),
  reason = ref('');
const query = () =>
  new URLSearchParams(
    mode.value === 'week' ? { week_of: week.value } : { from: from.value, to: to.value },
  ).toString();
const changed = computed(() => !!result.value && query() !== applied.value);
const cad = (value: any) =>
  value === null || value === undefined
    ? 'Non défini'
    : new Intl.NumberFormat('fr-CA', { style: 'currency', currency: 'CAD' }).format(Number(value));
const count = (value: any) =>
  value === null || value === undefined
    ? '—'
    : new Intl.NumberFormat('fr-CA', { maximumFractionDigits: 1 }).format(value);
const columns: Record<string, string> = {
  calls: 'Appels Orvia',
  programmed: 'Programmés',
  upcoming: 'À venir',
  attended: 'Tenus déclarés',
  absent: 'Non tenus déclarés',
  reprogrammed: 'Nouvelles occurrences liées',
  sales: 'Ventes déclarées',
  unqualified: 'Fiches non qualifiées avant réservation',
  unqualified_visits: 'Visites déclarées non qualifiées',
  cancelled: 'Annulations simples',
  pending_results: 'Résultats incomplets',
  attendance_credits: 'Présences rémunérables uniques',
  sale_credits: 'Primes uniques',
  attendance_unpriced: 'Présences sans tarif',
  sale_unpriced: 'Ventes sans tarif',
};
async function load(target = 1) {
  if (busy.value) return;
  busy.value = true;
  error.value = '';
  try {
    const criteria = query();
    result.value = await props.request(`isolation-compensation/?${criteria}&page=${target}`);
    applied.value = criteria;
    page.value = target;
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function roster() {
  try {
    const found: any[] = [];
    for (let p = 1; p <= 20; p++) {
      const data = await props.portal(`isolation/setters/?page=${p}`);
      if (
        !Array.isArray(data.results) ||
        !Number.isInteger(data.count) ||
        data.count < 0 ||
        data.count > 500
      )
        throw new Error('Annuaire indisponible');
      found.push(...data.results);
      if (found.length >= data.count) break;
      if (p === 20) throw new Error('Annuaire incomplet.');
    }
    setters.value = found;
  } catch (e: any) {
    rosterError.value = e.message;
  }
}
async function openRate(id: number, action = 'rate', expectedClient?: number) {
  if (busy.value) return;
  busy.value = true;
  error.value = '';
  reason.value = '';
  try {
    const grant = await props.portal('isolation/compensation-proof/', { setter_id: id });
    if (expectedClient && grant.client.id !== expectedClient)
      throw new Error(
        'Ce client n’est plus le client Isolation actif. Son tarif historique reste consultable dans le rapport.',
      );
    const rows = await props.request(
      `isolation-compensation/rates/?setter_id=${id}&client_id=${grant.client.id}`,
    );
    const row = rows.results[0] || { attendance_cad: null, sale_bonus_cad: null, revision: 0 };
    selected.value = {
      ...row,
      setter_id: id,
      setter_name: grant.setter.name,
      client_id: grant.client.id,
      client_name: grant.client.name,
    };
    attendance.value = row.attendance_cad ?? '';
    bonus.value = row.sale_bonus_cad ?? '';
    panelMode.value = action;
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
const dirty = computed(
  () =>
    !!selected.value &&
    (reason.value !== '' ||
      attendance.value !== (selected.value.attendance_cad ?? '') ||
      bonus.value !== (selected.value.sale_bonus_cad ?? '')),
);
function close() {
  if (!busy.value && (!dirty.value || window.confirm('Fermer sans enregistrer cette saisie ?')))
    selected.value = null;
}
async function saveRate() {
  busy.value = true;
  error.value = '';
  try {
    const grant = await props.portal('isolation/compensation-proof/', {
      setter_id: selected.value.setter_id,
    });
    if (grant.client.id !== selected.value.client_id)
      throw new Error('Client modifié : rechargez la fiche de tarif.');
    await props.request('isolation-compensation/rates/', {
      proof: grant.proof,
      attendance_cad: attendance.value === '' ? null : attendance.value,
      sale_bonus_cad: bonus.value === '' ? null : bonus.value,
      revision: selected.value.revision,
      reason: reason.value,
    });
    selected.value = null;
    message.value = 'Tarifs enregistrés. Les montants déjà valorisés sont conservés.';
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
  if (!selected.value) await load(page.value);
}
async function valueMissing() {
  if (!reason.value.trim() || !result.value) return;
  busy.value = true;
  error.value = '';
  try {
    const grant = await props.portal('isolation/compensation-proof/', {
      setter_id: selected.value.setter_id,
    });
    if (grant.client.id !== selected.value.client_id)
      throw new Error('Client modifié : rechargez.');
    const data = await props.request('isolation-compensation/value/', {
      proof: grant.proof,
      rate_revision: selected.value.revision,
      starts_on: String(result.value.from),
      ends_on: String(result.value.to),
      reason: reason.value,
    });
    selected.value = null;
    message.value = `${data.valued} résultat(s) valorisé(s). ${data.remaining} résultat(s) restent à valoriser avec ces tarifs. Les tarifs non définis restent signalés dans le rapport. Les prix existants sont conservés.`;
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
  if (!selected.value) await load(page.value);
}
async function download(kind: string) {
  if (!result.value || changed.value) return;
  busy.value = true;
  error.value = '';
  try {
    const blob = await props.request(`isolation-compensation/?${applied.value}&export=${kind}`);
    const url = URL.createObjectURL(blob),
      link = document.createElement('a');
    link.href = url;
    link.download = `remuneration-isolation-${result.value.from}-${result.value.to}.${kind}`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
onMounted(() => {
  void load();
  void roster();
});
</script>
<template>
  <section class="compensation">
    <p>
      Suivi administratif par setter et client. Montants en dollars canadiens, sans exécution de
      paiement.
    </p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <form class="toolbar" @submit.prevent="load()">
      <fieldset :disabled="busy">
        <label
          >Période<select v-model="mode">
            <option value="week">Une semaine</option>
            <option value="custom">Dates personnalisées</option>
          </select></label
        >
        <label v-if="mode === 'week'"
          >Un jour de la semaine<input v-model="week" type="date" required
        /></label>
        <template v-else
          ><label>Du<input v-model="from" type="date" required /></label
          ><label>Au inclus<input v-model="to" type="date" required /></label
        ></template>
        <button class="primary">Afficher</button><span>Heure du Québec</span>
      </fieldset>
    </form>
    <div class="toolbar">
      <label
        >Configurer un setter<select v-model="setter">
          <option value="">Choisir</option>
          <option v-for="person in setters" :key="person.id" :value="String(person.id)">
            {{ person.name }}
          </option>
        </select></label
      ><button class="secondary" :disabled="busy || !setter" @click="openRate(Number(setter))">
        Régler les tarifs CAD
      </button>
    </div>
    <p v-if="rosterError" role="alert">Annuaire : {{ rosterError }}</p>
    <template v-if="result">
      <p>Du {{ result.from }} au {{ result.to }} inclus · Québec</p>
      <p v-if="changed" role="status">
        Les filtres ont changé. Cliquez sur Afficher pour actualiser le rapport.
      </p>
      <p v-if="!result.calls_available" role="alert">
        Les compteurs d’appels sont momentanément indisponibles. Ils ne sont pas remplacés par zéro.
      </p>
      <div class="totals">
        <article>
          <small>Montant connu · CAD</small><strong>{{ cad(result.totals.amount_cad) }}</strong
          ><span
            >Présences : {{ cad(result.totals.attendance_amount) }} · Primes :
            {{ cad(result.totals.sale_amount) }}</span
          >
        </article>
        <article>
          <small>Crédits uniques</small
          ><strong
            >{{ result.totals.attendance_credits }} présences ·
            {{ result.totals.sale_credits }} ventes</strong
          ><span
            >{{ result.totals.attendance_unpriced }} présences et
            {{ result.totals.sale_unpriced }} ventes sans tarif</span
          >
        </article>
        <article>
          <small>Présence / résultats renseignés</small
          ><strong>{{ count(result.totals.presence_rate) }} %</strong
          ><span>Ventes / tenues : {{ count(result.totals.closing_rate) }} %</span>
        </article>
      </div>
      <p v-if="!result.totals.complete" role="status">
        Le montant connu reste incomplet : des tarifs ou des résultats de visite restent à
        renseigner.
      </p>
      <div class="toolbar">
        <button class="secondary" :disabled="busy || changed" @click="download('csv')">
          Exporter CSV</button
        ><button class="secondary" :disabled="busy || changed" @click="download('xlsx')">
          Exporter Excel
        </button>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Setter / client</th>
              <th v-for="(label, key) in columns" :key="key">{{ label }}</th>
              <th>Présences CAD</th>
              <th>Primes CAD</th>
              <th>Montant connu CAD</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th>Total</th>
              <td v-for="(_, key) in columns" :key="key">{{ count(result.totals[key]) }}</td>
              <td>{{ cad(result.totals.attendance_amount) }}</td>
              <td>{{ cad(result.totals.sale_amount) }}</td>
              <td>{{ cad(result.totals.amount_cad) }}</td>
              <td></td>
            </tr>
            <tr v-for="row in result.groups.results" :key="`${row.client_id}-${row.setter_id}`">
              <th>
                {{ row.setter_name }}<br /><small>{{ row.client_name }}</small>
              </th>
              <td v-for="(_, key) in columns" :key="key">{{ count(row[key]) }}</td>
              <td>{{ cad(row.attendance_amount) }}</td>
              <td>{{ cad(row.sale_amount) }}</td>
              <td>
                {{ cad(row.amount_cad) }}<br /><small v-if="!row.complete">À compléter</small>
              </td>
              <td>
                <button
                  v-if="row.client_id && setters.some((person) => person.id === row.setter_id)"
                  class="secondary"
                  :disabled="busy"
                  @click="openRate(row.setter_id, 'rate', row.client_id)"
                >
                  Tarifs</button
                ><button
                  v-if="
                    row.client_id && result && setters.some((person) => person.id === row.setter_id)
                  "
                  class="secondary"
                  :disabled="busy || changed"
                  @click="openRate(row.setter_id, 'value', row.client_id)"
                >
                  Valoriser les résultats sans tarif
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="toolbar">
        <button class="secondary" :disabled="busy || page === 1 || changed" @click="load(page - 1)">
          Précédent</button
        ><span>{{ result.groups.count }} groupe(s) · page {{ page }}</span
        ><button
          class="secondary"
          :disabled="busy || page * 25 >= result.groups.count || changed"
          @click="load(page + 1)"
        >
          Suivant
        </button>
      </div>
      <details>
        <summary>Définition du rapport</summary>
        <p>{{ result.definition }}</p>
      </details>
    </template>
    <SidePanel
      :open="!!selected"
      :title="
        panelMode === 'rate' ? 'Tarifs du setter · CAD' : 'Valoriser les résultats sans tarif'
      "
      :close-disabled="busy"
      @request-close="close"
    >
      <form v-if="selected" @submit.prevent="panelMode === 'rate' ? saveRate() : valueMissing()">
        <h3>{{ selected.setter_name }} · {{ selected.client_name }}</h3>
        <p v-if="error" role="alert">{{ error }}</p>
        <fieldset :disabled="busy">
          <template v-if="panelMode === 'rate'"
            ><label
              >Montant par visite tenue · CAD<input
                v-model="attendance"
                type="number"
                min="0"
                step="0.01" /></label
            ><label
              >Prime supplémentaire par vente · CAD<input
                v-model="bonus"
                type="number"
                min="0"
                step="0.01"
            /></label>
            <p>
              Laissez vide pour un tarif non défini. Zéro signifie un tarif explicitement nul. Les
              prix déjà conservés sur les résultats ne changent pas.
            </p></template
          >
          <template v-else
            ><p>Période du {{ result?.from }} au {{ result?.to }} (Québec).</p>
            <p>
              Présence : {{ cad(selected.attendance_cad) }} · Prime de vente :
              {{ cad(selected.sale_bonus_cad) }}
            </p>
            <p>
              Applique ces tarifs uniquement aux résultats sans prix, par lots de 200. Les anciens
              prix sont conservés. Une reprogrammation ne génère pas un second crédit pour le même
              processus.
            </p></template
          >
          <label
            >Motif obligatoire<textarea v-model="reason" required maxlength="1000"></textarea>
          </label>
          <button
            class="primary"
            :disabled="
              !reason.trim() ||
              (panelMode === 'value' &&
                selected.attendance_cad === null &&
                selected.sale_bonus_cad === null)
            "
          >
            {{
              panelMode === 'rate' ? 'Enregistrer les tarifs' : 'Valoriser les résultats sans tarif'
            }}
          </button>
        </fieldset>
      </form>
    </SidePanel>
  </section>
</template>
<style scoped>
.compensation {
  display: grid;
  gap: 18px;
}
.toolbar,
fieldset {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: end;
}
label {
  display: grid;
  gap: 6px;
}
form fieldset {
  border: 0;
  padding: 0;
}
.table-wrap {
  overflow-x: auto;
}
th,
td {
  white-space: nowrap;
  vertical-align: top;
}
.totals {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 14px;
}
.totals article {
  display: grid;
  gap: 10px;
  border: 1px solid #dfe5ef;
  border-radius: 14px;
  padding: 18px;
  background: white;
}
strong {
  font-size: 20px;
}
[role='alert'] {
  color: #b42318;
}
form p {
  line-height: 1.6;
}
small {
  color: #68758a;
}
</style>
