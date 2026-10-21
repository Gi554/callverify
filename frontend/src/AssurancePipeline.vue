<script setup lang="ts">
import {onMounted,onBeforeUnmount,ref,computed} from 'vue'
import {Search,RefreshCw,ArrowUpRight,Phone,Mail} from 'lucide-vue-next'
import AssuranceContactEditor from './AssuranceContactEditor.vue'
const props=defineProps<{request:(path:string,body?:any,method?:string)=>Promise<any>;portal:(path:string,body?:any)=>Promise<any>;role:string}>()
type Column={key:string;label:string;active:boolean;rows:any[];count:number;page:number;next:boolean;busy:boolean;error:string}
const columns=ref<Column[]>([]),search=ref(''),applied=ref(''),busy=ref(false),error=ref(''),selected=ref<any>(null)
let version=0
const total=computed(()=>columns.value.reduce((sum,column)=>sum+column.count,0))
const incomplete=computed(()=>columns.value.some(column=>column.error))
const opening=ref(false)
onBeforeUnmount(()=>{version++})
async function loadColumn(column:Column,generation:number,append=false){
 column.busy=true;column.error=''
 const page=append?column.page+1:1
 try{const data=await props.request(`contacts/?status=${encodeURIComponent(column.key)}&search=${encodeURIComponent(applied.value)}&page=${page}`)
  if(generation!==version)return
  column.rows=append?[...column.rows,...data.results]:data.results;column.count=data.count;column.page=page;column.next=!!data.next
 }catch(e:any){if(generation===version)column.error=e.message}finally{if(generation===version)column.busy=false}
}
async function load(){
 const generation=++version;busy.value=true;error.value='';applied.value=search.value.trim()
 try{const data=await props.request('pipeline/');if(generation!==version)return
  columns.value=data.stages.map((stage:any)=>({...stage,rows:[],count:0,page:0,next:false,busy:true,error:''}))
  // Bound parallel requests even when administrators configure thirty stages.
  const queue=[...columns.value]
  await Promise.all(Array.from({length:3},async()=>{while(queue.length&&generation===version){await loadColumn(queue.shift()!,generation)}}))
 }catch(e:any){if(generation===version)error.value=e.message}finally{if(generation===version)busy.value=false}
}
async function open(id:number){if(opening.value)return;opening.value=true;error.value='';try{selected.value=await props.request(`contacts/${id}/`)}catch(e:any){error.value=e.message}finally{opening.value=false}}
onMounted(load)
</script>
<template>
 <section class="pipeline">
  <p v-if="error" role="alert" class="error">{{error}}</p>
  <AssuranceContactEditor v-if="selected" :key="selected.id" :contact="selected" :portal="portal" :request="request" :role="role" @close="selected=null;load()" @changed="load"/>
  <template v-else>
   <header class="pipeline-navigation"><h2>Opportunités</h2><span>Pipeline commercial</span></header>
   <div class="pipeline-context"><strong>Assurance</strong><span class="pipeline-total" role="status">{{busy?'Chargement…':`${total} opportunités${incomplete?' · résultat partiel':''}`}}</span></div>
   <form class="pipeline-toolbar" @submit.prevent="load">
    <p>Ouvrez une fiche pour modifier son statut.</p>
    <label><Search :size="17"/><input v-model="search" aria-label="Rechercher des opportunités" placeholder="Nom, téléphone ou e-mail"></label>
    <button class="primary" :disabled="busy">Rechercher</button>
    <button type="button" class="secondary" :disabled="busy" aria-label="Actualiser le pipeline" @click="load"><RefreshCw :size="17"/></button>
   </form>
   <p v-if="busy" role="status">Chargement du pipeline…</p>
   <div class="pipeline-board" role="region" tabindex="0" aria-label="Opportunités par statut commercial, défilement horizontal">
    <section v-for="(column,index) in columns" :key="column.key" class="pipeline-column" :style="{'--stage-color':['#299ed0','#e4b94f','#9290cf','#63a69c','#5f8fda'][index%5]}">
     <header><h3>{{column.label}} <small v-if="!column.active">Archivé</small></h3><span>{{column.busy&&column.page===0?'…':column.count}} contact(s)</span></header>
     <div class="pipeline-cards">
      <p v-if="column.error" role="alert">{{column.error}} <button class="secondary" @click="loadColumn(column,version,column.page>0)">Réessayer</button></p>
      <article v-for="row in column.rows" :key="row.id" class="pipeline-card">
       <button class="pipeline-name" :disabled="opening" @click="open(row.id)"><strong>{{row.name||'Sans nom'}}</strong><ArrowUpRight :size="16"/></button>
       <p><Phone :size="14"/>{{row.phone||'Téléphone non renseigné'}}</p><p v-if="row.email"><Mail :size="14"/>{{row.email}}</p>
       <footer><span>Mis à jour {{new Date(row.updated_at).toLocaleDateString('fr-FR')}}</span><button class="text-button" :disabled="opening" @click="open(row.id)">Ouvrir la fiche</button></footer>
      </article>
      <p v-if="!column.busy&&!column.error&&!column.count" class="pipeline-empty">Aucun contact dans cette étape.</p>
      <button v-if="column.next" class="secondary pipeline-more" :disabled="column.busy" @click="loadColumn(column,version,true)">{{column.busy?'Chargement…':'Afficher plus'}} ({{column.rows.length}} / {{column.count}})</button>
     </div>
    </section>
   </div>
  </template>
 </section>
