<script setup lang="ts">
import {computed,ref,onMounted,onBeforeUnmount} from 'vue'
import CallAction from './CallAction.vue'
import AssuranceAppointments from './AssuranceAppointments.vue'
import AssuranceAgreements from './AssuranceAgreements.vue'
import AssuranceContactInteractions from './AssuranceContactInteractions.vue'
import AssuranceContactNotes from './AssuranceContactNotes.vue'
import AssuranceContactDocuments from './AssuranceContactDocuments.vue'
import AssuranceCustomValues from './AssuranceCustomValues.vue'
import AssuranceSharedFields from './AssuranceSharedFields.vue'
const props=defineProps<{contact:any;role:string;portal:(path:string,body?:any)=>Promise<any>;request:(path:string,body?:any,method?:string)=>Promise<any>}>()
const emit=defineEmits<{close:[];changed:[]}>()
const detailTab=ref('notes')
const current=ref({...props.contact}),draft=ref({name:props.contact.name,phone:props.contact.phone,email:props.contact.email})
const base=ref({...draft.value}),token=ref(''),expires=ref(''),locked=ref(false),mine=ref(false),busy=ref(false),saving=ref(false),error=ref(''),message=ref(''),reason=ref('')
const history=ref<any[]>([]),historyPage=ref(1),historyCount=ref(0),showHistory=ref(false)
const canWrite=computed(()=>['setter','administrator'].includes(props.role))
const pipeline=ref<any>(null),nextStatus=ref(current.value.status),statusReason=ref('')
async function loadPipeline(){try{pipeline.value=await props.request('pipeline/')}catch(e:any){fail(e)}}
async function changeStatus(){
 if(saveTimer)clearTimeout(saveTimer)
 if(!(await persist()))return
 busy.value=true;error.value=''
 try{current.value=await props.request(endpoint+'commercial-status/',{token:token.value,revision:current.value.revision,pipeline_revision:pipeline.value.revision,status:nextStatus.value,reason:statusReason.value});statusReason.value='';message.value='Statut commercial enregistré.';emit('changed')}catch(e:any){fail(e)}finally{busy.value=false}
}
const dirty=computed(()=>Object.keys(draft.value).some(key=>draft.value[key as keyof typeof draft.value]!==base.value[key as keyof typeof base.value]))
const endpoint=`contacts/${props.contact.id}/`
let lastActivity=Date.now(),saveTimer:ReturnType<typeof setTimeout>|undefined,pulseTimer:ReturnType<typeof setInterval>|undefined,disposed=false,pendingSave:Promise<boolean>|null=null
function fail(e:any){error.value=e.message;message.value='';if(e.status===409){token.value='';message.value='Votre verrou ou votre version n’est plus valable. Reprenez la fiche pour la recharger.'}}
async function refreshLock(){if(!canWrite.value)return;const state=await props.request(endpoint+'lease/');locked.value=state.locked;mine.value=state.mine;expires.value=state.expires_at||''}
async function claim(){busy.value=true;error.value='';message.value='';try{const lease=await props.request(endpoint+'lease/',{});token.value=lease.token;expires.value=lease.expires_at;lastActivity=Date.now();current.value=await props.request(endpoint);draft.value={name:current.value.name,phone:current.value.phone,email:current.value.email};base.value={...draft.value};locked.value=true;mine.value=true;message.value='Fiche prise en charge. Sauvegarde automatique activée.'}catch(e:any){fail(e)}finally{busy.value=false}}
async function persist():Promise<boolean>{
 if(pendingSave)return pendingSave
 if(!dirty.value)return true
 if(!token.value){error.value='Reprenez la fiche avant de modifier.';return false}
 const changes={...draft.value},leaseToken=token.value
 saving.value=true;error.value='';message.value='Enregistrement…'
 pendingSave=(async()=>{try{const result=await props.request(endpoint,{...changes,revision:current.value.revision,token:leaseToken},'PATCH');current.value=result;base.value=changes;message.value='Modifications enregistrées.';emit('changed');return true}catch(e:any){fail(e);return false}finally{saving.value=false;pendingSave=null}})()
 const success=await pendingSave
 if(success&&dirty.value&&!disposed)schedule()
 return success
}
function schedule(){if(saveTimer)clearTimeout(saveTimer);saveTimer=setTimeout(()=>{void persist()},1200)}
function activity(){lastActivity=Date.now()}
function edited(){activity();schedule()}
async function prepareCall(){
 if(saveTimer)clearTimeout(saveTimer)
 if(!(await persist())||!token.value||dirty.value)throw new Error('Enregistrez et prenez en charge la fiche avant l’appel.')
}
async function callIntent(id:string){
 if(saveTimer)clearTimeout(saveTimer)
 if(!(await persist())||!token.value||dirty.value)throw new Error('Enregistrez et prenez en charge la fiche avant l’appel.')
 return props.request(endpoint+'call-intent/',{request_id:id,token:token.value,contact_revision:current.value.revision})
}
async function release(){if(saveTimer)clearTimeout(saveTimer);if(pendingSave&&!(await pendingSave))return false;if(dirty.value&&!(await persist()))return false;if(!token.value)return true;try{await props.request(endpoint+'lease/',{token:token.value},'DELETE');token.value='';await refreshLock();message.value='Fiche libérée.';return true}catch(e:any){fail(e);return false}}
async function close(){busy.value=true;if(await release())emit('close');busy.value=false}
async function pulse(){if(!token.value||busy.value||saving.value)return;if(Date.now()>=Date.parse(expires.value)){token.value='';message.value='Verrou expiré après inactivité. Reprenez la fiche pour continuer.';return}if(document.visibilityState!=='visible'||Date.now()-lastActivity>120000)return;try{const lease=await props.request(endpoint+'lease/',{token:token.value},'PATCH');expires.value=lease.expires_at}catch(e:any){fail(e)}}
async function unlock(){busy.value=true;error.value='';try{await props.request(endpoint+'unlock/',{reason:reason.value});token.value='';reason.value='';await refreshLock();message.value='Déverrouillage administrateur enregistré.'}catch(e:any){fail(e)}finally{busy.value=false}}
async function loadHistory(){error.value='';try{const result=await props.request(endpoint+'history/?page='+historyPage.value);history.value=result.results;historyCount.value=result.count;showHistory.value=true}catch(e:any){fail(e)}}
onMounted(async()=>{try{await refreshLock();if(canWrite.value)await loadPipeline()}catch(e:any){fail(e)}pulseTimer=setInterval(()=>{void pulse()},30000)})
onBeforeUnmount(()=>{disposed=true;if(saveTimer)clearTimeout(saveTimer);if(pulseTimer)clearInterval(pulseTimer);const activeToken=token.value;const finish=pendingSave||Promise.resolve(true);void finish.then(()=>{if(activeToken)return props.request(endpoint+'lease/',{token:activeToken},'DELETE')}).catch(()=>{})})
</script>
<template>
<section class="contact-editor" aria-label="Fiche contact" @pointerdown="activity" @keydown="activity">
 <header class="record-header"><button class="secondary" :disabled="busy||saving" @click="close">← Contacts</button><div><h3>{{current.name||'Contact sans nom'}}</h3><span>{{current.status_label||current.status}}</span></div><small>Dossier #{{current.id}}</small></header>
 <p v-if="error" role="alert" class="error record-feedback">{{error}}</p><p v-if="message" role="status" class="record-feedback">{{message}}</p>
 <div class="record-columns">
  <aside class="record-information"><div class="record-panel-title">Informations du contact</div><div class="record-panel-body">
