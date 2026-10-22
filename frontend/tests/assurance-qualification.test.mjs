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
let code=compileScript(parse(readFileSync(new URL('../src/AssuranceQualification.vue',import.meta.url),'utf8')).descriptor,{id:'qualification',inlineTemplate:true}).content
code=code.replace(/import \{([^}]+)\} from 'lucide-vue-next'/g,(_,names)=>names.split(',').map(name=>`const ${name.trim()}={render:()=>null}`).join(';')).replace(/from ['"]vue['"]/g,`from '${pathToFileURL(require.resolve('vue')).href}'`).replace("'./booking-time'",JSON.stringify(url(readFileSync(new URL('../src/booking-time.ts',import.meta.url),'utf8'))))
code=code.replace(/vModelText as _vModelText,?/g,'').replace(/vModelSelect as _vModelSelect,?/g,'')+';const _vModelText={},_vModelSelect={};'
const component=(await import(url(code))).default
globalThis.document={activeElement:null}
const renderer=createRenderer({createElement:tag=>({tag,tagName:tag.toUpperCase(),children:[],props:{},addEventListener(){},get options(){return this.children.filter(n=>n.tag==='option')}}),createText:text=>({text}),createComment:()=>({}),setText:(n,t)=>n.text=t,setElementText:(n,t)=>{n.children=[];n.text=t},patchProp:(n,k,o,v)=>{n.props[k]=v;if(k==='value'){n.value=v;n._value=v}},parentNode:n=>n.parent,nextSibling:()=>null,insert(n,p,a){n.parent=p;const i=p.children.indexOf(a);p.children.splice(i<0?p.children.length:i,0,n)},remove(n){const i=n.parent?.children.indexOf(n);if(i>=0)n.parent.children.splice(i,1)}})
const all=n=>[n,...(n.children||[]).flatMap(all)]
async function flush(){for(let i=0;i<5;i++){await nextTick();await new Promise(resolve=>setImmediate(resolve))}}
const fields=[{key:'age',label:'Âge',type:'number',min:0,max:120},{key:'smoker',label:'Fumeur',type:'boolean'},{key:'insurances',label:'Assurances',type:'multiple',choices:{life:'Assurance vie',none_known:'Aucune assurance connue'}},{key:'advisor_notes',label:'Notes conseiller',type:'text'}]
function fixture({fail=false}={}){const root={children:[]},writes=[],dirty=[],saved=[];let exposed
 const app=renderer.createApp({setup:()=>()=>h(component,{ref:ref=>exposed=ref,contactId:7,role:'setter',leaseToken:'lease',contactRevision:3,prepare:async()=>{},request:async(path,body)=>{if(body){writes.push({path,body});if(fail)throw new Error('Conflit de qualification');return {fields,qualification:body.qualification,contact_revision:4}}return {fields,qualification:{},contact_revision:3}},onSaved:revision=>saved.push(revision),onDirty:value=>dirty.push(value)})});app.mount(root);return {root,writes,dirty,saved,app,exposed:()=>exposed}}
function set(node,value){node.props['onUpdate:modelValue'](value)}
test('unknown answers stay null and insurance none cannot coexist with a known insurance',async()=>{const f=fixture();try{await flush();const checks=()=>all(f.root).filter(n=>n.tag==='input'&&n.props.type==='checkbox');checks()[1].props.onChange({});await flush();checks()[0].props.onChange({});await flush();await f.exposed().ensureSaved();assert.equal(f.writes.length,1);assert.deepEqual(f.writes[0].body.qualification.insurances,['life']);assert.equal(f.writes[0].body.qualification.smoker,null);assert.equal(f.writes[0].body.qualification.age,null);assert.deepEqual(f.saved,[4])}finally{f.app.unmount()}})
test('booking preparation awaits a changed qualification save, then skips unchanged data',async()=>{const f=fixture();try{await flush();set(all(f.root).find(n=>n.tag==='textarea'),'Préparer la rencontre');await flush();assert.equal(f.dirty.at(-1),true);await f.exposed().ensureSaved();assert.equal(f.writes[0].path,'contacts/7/qualification/');assert.equal(f.writes[0].body.contact_revision,3);assert.equal(f.writes[0].body.qualification.advisor_notes,'Préparer la rencontre');await flush();assert.equal(f.dirty.at(-1),false);await f.exposed().ensureSaved();assert.equal(f.writes.length,1)}finally{f.app.unmount()}})
test('failed saving rejects booking preparation while keeping the qualification draft',async()=>{const f=fixture({fail:true});try{await flush();set(all(f.root).find(n=>n.tag==='textarea'),'Ne pas perdre');await flush();await assert.rejects(f.exposed().ensureSaved(),/Conflit/);assert.equal(f.saved.length,0);assert.equal(f.dirty.at(-1),true)}finally{f.app.unmount()}})
