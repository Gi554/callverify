import {readFileSync} from 'node:fs'
import {createRequire} from 'node:module'
import {pathToFileURL} from 'node:url'
import test from 'node:test'
import assert from 'node:assert/strict'
import {parse,compileScript} from 'vue/compiler-sfc'
import {createRenderer,h,nextTick} from 'vue'
import ts from 'typescript'
const require=createRequire(import.meta.url)
const url=code=>'data:text/javascript;base64,'+Buffer.from(ts.transpileModule(code,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText).toString('base64')
let code=compileScript(parse(readFileSync(new URL('../src/IsolationFollowUps.vue',import.meta.url),'utf8')).descriptor,{id:'qualification',inlineTemplate:true,templateOptions:{compilerOptions:{hoistStatic:false}}}).content
code=code.replace(/import \{([^}]+)\} from 'lucide-vue-next'/g,(_,names)=>names.split(',').map(name=>`const ${name.trim()}={render:()=>null}`).join(';')).replace(/from ['"]vue['"]/g,`from '${pathToFileURL(require.resolve('vue')).href}'`).replace("'./booking-time'",JSON.stringify(url(readFileSync(new URL('../src/booking-time.ts',import.meta.url),'utf8'))))
code=code.replace(/vModelText as _vModelText,?/g,'').replace(/vModelSelect as _vModelSelect,?/g,'').replace(/vModelDynamic as _vModelDynamic,?/g,'')+';const _vModelText={},_vModelSelect={},_vModelDynamic={};'
const component=(await import(url(code))).default
globalThis.document={activeElement:null};globalThis.window={addEventListener(){},removeEventListener(){},confirm(){return false}}
const renderer=createRenderer({createElement:tag=>({tag,tagName:tag.toUpperCase(),children:[],props:{},addEventListener(){},get options(){return this.children.filter(n=>n.tag==='option')}}),createText:text=>({text}),createComment:()=>({}),setText:(n,t)=>n.text=t,setElementText:(n,t)=>{n.children=[];n.text=t},patchProp:(n,k,o,v)=>{n.props[k]=v;if(k==='value'){n.value=v;n._value=v}},parentNode:n=>n?.parent||null,nextSibling:n=>{const siblings=n?.parent?.children||[];return siblings[siblings.indexOf(n)+1]||null},insert(n,p,a){if(n.parent){const old=n.parent.children.indexOf(n);if(old>=0)n.parent.children.splice(old,1)}n.parent=p;const i=p.children.indexOf(a);p.children.splice(i<0?p.children.length:i,0,n)},remove(n){const i=n.parent?.children.indexOf(n);if(i>=0)n.parent.children.splice(i,1)}})
const all=n=>[n,...(n.children||[]).flatMap(all)]
async function flush(){for(let i=0;i<5;i++){await nextTick();await new Promise(resolve=>setImmediate(resolve))}}
function fixture(){const root={children:[]},writes=[],saved=[];let closed=false;const row={id:4,prospect_id:7,prospect_name:'Prospect',revision:2,due_at:'2030-12-01T15:00:00Z',note:'Rappel',closed_at:null,overdue:false};const app=renderer.createApp(component,{prospectId:7,request:async(path,body)=>{if(body){writes.push({path,body});if(path.endsWith('/close/'))closed=true;return {recorded:true}}if(path.startsWith('work-queue/'))return {id:7,revision:5};return {results:closed?[]:[row],count:closed?0:1}},onSaved:()=>saved.push(true)});app.mount(root);return {root,writes,saved,app}}
function set(node,value){node.props['onUpdate:modelValue'](value)}
async function submit(f){await all(f.root).find(n=>n.tag==='form').props.onSubmit({preventDefault(){}});await flush()}

test('manual reminders can be created from a prospect without an appointment',async()=>{const f=fixture();try{await flush();all(f.root).find(n=>n.tag==='button'&&n.text==='Créer un rappel manuel').props.onClick();await flush();set(all(f.root).find(n=>n.tag==='input'),'2030-12-01T10:00');await submit(f);assert.equal(f.writes[0].path,'work-queue/7/follow-ups/');assert.equal(f.writes[0].body.revision,5);assert.equal(f.writes[0].body.due_at,'2030-12-01T10:00:00-05:00');assert.deepEqual(f.saved,[true])}finally{f.app.unmount()}})

test('finishing a reminder sends its revision and explicit resolution',async()=>{const f=fixture();try{await flush();all(f.root).find(n=>n.tag==='button'&&n.text==='Terminer').props.onClick();await flush();set(all(f.root).find(n=>n.tag==='textarea'),'Prospect rappelé');await submit(f);assert.equal(f.writes[0].path,'follow-ups/4/close/');assert.equal(f.writes[0].body.revision,2);assert.equal(f.writes[0].body.resolution,'Prospect rappelé');assert.deepEqual(f.saved,[true])}finally{f.app.unmount()}})