</template>
<style scoped>
.pipeline{padding:20px;background:#f1f6fa}.pipeline-toolbar{display:flex;align-items:center;gap:12px;margin-bottom:22px;flex-wrap:wrap}.pipeline-toolbar>div{margin-right:auto}.pipeline-toolbar p{font-size:12px;color:#66778e;margin:6px 0}.pipeline-toolbar label{display:flex;align-items:center;gap:8px;background:white;border:1px solid #d9e3ed;border-radius:6px;padding:0 10px}.pipeline-toolbar input{border:0!important;min-width:210px}.pipeline-board{display:flex;gap:16px;overflow-x:auto;align-items:flex-start;padding-bottom:18px}.pipeline-column{flex:0 0 290px;min-width:0}.pipeline-column>header{border-top:3px solid var(--stage-color);background:white;border-radius:6px;padding:16px;box-shadow:0 1px 3px #23324718;margin-bottom:16px}.pipeline-column h3{font-size:14px!important;margin:0 0 8px}.pipeline-column header span,.pipeline-column header small{color:#6b7d91;font-size:12px}.pipeline-cards{display:grid;gap:12px}.pipeline-card{margin:0!important;padding:16px!important;border:1px solid #e1e7ed!important;border-radius:8px!important;box-shadow:0 2px 2px #23324712}.pipeline-name{display:flex;justify-content:space-between;gap:10px;width:100%;background:none;border:0;padding:0;text-align:left;cursor:pointer;color:#25374d}.pipeline-card p{display:flex;align-items:center;gap:7px;font-size:12px;color:#62748b;overflow-wrap:anywhere}.pipeline-card footer{display:flex;flex-wrap:wrap;gap:8px;justify-content:space-between;border-top:1px solid #edf1f5;padding-top:12px;font-size:10px;color:#748399}.pipeline-card .text-button{border:0;background:none;color:#2563a6;cursor:pointer;padding:0}.pipeline-empty{font-size:12px;color:#7a8a9c;padding:10px}.pipeline-more{width:100%}
</style>
<style scoped>
.pipeline{padding:0;background:#f2f6fa}
.pipeline-navigation{display:flex;align-items:center;gap:28px;min-height:64px;padding:0 24px;background:white;border-bottom:1px solid #dfe5ed}
.pipeline-navigation h2{font-size:19px;margin:0;color:#253347}
.pipeline-navigation>span{align-self:stretch;display:flex;align-items:center;border-bottom:2px solid #1887c8;color:#1887c8;font-size:13px}
.pipeline-context{display:flex;align-items:center;gap:16px;padding:22px 24px 16px}
.pipeline-context>strong{background:white;border:1px solid #dae2eb;border-radius:5px;padding:12px 18px;min-width:220px;font-size:14px}
.pipeline-total{background:#e8f1ff;color:#2767ae;padding:8px 12px;border-radius:18px;font-size:12px}
.pipeline .pipeline-toolbar{display:flex;align-items:center;padding:0 24px 18px;margin:0;gap:10px}
.pipeline-toolbar>p{margin-right:auto}
.pipeline-toolbar label{flex:none!important;min-width:0}
.pipeline-board{margin:0 24px;gap:14px;align-items:stretch;height:calc(100dvh - 295px);min-height:350px;overscroll-behavior-x:contain}
.pipeline-column{display:flex;flex-direction:column;flex-basis:300px;max-height:100%;min-height:0}
.pipeline-column>header{flex-shrink:0;margin-bottom:16px;padding:14px;border-radius:5px;border-top-width:2px}
.pipeline-cards{display:flex;flex-direction:column;overflow-y:auto;min-height:0;gap:12px;padding:0 3px 8px 0;scrollbar-width:thin}
.pipeline-card{background:white;flex-shrink:0;padding:14px!important}
.pipeline-name strong{overflow-wrap:anywhere;min-width:0}.pipeline-name svg{flex-shrink:0}
.pipeline button:disabled{opacity:.55;cursor:wait}
.pipeline>p{margin:12px 24px}
@media(max-width:720px){.pipeline-navigation{padding:0 12px;gap:16px}.pipeline-context{padding:16px 12px;flex-wrap:wrap}.pipeline .pipeline-toolbar{padding:0 12px 16px}.pipeline-toolbar>p{width:100%}.pipeline-toolbar label{flex:1!important}.pipeline-toolbar input{min-width:0;width:100%}.pipeline-board{margin:0 12px;height:65dvh}.pipeline-column{flex-basis:280px}}
</style>
