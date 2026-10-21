import {readFileSync} from 'node:fs'
import {createRequire} from 'node:module'
import {pathToFileURL} from 'node:url'
import test from 'node:test'
import assert from 'node:assert/strict'
import {parse,compileScript} from 'vue/compiler-sfc'
import ts from 'typescript'
import {createRenderer,nextTick} from 'vue'

const require=createRequire(import.meta.url)
const source=readFileSync(new URL('../src/PortalLogin.vue',import.meta.url),'utf8')
let compiled=compileScript(parse(source).descriptor,{id:'portal-login',inlineTemplate:true}).content
compiled=compiled.replace(/import \{([^}]+)\} from 'lucide-vue-next'/g,(_,names)=>names.split(',').map(name=>`const ${name.trim()}={render:()=>null}`).join(';'))
compiled=compiled.replace(/from ['"]vue['"]/g,`from '${pathToFileURL(require.resolve('vue')).href}'`)
const code=ts.transpileModule(compiled,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText
const component=(await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'))).default
const renderer=createRenderer({
 insertStaticContent(content,parent,anchor){const node={text:content,children:[],props:{},parent};const i=parent.children.indexOf(anchor);parent.children.splice(i<0?parent.children.length:i,0,node);return [node,node]},
 createElement:tag=>({tag,tagName:tag.toUpperCase(),children:[],props:{},getRootNode(){return globalThis.document},addEventListener(){},removeEventListener(){},setAttribute(){},removeAttribute(){}}),createText:text=>({text}),createComment:()=>({text:''}),
 setText:(node,text)=>{node.text=text},setElementText:(node,text)=>{node.children=[];node.text=text},
 patchProp:(node,key,old,value)=>{node.props[key]=value},parentNode:node=>node?.parent,nextSibling:node=>{const siblings=node?.parent?.children||[];return siblings[siblings.indexOf(node)+1]||null},
 insert(node,parent,anchor){if(node.parent){const i=node.parent.children.indexOf(node);if(i>=0)node.parent.children.splice(i,1)}node.parent=parent;const i=parent.children.indexOf(anchor);parent.children.splice(i<0?parent.children.length:i,0,node)},
 remove(node){const i=node.parent?.children.indexOf(node);if(i>=0)node.parent.children.splice(i,1)}
})
const text=node=>(node.text||'')+(node.children||[]).map(text).join('')

globalThis.Document=class {};globalThis.ShadowRoot=class {};globalThis.document={activeElement:null}
function fixture(){
 const root={children:[]},submitted=[]
 const app=renderer.createApp(component,{busy:false,error:'',onSubmit:value=>submitted.push(value)})
 app.mount(root)
 const all=node=>[node,...(node.children||[]).flatMap(all)]
 async function click(label){const button=all(root).find(n=>n.tag==='button'&&text(n).trim()===label);assert.ok(button,label);await button.props.onClick();await nextTick()}
 return {root,submitted,click,all:()=>all(root),close:()=>app.unmount()}
}
test('CallVerify login starts with two explicit profiles and no password field',()=>{
 const f=fixture();try{assert.match(text(f.root),/Assurance/);assert.match(text(f.root),/Isolation/);assert.equal(f.all().filter(n=>n.tag==='input').length,0);assert.equal(f.submitted.length,0)}finally{f.close()}
})
test('profile selection opens credentials; switching clears password',async()=>{
 const f=fixture();try{
  await f.click('AssuranceContacts et rendez-vous')
  const username=f.all().find(n=>n.props?.id==='crm-username'),password=f.all().find(n=>n.props?.id==='crm-password')
  assert.ok(username);assert.ok(password)
  username.props['onUpdate:modelValue']('synthetic-setter');password.props['onUpdate:modelValue']('synthetic-secret')
  await nextTick();await f.all().find(n=>n.tag==='form').props.onSubmit({preventDefault(){}});await nextTick()
  assert.equal(f.submitted.length,1);assert.equal(f.submitted[0].workspace,'assurance');assert.equal(f.submitted[0].username,'synthetic-setter')
  assert.equal(f.all().find(n=>n.props?.id==='crm-password').value,'')
  await f.click('Changer de profil');await f.click('IsolationProspects et visites')
  assert.equal(f.all().find(n=>n.props?.id==='crm-password').value,'')
 }finally{f.close()}
})
