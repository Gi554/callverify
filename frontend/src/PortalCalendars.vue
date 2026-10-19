<script setup lang="ts">
import {ref,onMounted} from 'vue'
const props=defineProps<{request:(path:string,body?:any)=>Promise<any>}>()
const rows=ref<any[]>([]),busy=ref(false),error=ref(''),message=ref(''),start=ref(''),end=ref(''),periods=ref<any[]>([]),checkedSpace=ref(''),history=ref<Record<string,any>>({}),password=ref(''),ack=ref(false)
async function load(){rows.value=(await props.request('calendar/')).connections;for(const row of rows.value){try{history.value[row.workspace]=await props.request(`calendar/${row.workspace}/sync/`)}catch{history.value[row.workspace]=null}}}
async function run(action:()=>Promise<void>){busy.value=true;error.value='';try{await action()}catch(e:any){error.value=e.message;periods.value=[];checkedSpace.value=''}finally{busy.value=false}}
async function connect(row:any,provider:string){await run(async()=>{const result=await props.request(`calendar/${row.workspace}/start/`,{provider});location.assign(result.authorization_url)})}
async function disconnect(row:any){await run(async()=>{await props.request(`calendar/${row.workspace}/disconnect/`,{revision:row.revision});message.value='Connexion retirée de AMX. Vous pouvez aussi révoquer le consentement dans votre compte Google ou Microsoft.';periods.value=[];checkedSpace.value='';await load()})}
async function check(row:any){await run(async()=>{checkedSpace.value='';periods.value=[];const result=await props.request(`calendar/${row.workspace}/busy/`,{starts_at:start.value,ends_at:end.value});periods.value=result.busy;checkedSpace.value=row.workspace})}
async function toggle(row:any){await run(async()=>{await props.request(`calendar/${row.workspace}/sync-config/`,{revision:row.revision,enabled:!row.auto_sync});await load()})}
async function sync(row:any){await run(async()=>{const result=await props.request(`calendar/${row.workspace}/sync/`,{});message.value='Vérification terminée : '+countText(result.counts);await load()})}
async function withdraw(row:any){if(!confirm('Retirer les événements AMX de cet agenda et arrêter leur synchronisation ? Les rendez-vous CRM sont conservés.'))return;await run(async()=>{const result=await props.request(`calendar/${row.workspace}/withdraw/`,{confirm:true});message.value='Retrait : '+countText(result.counts)+'. Vérifiez les erreurs avant de déconnecter.';await load()})}
async function detach(row:any){await run(async()=>{try{await props.request(`calendar/${row.workspace}/detach/`,{current_password:password.value,revision:row.revision,confirm_external_cleanup:ack.value});message.value='Nettoyage manuel confirmé. Connexion locale retirée ; aucun événement distant supprimé par cette action.';ack.value=false;await load()}finally{password.value=''}})}
async function page(row:any,url:string){await run(async()=>{const parsed=new URL(url,location.origin);history.value[row.workspace]=await props.request(`calendar/${row.workspace}/sync/${parsed.search}`)})}
const states:Record<string,string>={synced:'Synchronisé',pending:'À reprendre',error:'Erreur',removed:'Retiré',abandoned:'Nettoyage manuel confirmé'}
const errors:Record<string,string>={slot_busy:'Créneau occupé',event_changed:'Événement modifié dans l’agenda : vérification manuelle requise',event_has_attendees:'Participants ajoutés : action automatique bloquée',uncertain_create:'Création non confirmée : vérifiez l’agenda, aucun nouvel envoi automatique',provider_unavailable:'Fournisseur indisponible',source_unavailable:'Rendez-vous CRM indisponible',source_changed:'Rendez-vous modifié pendant la synchronisation',past_source:'Rendez-vous passé'}
function countText(counts:Record<string,number>){return Object.entries(counts).map(([key,n])=>`${states[key]||key} : ${n}`).join(', ')||'Aucun rendez-vous à traiter'}
onMounted(()=>run(load))
</script>
<template>
<section>
  <h3>Mes agendas Google et Microsoft</h3>
  <p>Connexion personnelle du conseiller Assurance ou du client Isolation. Un agenda principal par espace. Retirez les événements AMX avant de changer de compte. Calendly sera traité ultérieurement.</p>
  <p v-if="error" role="alert">{{error}}</p><p v-if="message" role="status">{{message}}</p>
  <button class="secondary" :disabled="busy" @click="run(load)">Actualiser les connexions et résultats</button>
  <p v-if="!rows.length">Votre rôle actuel ne possède pas d’agenda à connecter.</p>
  <article v-for="row in rows" :key="row.workspace">
    <h4>{{row.workspace==='assurance'?'Assurance':'Isolation'}}</h4>
    <p>{{row.connected?`Connecté à ${row.provider==='google'?'Google Calendar':'Microsoft Outlook'} · agenda principal`:'Non connecté'}}</p>
    <button class="secondary" :disabled="busy||!row.configured.google" @click="connect(row,'google')">Connecter Google Calendar</button>
    <button class="secondary" :disabled="busy||!row.configured.microsoft" @click="connect(row,'microsoft')">Connecter Microsoft Outlook</button>
    <p v-if="!row.configured.google||!row.configured.microsoft">Un bouton désactivé indique une configuration OAuth manquante côté serveur.</p>
    <button v-if="row.connected" class="secondary" :disabled="busy" @click="disconnect(row)">Déconnecter cet agenda de AMX</button>
    <form v-if="row.connected" @submit.prevent="check(row)"><fieldset :disabled="busy">
      <legend>Consulter les périodes occupées (31 jours maximum)</legend>
      <label>Début ISO 8601 avec décalage<input v-model="start" placeholder="2026-12-01T00:00:00-05:00" required></label>
      <label>Fin ISO 8601 avec décalage<input v-model="end" placeholder="2026-12-02T00:00:00-05:00" required></label>
      <button class="secondary">Vérifier les disponibilités</button>
    </fieldset></form>
    <section v-if="checkedSpace===row.workspace">
      <p>Consultation réussie : {{periods.length}} période(s) occupée(s). Cette consultation ne réserve rien et ne vérifie pas les autres agendas.</p>
      <p v-for="(period,index) in periods" :key="index">{{new Date(period.start).toLocaleString('fr-FR')}} → {{new Date(period.end).toLocaleString('fr-FR')}}</p>
    </section>
    <section v-if="row.provider">
      <h4>Publication des rendez-vous CRM</h4>
      <p>Synchronisation {{row.auto_sync?'activée':'arrêtée'}}. Le CRM reste la référence. Les changements sont publiés par le worker serveur ou le bouton ci-dessous. Un conflit externe ne supprime pas le rendez-vous interne.</p>
      <button v-if="row.connected" class="secondary" :disabled="busy" @click="toggle(row)">{{row.auto_sync?'Arrêter la synchronisation':'Activer la synchronisation'}}</button>
      <button v-if="row.connected" class="secondary" :disabled="busy||!row.auto_sync" @click="sync(row)">Synchroniser maintenant</button>
      <button v-if="row.connected" class="secondary" :disabled="busy" @click="withdraw(row)">Retirer les événements AMX de cet agenda</button>
      <section v-if="history[row.workspace]">
        <p v-if="!history[row.workspace].count">Aucun événement publié.</p>
        <p v-for="event in history[row.workspace].results" :key="event.source_id">Rendez-vous {{event.source_id}} · {{states[event.status]||event.status}} <span v-if="event.error_code">· {{errors[event.error_code]||'Vérification nécessaire'}}</span> · {{event.checked_at?new Date(event.checked_at).toLocaleString('fr-FR'):'Non vérifié'}}</p>
        <button class="secondary" :disabled="busy||!history[row.workspace].previous" @click="page(row,history[row.workspace].previous)">Précédent</button>
        <button class="secondary" :disabled="busy||!history[row.workspace].next" @click="page(row,history[row.workspace].next)">Suivant</button>
      </section>
      <details><summary>Récupérer une connexion bloquée après nettoyage manuel</summary>
        <p>Si le fournisseur refuse l’accès ou si une création reste incertaine, vérifiez et supprimez vous-même les anciens événements AMX chez Google/Microsoft. Cette confirmation efface la connexion locale et arrête la synchronisation ; elle ne supprime aucun événement distant.</p>
        <form @submit.prevent="detach(row)"><fieldset :disabled="busy">
          <label><input v-model="ack" type="checkbox" required>J’ai vérifié et retiré les anciens événements AMX dans l’agenda externe.</label>
          <label>Mot de passe actuel<input v-model="password" type="password" autocomplete="current-password" required></label>
          <button class="secondary">Confirmer le nettoyage manuel et déconnecter</button>
        </fieldset></form>
      </details>
    </section>
  </article>
  <p>Événements privés, sans participant ni invitation. La publication ne garantit pas une réservation atomique : un autre événement peut être ajouté entre les contrôles. Les modifications dans Google/Microsoft ne mettent pas à jour le CRM. Aucun intitulé privé externe n’est affiché.</p>
</section>
</template>
