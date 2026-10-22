<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { MailPlus, RefreshCw, Send, X, ChevronLeft, ChevronRight, UserRound } from 'lucide-vue-next'
const props = defineProps<{
  space: string
  request: (path: string, body?: any, method?: string) => Promise<any>
}>()
const rows = ref<any[]>([]),
  page = ref(1),
  count = ref(0),
  busy = ref(false),
  error = ref(''),
  message = ref('')
const form = ref({ username: '', email: '', role: 'setter' })
const composing = ref(false),
  loading = ref(false)
const roleLabels: Record<string, string> = {
  setter: 'Setter',
  administrator: 'Administrateur',
  advisor: 'Conseiller',
  client: 'Client',
  closer: 'Closer',
}
function cancel() {
  composing.value = false
  form.value = { username: '', email: '', role: 'setter' }
}
const base = () => `workspaces/${props.space}/invitations/`
async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await props.request(base() + `?page=${page.value}`)
    rows.value = data.results
    count.value = data.count
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
async function create() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    const result = await props.request(base(), { ...form.value })
    cancel()
    page.value = 1
    await load()
    message.value = result.mail_queued
      ? 'Invitation mise en file d’envoi.'
      : 'Invitation enregistrée, mais e-mail non envoyé. Vous pouvez réessayer.'
  } catch (e: any) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
async function action(row: any, action: string) {
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    const result = await props.request(base() + row.id + '/', { action })
    message.value =
      action === 'revoke'
        ? 'Invitation révoquée.'
        : result.mail_queued
          ? 'Nouveau lien mis en file ; le précédent est invalidé.'
          : 'Envoi échoué ; réessayez.'
    await load()
  } catch (e: any) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
const labels: Record<string, string> = {
  pending: 'En attente',
  accepted: 'Acceptée',
  revoked: 'Révoquée',
  expired: 'Expirée',
}
onMounted(load)
</script>
<!-- prettier-ignore -->
<template>
 <section class="invitations">
  <header class="invitation-heading"><div><h2>Invitations</h2><p>Invitez un utilisateur dans l’espace {{space==='assurance'?'Assurance':'Isolation'}}.</p></div><button class="primary" :disabled="busy||loading||composing" @click="composing=true"><MailPlus :size="17"/>Nouvelle invitation</button></header>
  <p v-if="error" role="alert" class="invitation-error">{{error}}</p><p v-if="message" role="status" class="invitation-notice">{{message}}</p>
  <form v-if="composing" class="invitation-form" @submit.prevent="create">
   <div class="form-heading"><h3>Nouvelle invitation</h3><button type="button" class="secondary" :disabled="busy" aria-label="Fermer le formulaire" @click="cancel"><X :size="16"/></button></div>
   <p>Le destinataire choisira son mot de passe. Son accès sera activé après acceptation.</p>
   <fieldset :disabled="busy"><label>Identifiant<input v-model="form.username" required maxlength="150" autocomplete="off"></label><label>Adresse e-mail<input v-model="form.email" type="email" required maxlength="254" autocomplete="off"></label><label>Rôle dans cet espace<select v-model="form.role"><option value="setter">Setter</option><option value="administrator">Administrateur</option><option v-if="space==='assurance'" value="advisor">Conseiller</option><template v-else><option value="client">Client</option><option value="closer">Closer</option></template></select></label></fieldset>
   <div class="form-actions"><button type="button" class="secondary" :disabled="busy" @click="cancel">Annuler</button><button class="primary" :disabled="busy||loading"><Send :size="16"/>{{busy?'Enregistrement…':'Envoyer l’invitation'}}</button></div>
  </form>
  <div class="invitation-summary"><span role="status">{{loading?'Chargement…':`${count} invitation(s)`}}</span><button class="secondary" :disabled="busy||loading" @click="load"><RefreshCw :size="15"/>Actualiser</button></div>
  <div class="table-scroll" :aria-busy="loading"><table><thead><tr><th>Destinataire</th><th>Rôle</th><th>État</th><th>Actions</th></tr></thead><tbody>
   <tr v-for="row in rows" :key="row.id"><td><div class="recipient"><span class="recipient-icon"><UserRound :size="17"/></span><div><strong>{{row.username}}</strong><small>{{row.email}}</small></div></div></td><td>{{roleLabels[row.role]||row.role}}</td><td><span class="invitation-status" :class="row.status">{{labels[row.status]||row.status}}</span></td><td><div v-if="['pending','expired'].includes(row.status)" class="invitation-actions"><button class="secondary" :disabled="busy||loading" :aria-label="'Renvoyer l’invitation à '+row.username" @click="action(row,'resend')"><Send :size="15"/>Renvoyer</button><button class="secondary revoke" :disabled="busy||loading" :aria-label="'Révoquer l’invitation de '+row.username" @click="action(row,'revoke')"><X :size="15"/>Révoquer</button></div><span v-else class="closed">Clôturée</span></td></tr>
   <tr v-if="!rows.length"><td colspan="4" class="invitation-empty">{{loading?'Chargement des invitations…':error?'Impossible de charger les invitations. Réessayez avec Actualiser.':'Aucune invitation dans cet espace.'}}</td></tr>
  </tbody></table></div>
  <footer class="invitation-pagination"><span>Page {{page}} / {{Math.max(1,Math.ceil(count/25))}}</span><button class="secondary" :disabled="busy||loading||page===1" @click="page--;load()"><ChevronLeft :size="16"/>Précédent</button><button class="secondary" :disabled="busy||loading||page*25>=count" @click="page++;load()">Suivant<ChevronRight :size="16"/></button></footer>
 </section>