<template v-if="canWrite"><p>{{token?'Vous avez la prise en charge de cette fiche.':locked?(mine?'Fiche prise en charge dans une autre session de votre compte.':'Fiche prise en charge par un autre utilisateur. Lecture seule disponible.'):'Cette fiche est disponible.'}}</p><p v-if="expires" class="subtle">Expiration du verrou : {{new Date(expires).toLocaleTimeString('fr-FR')}}. Renouvellement pendant votre activité.</p><button v-if="!token" class="primary" :disabled="busy" @click="claim">Prendre en charge / actualiser</button><button v-else class="secondary" :disabled="busy||saving" @click="release">Enregistrer et libérer</button></template>
<CallAction v-if="role==='setter'" workspace="assurance" :resource-id="current.id" :phone="current.phone" :portal="portal" :prepare="callIntent" :before-open="prepareCall" :disabled="!token||busy||saving"/>
<form @submit.prevent="persist" @input="edited"><label>Nom<input v-model="draft.name" :readonly="!token||busy" maxlength="250"></label><label>Téléphone fourni<input v-model="draft.phone" :readonly="!token||busy" maxlength="250" required></label><label>E-mail fourni<input v-model="draft.email" :readonly="!token||busy" maxlength="254"></label><p>Statut : {{current.status_label||current.status}} · version {{current.revision}}</p><button v-if="token" class="primary" :disabled="busy||saving||!dirty">{{saving?'Enregistrement…':'Enregistrer maintenant'}}</button></form>
<button v-if="!token&&dirty" class="secondary" @click="emit('close')">Fermer sans enregistrer les changements locaux</button><template v-if="role==='administrator'"><form class="unlock-form" @submit.prevent="unlock"><label>Motif du déverrouillage forcé<input v-model="reason" maxlength="1000" required></label><button class="secondary" :disabled="busy||saving||!!token||!reason.trim()">Déverrouiller la fiche</button></form><button class="secondary" @click="historyPage=1;loadHistory()">Consulter l’historique administrateur</button><div v-if="showHistory"><p v-if="!history.length">Aucune modification enregistrée.</p><article v-for="entry in history" :key="entry.id"><strong>{{entry.action}}</strong><small>{{new Date(entry.created_at).toLocaleString('fr-FR')}} · utilisateur interne {{entry.actor_id}}</small><pre>{{JSON.stringify(entry.metadata,null,2)}}</pre></article><div class="history-pages"><button class="secondary" :disabled="historyPage===1" @click="historyPage--;loadHistory()">Précédent</button><span>Page {{historyPage}}</span><button class="secondary" :disabled="historyPage*25>=historyCount" @click="historyPage++;loadHistory()">Suivant</button></div></div></template>
<AssuranceSharedFields v-if="role==='advisor'" :contact-id="current.id" :request="request"/>
<AssuranceCustomValues v-if="canWrite" :contact-id="current.id" :lease-token="token" :blocked="busy||saving" :request="request" @saved="current.revision=$event;emit('changed')"/>
<section v-if="canWrite"><h3>Statut commercial : {{current.status_label||current.status}}</h3><p>Le statut ne remplace pas le compte rendu d’un rendez-vous ni l’enregistrement d’un contrat.</p><form v-if="pipeline" @submit.prevent="changeStatus"><label>Nouveau statut<select v-model="nextStatus" :disabled="!token||busy||saving"><option v-for="stage in pipeline.stages.filter((s:any)=>s.active)" :key="stage.key" :value="stage.key">{{stage.label}}</option></select></label><label>Motif du changement<textarea v-model="statusReason" maxlength="1000" required :disabled="!token||busy||saving"></textarea></label><button class="primary" :disabled="!token||busy||saving||nextStatus===current.status">Enregistrer le statut</button></form><button class="secondary" :disabled="busy||saving" @click="loadPipeline">Recharger les statuts disponibles</button></section>
</div></aside>
  <main class="record-timeline"><div class="record-panel-title">Activité du dossier</div><div class="record-panel-body"><AssuranceContactInteractions :contact-id="current.id" :request="request"/>
