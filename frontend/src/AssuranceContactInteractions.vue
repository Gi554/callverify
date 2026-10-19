<script setup lang="ts">
import {ref,onMounted} from 'vue'
const props=defineProps<{contactId:number;request:(path:string,body?:any,method?:string)=>Promise<any>}>()
const rows=ref<any[]>([]),page=ref(1),count=ref(0),kind=ref(''),after=ref(''),before=ref(''),busy=ref(false),error=ref('')
const labels:Record<string,string>={note:'Note ajoutée',document:'Document ajouté',appointment:'Rendez-vous enregistré',report:'Compte rendu enregistré',incident:'Signalement ajouté'}
const states:Record<string,string>={internal:'Interne',advisor:'Personnel conseiller',scheduled:'Planifié',cancelled:'Annulé',performed:'Effectué',not_performed:'Non effectué',reported:'Signalé'}
async function load(reset=false){if(reset)page.value=1;busy.value=true;error.value='';rows.value=[];try{const query=new URLSearchParams({page:String(page.value)});if(kind.value)query.set('type',kind.value);if(after.value)query.set('after',after.value);if(before.value)query.set('before',before.value);const data=await props.request(`contacts/${props.contactId}/interactions/?${query}`);rows.value=data.results;count.value=data.count}catch(e:any){error.value=e.message;count.value=0}finally{busy.value=false}}
onMounted(()=>load())
</script>
<template><section><h3>Historique des interactions</h3>
<p>Ajouts enregistrés, du plus récent au plus ancien, limités à vos droits. L’état des rendez-vous est leur état actuel. Les reports, annulations et changements commerciaux détaillés restent dans leurs journaux ; les appels Phonetico ne sont pas encore intégrés.</p>
<form @submit.prevent="load(true)"><fieldset :disabled="busy"><label>Type<select v-model="kind"><option value="">Tous</option><option v-for="(label,key) in labels" :key="key" :value="key">{{label}}</option></select></label><label>Depuis (ISO 8601 avec décalage)<input v-model="after" placeholder="2026-10-01T00:00:00-04:00"></label><label>Jusqu’au (ISO 8601 avec décalage)<input v-model="before" placeholder="2026-11-01T00:00:00-04:00"></label><button class="secondary">Filtrer / actualiser</button></fieldset></form>
<p v-if="error" role="alert">{{error}}</p><p v-if="!busy&&!error&&!rows.length">Aucune interaction accessible pour ces filtres.</p>
<article v-for="entry in rows" :key="entry.event_type+':'+entry.event_id"><strong>{{labels[entry.event_type]}}</strong> · {{new Date(entry.occurred_at).toLocaleString('fr-FR')}}<p>Référence {{entry.reference_id}} · {{states[entry.state]||entry.state}}</p><p style="white-space:pre-wrap;overflow-wrap:anywhere">{{entry.detail}}</p></article>
<button class="secondary" :disabled="busy||page===1" @click="page--;load()">Précédent</button> Page {{page}} · {{count}} résultat(s) <button class="secondary" :disabled="busy||page*25>=count" @click="page++;load()">Suivant</button>
</section></template>