</template>
<style scoped>
.invitations {
  color: #29394e;
}
.invitation-heading,
.form-heading,
.form-actions,
.invitation-summary,
.invitation-pagination,
.invitation-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.invitation-heading {
  margin-bottom: 22px;
}
.invitation-heading h2 {
  font-size: 19px;
  margin: 0;
}
.invitation-heading p,
.invitation-form p {
  font-size: 13px;
  color: #718096;
  line-height: 1.6;
}
.invitation-form {
  display: block !important;
  background: #f6f9fc;
  border: 1px solid #dce5ef;
  border-radius: 8px;
  padding: 22px;
  margin-bottom: 24px;
}
.form-heading h3 {
  margin: 0;
  font-size: 16px;
}
.invitation-form fieldset {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
  border: 0;
  padding: 0;
  margin: 20px 0;
}
.invitation-form select {
  padding: 12px;
  background: white;
  border: 1px solid #dbe3ec;
  border-radius: 5px;
  color: #34445b;
}
.form-actions {
  justify-content: flex-end;
}
.invitation-summary {
  padding: 12px 16px;
  background: #eef5fc;
  font-size: 12px;
}
.recipient {
  display: flex;
  align-items: center;
  gap: 12px;
}
.recipient-icon {
  display: grid;
  place-items: center;
  flex-shrink: 0;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: #edf2fb;
  color: #587dab;
}
.recipient small {
  display: block;
  color: #738196;
  margin-top: 5px;
}
.invitation-status {
  padding: 5px 10px;
  border-radius: 14px;
  font-size: 12px;
  white-space: nowrap;
  background: #f0f2f5;
  color: #657185;
}
.invitation-status.pending {
  background: #fff4dc;
  color: #916315;
}
.invitation-status.accepted {
  background: #e6f5ed;
  color: #24744c;
}
.invitation-status.expired {
  background: #fff0e6;
  color: #a15b26;
}
.invitation-actions {
  justify-content: flex-start;
  gap: 8px;
}
.invitation-actions .revoke {
  color: #a24b49;
}
.closed {
  color: #7c899a;
  font-size: 12px;
}
.invitation-pagination {
  justify-content: flex-end;
  margin-top: 18px;
  font-size: 12px;
}
.invitation-pagination > span {
  margin-right: auto;
}
.invitation-empty {
  text-align: center;
  padding: 36px !important;
  color: #718096;
}
.invitation-error,
.invitation-notice {
  padding: 14px;
  border-radius: 6px;
  font-size: 13px;
}
.invitation-error {
  background: #fff0ef;
  color: #9b3f3a;
}
.invitation-notice {
  background: #edf5ff;
  color: #34638e;
}
.invitations button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
@media (max-width: 750px) {
  .invitation-form fieldset {
    grid-template-columns: 1fr;
  }
  .invitation-form {
    padding: 16px;
  }
}
</style>
