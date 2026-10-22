import {readFileSync} from 'node:fs'
import {createRequire} from 'node:module'
import {pathToFileURL} from 'node:url'
import test from 'node:test'
import assert from 'node:assert/strict'
import {parse,compileScript} from 'vue/compiler-sfc'
import {createRenderer,nextTick} from 'vue'
import ts from 'typescript'
const require=createRequire(import.meta.url)
const url=code=>'data:text/javascript;base64,'+Buffer.from(ts.transpileModule(code,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText).toString('base64')
let code=compileScript(parse(readFileSync(new URL('../src/AssuranceFollowUps.vue',import.meta.url),'utf8')).descriptor,{id:'qualification',inlineTemplate:true,templateOptions:{compilerOptions:{hoistStatic:false}}}).content
code=code.replace(/import \{([^}]+)\} from 'lucide-vue-next'/g,(_,names)=>names.split(',').map(name=>`const ${name.trim()}={render:()=>null}`).join(';')).replace(/from ['"]vue['"]/g,`from '${pathToFileURL(require.resolve('vue')).href}'`)
code=code.replace(/vModelText as _vModelText,?/g,'').replace(/vModelSelect as _vModelSelect,?/g,'').replace(/vModelDynamic as _vModelDynamic,?/g,'')+';const _vModelText={},_vModelSelect={},_vModelDynamic={};'
code=code.replace(/import (\w+) from ['"]\.\/[^'"]+\.vue['"]/g,(_,name)=>`const ${name}={props:['open','title','autoOpen','role','taskId'],setup(p,{slots}){return()=>(${JSON.stringify(name)}==='SidePanel'&&!p.open)?null:stubH('div',{'data-component':${JSON.stringify(name)},'data-title':p.title,'data-auto-open':p.autoOpen,'data-task-id':p.taskId},slots.default?.())}}`)
code="import {h as stubH} from '"+pathToFileURL(require.resolve('vue')).href+"';"+code
code=code.replace("'./booking-time'",JSON.stringify(url(readFileSync(new URL('../src/booking-time.ts',import.meta.url),'utf8'))))
const component=(await import(url(code))).default
globalThis.document={activeElement:null};globalThis.window={addEventListener(){},removeEventListener(){},confirm(){return false}}
const renderer=createRenderer({createElement:tag=>({tag,tagName:tag.toUpperCase(),children:[],props:{},addEventListener(){},get options(){return this.children.filter(n=>n.tag==='option')}}),createText:text=>({text}),createComment:()=>({}),setText:(n,t)=>n.text=t,setElementText:(n,t)=>{n.children=[];n.text=t},patchProp:(n,k,o,v)=>{n.props[k]=v;if(k==='value'){n.value=v;n._value=v}},parentNode:n=>n?.parent||null,nextSibling:n=>{const siblings=n?.parent?.children||[];return siblings[siblings.indexOf(n)+1]||null},insert(n,p,a){if(n.parent){const old=n.parent.children.indexOf(n);if(old>=0)n.parent.children.splice(old,1)}n.parent=p;const i=p.children.indexOf(a);p.children.splice(i<0?p.children.length:i,0,n)},remove(n){const i=n.parent?.children.indexOf(n);if(i>=0)n.parent.children.splice(i,1)}})
const all=n=>[n,...(n.children||[]).flatMap(all)]
async function flush(){for(let i=0;i<5;i++){await nextTick();await new Promise(resolve=>setImmediate(resolve))}}
const text=n=>(n.text||'')+(n.children||[]).map(text).join('')
test('administrator plans a task with a local date picker and explicit Montreal offset',async()=>{
 const root={children:[]},writes=[],row={id:5,contact_name:'Prospect',due_at:'2030-12-01T15:00:00Z',reason:'Rappel',priority:'normal',revision:2,assigned_setter_id:1}
 const app=renderer.createApp(component,{role:'administrator',taskId:5,portal:async()=>({}),request:async(path,body)=>{if(body)writes.push({path,body});return row}});app.mount(root)
 try{await flush();const buttons=()=>all(root).filter(n=>n.tag==='button');assert.ok(buttons().some(n=>text(n).trim()==='Réattribuer'));await buttons().find(n=>text(n).trim()==='Priorité et échéance').props.onClick();await flush();const date=all(root).find(n=>n.props?.type==='datetime-local');assert.ok(date);date.props['onUpdate:modelValue']('2030-12-02T10:00');all(root).find(n=>n.tag==='textarea').props['onUpdate:modelValue']('Ajustement demandé');await all(root).find(n=>n.tag==='form').props.onSubmit({preventDefault(){}});await flush();assert.equal(writes[0].path,'follow-ups/5/plan/?state=all');assert.equal(writes[0].body.due_at,'2030-12-02T10:00:00-05:00');assert.equal(writes[0].body.revision,2)
 }finally{app.unmount()}
})
