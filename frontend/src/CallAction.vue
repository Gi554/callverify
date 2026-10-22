<script setup lang="ts">
import {ref,computed,nextTick,onMounted,watch} from 'vue'
import {Phone,RefreshCw} from 'lucide-vue-next'
const props=defineProps<{workspace:'assurance'|'isolation';resourceId:number;phone:string;disabled?:boolean;autoOpen?:boolean;beforeOpen?:()=>Promise<void>;prepare:(id:string)=>Promise<{proof:string}>;portal:(path:string,body?:any)=>Promise<any>}>()
const emit=defineEmits<{busy:[value:boolean]}>()
const key=`amx-call:${props.workspace}:${props.resourceId}`
const pending=ref(false),confirming=ref(false),error=ref(''),result=ref<any>(null),requestId=ref('')
const confirmedPhone=ref('')
watch(pending,value=>emit('busy',value),{flush:'sync'})
try{requestId.value=sessionStorage.getItem(key)||''}catch{/* Memory state still prevents an automatic retry. */}
const labels:Record<string,string>={accepted:'Commande acceptée',rejected:'Commande refusée',blocked:'Appel bloqué par les contrôles',unknown:'Résultat indéterminé',dispatching:'Commande réservée, résultat à vérifier'}
const unresolved=computed(()=>!!requestId.value&&!['accepted','rejected','blocked'].includes(result.value?.state))
function remember(id:string){requestId.value=id;try{if(id)sessionStorage.setItem(key,id);else sessionStorage.removeItem(key)}catch{}}
async function open(){
 if(pending.value)return
 pending.value=true;error.value=''
 try{
  await props.beforeOpen?.();await nextTick()
  const state=await props.portal(`${props.workspace}/calls/options/`)
  if(!state.enabled)throw new Error('Les appels sont désactivés pour cet espace.')
  if(!state.post_associated)throw new Error('Un administrateur doit associer votre poste Phonetico à votre compte.')
  confirmedPhone.value=props.phone;confirming.value=true
 }catch(e:any){error.value=e.message}finally{pending.value=false}
}
async function send(){
 if(pending.value||unresolved.value)return
 pending.value=true;error.value='';confirming.value=false;result.value=null
 const id=crypto.randomUUID();let submitted=false
 try{
  const intent=await props.prepare(id)
  await nextTick()
  if(props.phone!==confirmedPhone.value)throw new Error('Le numéro a changé. Vérifiez-le et confirmez à nouveau.')
  // Persist before POST. An interrupted response can only be inspected by GET.
  remember(id);submitted=true
  result.value=await props.portal(`${props.workspace}/calls/`,{proof:intent.proof})
 }catch(e:any){error.value=e.message;if(!submitted)remember('')}
 finally{pending.value=false}
}
async function inspect(){
 if(!requestId.value||pending.value)return
 pending.value=true;error.value=''
 try{result.value=await props.portal(`${props.workspace}/calls/${requestId.value}/`)}
 catch(e:any){error.value=e.message+' Aucun nouvel appel n’a été envoyé.'}
 finally{pending.value=false}
}
function reset(){if(unresolved.value||pending.value)return;remember('');result.value=null;error.value=''}
onMounted(()=>{if(props.autoOpen&&!requestId.value)void open()})
</script>
<template>
 <div class="call-action">
  <button v-if="!requestId" type="button" class="secondary" :disabled="disabled||pending" @click="open"><Phone :size="16"/> Appeler</button>
  <section v-if="confirming" class="call-confirm" aria-label="Confirmer l’appel">
   <strong>Appeler {{confirmedPhone}}</strong><p>Votre poste Phonetico sonnera d’abord. Décrochez : la composition du numéro extérieur démarre ensuite. Le son passe par votre téléphone ou softphone.</p>
   <button type="button" class="primary" :disabled="disabled||pending" @click="send">Confirmer l’appel</button>
   <button type="button" class="secondary" @click="confirming=false">Annuler</button>
  </section>
  <p v-if="pending" role="status">Traitement de la demande…</p>
  <p v-if="result" role="status">{{labels[result.state]||'État inconnu'}}. {{result.definition||'Une acceptation ne prouve ni sonnerie distante ni décrochage.'}}</p>
  <p v-if="error" role="alert">{{error}}</p>
  <template v-if="requestId">
   <small>Référence de commande : {{requestId}}</small>
   <p v-if="unresolved">Vérifiez cette commande avant toute nouvelle tentative. Aucune relance automatique.</p>
   <button type="button" class="secondary" :disabled="pending" @click="inspect"><RefreshCw :size="14"/> Vérifier la commande</button>
   <button v-if="!unresolved" type="button" class="secondary" :disabled="pending" @click="reset">Préparer un nouvel appel</button>
  </template>
 </div>
</template>
<style scoped>
.call-action{margin:12px 0}.call-action button{display:inline-flex;align-items:center;gap:7px;margin:4px}.call-confirm{padding:16px;border:1px solid var(--border,#dedfd3);border-radius:12px}.call-action small{display:block;overflow-wrap:anywhere}
</style>