</div></main>
  <aside class="record-actions"><nav class="record-tabs" aria-label="Actions du dossier"><button :class="{active:detailTab==='notes'}" @click="detailTab='notes'">Notes</button><button :class="{active:detailTab==='documents'}" @click="detailTab='documents'">Documents</button><button :class="{active:detailTab==='appointments'}" @click="detailTab='appointments'">RDV</button><button v-if="role==='administrator'" :class="{active:detailTab==='agreements'}" @click="detailTab='agreements'">Contrats</button></nav><div class="record-panel-body">
   <div v-show="detailTab==='notes'"><AssuranceContactNotes :contact-id="current.id" :lease-token="token" :role="role" :request="request"/>
</div>
   <div v-show="detailTab==='documents'"><AssuranceContactDocuments :contact-id="current.id" :lease-token="token" :role="role" :request="request"/>
</div>
   <div v-show="detailTab==='appointments'"><AssuranceAppointments :contact-id="current.id" :lease-token="token" :role="role" :request="request" :portal="portal"/>
</div>
   <div v-if="role==='administrator'" v-show="detailTab==='agreements'"><AssuranceAgreements v-if="role==='administrator'" :contact-id="current.id" :contact-revision="current.revision" :lease-token="token" :blocked="busy||saving" :request="request" @saved="current.revision=$event;emit('changed')"/>
