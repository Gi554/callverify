<script setup lang="ts">
import {ref,watch,nextTick,onBeforeUnmount,useId} from 'vue'
import {X,PanelRight} from 'lucide-vue-next'
const props=withDefaults(defineProps<{open:boolean;title:string;subtitle?:string;eyebrow?:string;closeDisabled?:boolean;scrollable?:boolean}>(),{eyebrow:'MON ESPACE',scrollable:true})
const emit=defineEmits<{requestClose:[]}>()
const dialog=ref<HTMLDialogElement|null>(null),headingId=useId()
function requestClose(){if(!props.closeDisabled)emit('requestClose')}
watch(()=>props.open,async open=>{await nextTick();if(open&&props.open&&!dialog.value?.open)dialog.value?.showModal();else if(!props.open)dialog.value?.close()},{immediate:true,flush:'post'})
onBeforeUnmount(()=>dialog.value?.close())
</script>
<template>
 <dialog ref="dialog" class="side-panel" :aria-labelledby="headingId" @cancel.prevent="requestClose">
  <header class="side-panel-heading"><div class="panel-heading-icon"><PanelRight :size="21"/></div><div class="panel-heading-text"><span>{{eyebrow}}</span><h2 :id="headingId">{{title}}</h2><p v-if="subtitle">{{subtitle}}</p></div><button type="button" class="panel-close" :disabled="closeDisabled" aria-label="Fermer le panneau" title="Fermer" @click="requestClose"><X :size="21"/></button></header>
  <div class="side-panel-body" :class="{'panel-body-scroll':scrollable}"><slot/></div>
  <footer v-if="$slots.footer" class="side-panel-footer"><slot name="footer"/></footer>
 </dialog>
</template>
<style scoped>
.side-panel{position:fixed;inset:0 0 0 auto;margin:0;padding:0;border:0;border-left:1px solid #e0e7f1;width:min(660px,100vw);max-width:100vw;height:100dvh;max-height:100dvh;background:#f9fbfe;color:#293c55;box-shadow:-18px 0 70px #142a492b;overflow:hidden}
.side-panel[open]{display:flex;flex-direction:column;animation:panel-enter .22s cubic-bezier(.2,.8,.2,1)}
.side-panel::backdrop{background:#162d4938;animation:panel-shade .18s ease-out}
.side-panel-heading{display:flex;align-items:center;gap:14px;flex-shrink:0;padding:24px;background:linear-gradient(120deg,#f1f5ff,#faf7ff 65%,#effaf5);border-bottom:1px solid #e2e9f4}
.panel-heading-icon{width:43px;height:43px;display:grid;place-items:center;flex-shrink:0;border:1px solid #dfe7fc;background:#fff;color:#7388d7;border-radius:13px}
.panel-heading-text{flex:1;min-width:0}.panel-heading-text>span{display:block;font-size:9px;letter-spacing:1.6px;font-weight:700;color:#8b94b0}.side-panel .panel-heading-text h2{margin:7px 0 0;color:#293c55;font-size:21px;font-weight:700;letter-spacing:-.5px;overflow-wrap:anywhere;line-height:1.3}.panel-heading-text p{margin:6px 0 0;font-size:12px;color:#7a8da8}
.panel-close{display:grid;place-items:center;width:35px;height:35px;flex-shrink:0;background:#ffffffa8;border:1px solid #e3e8f1;border-radius:10px;color:#7a8ba3;cursor:pointer}.panel-close:hover{background:white;color:#426cbb}.panel-close:disabled{opacity:.45;cursor:wait}.panel-close:focus-visible{outline:3px solid #a4c5f8;outline-offset:2px}
.side-panel-body{display:flex;flex-direction:column;flex:1;min-height:0;overflow:hidden}.side-panel-footer{flex-shrink:0;background:white;border-top:1px solid #e4eaf3;padding:18px 24px}
.side-panel-body.panel-body-scroll{display:block;overflow-y:auto;overscroll-behavior:contain;padding:24px}
@keyframes panel-enter{from{transform:translateX(45px);opacity:.4}to{transform:translateX(0);opacity:1}}@keyframes panel-shade{from{opacity:0}to{opacity:1}}
@media(max-width:600px){.side-panel-heading{padding:20px 17px;gap:11px}.side-panel .panel-heading-text h2{font-size:18px}.panel-heading-icon{width:37px;height:37px}.side-panel-footer{padding:16px}}
@media(prefers-reduced-motion:reduce){.side-panel[open],.side-panel::backdrop{animation:none}}
</style>