</div>
  </div></aside>
 </div>
</section>
</template>
<style scoped>
.contact-editor{padding:24px;border:1px solid #dfe2ce;border-radius:16px;margin:24px 0;background:#f8f8f0}.contact-editor form{display:grid;gap:16px;margin:24px 0}.contact-editor input[readonly]{background:#f1f1e9;color:#727763}.contact-editor article{border-top:1px solid #ddd;padding:16px 0}.contact-editor small{display:block;margin-top:8px}.contact-editor pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}.history-pages{display:flex;align-items:center;gap:12px}.contact-editor button:disabled{opacity:.5;cursor:not-allowed}

.contact-editor{padding:0;background:#fff;border-radius:8px;margin:0;overflow:hidden}.record-header{display:flex;align-items:center;gap:16px;padding:16px 20px;border-bottom:1px solid #e2e5dd;background:#fff}.record-header>div{flex:1}.record-header h3{font-size:16px;margin:0 0 5px}.record-header span{font-size:11px;color:#3974b7}.record-header small{color:#64748b;font-size:11px}.record-feedback{margin:0;padding:12px 20px;background:#f6f7ef}.record-columns{display:grid;grid-template-columns:minmax(245px,.85fr) minmax(300px,1.15fr) minmax(280px,1fr);align-items:start}.record-information,.record-timeline,.record-actions{min-width:0;min-height:65vh}.record-information,.record-timeline{border-right:1px solid #e3e7dd}.record-panel-title{height:49px;display:flex;align-items:center;padding:0 18px;font-size:12px;font-weight:650;border-bottom:1px solid #e3e7dd}.record-panel-body{padding:18px}.record-tabs{display:flex;min-height:49px;border-bottom:1px solid #e3e7dd;overflow:auto}.record-tabs button{border:0;border-bottom:2px solid transparent;background:none;padding:14px 12px;color:#7c8572;font-size:11px;cursor:pointer}.record-tabs button.active{color:#2563a6;border-bottom-color:#2563a6;font-weight:650}.record-panel-body :deep(h3){font-size:14px!important;margin-top:0}.record-panel-body :deep(p){font-size:12px;line-height:1.6;color:#64748b}.record-panel-body :deep(form){display:grid;grid-template-columns:1fr;gap:12px;margin:18px 0}.record-panel-body :deep(fieldset){min-width:0;display:grid;gap:10px}.record-panel-body :deep(input),.record-panel-body :deep(select),.record-panel-body :deep(textarea){width:100%;font-size:12px;padding:10px;border-radius:6px}.record-panel-body :deep(button){font-size:11px;padding:9px 12px}.record-panel-body :deep(article){box-shadow:none;border-radius:6px;padding:12px}.record-panel-body :deep(label){font-size:11px}.record-panel-body :deep(table){min-width:560px}.record-panel-body :deep(section){min-width:0}.record-panel-body :deep(.table-scroll){overflow:auto}
@media(max-width:1150px){.record-columns{grid-template-columns:280px minmax(0,1fr)}.record-actions{grid-column:1/-1;border-top:1px solid #e3e7dd;min-height:0}.record-timeline{border-right:0}.record-information{min-height:0}}@media(max-width:650px){.record-columns{display:block}.record-information,.record-timeline{border-right:0;border-bottom:1px solid #e3e7dd;min-height:0}.record-header{gap:10px;padding:12px}.record-header small{display:none}}
</style>
