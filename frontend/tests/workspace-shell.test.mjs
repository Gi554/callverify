import {readFileSync} from 'node:fs'
import {createRequire} from 'node:module'
import {pathToFileURL} from 'node:url'
import test from 'node:test'
import assert from 'node:assert/strict'
import {parse,compileScript} from 'vue/compiler-sfc'
import {createSSRApp} from 'vue'
import {renderToString} from 'vue/server-renderer'
import ts from 'typescript'
const require=createRequire(import.meta.url)
const source=readFileSync(new URL('../src/CrmShell.vue',import.meta.url),'utf8')
let compiled=compileScript(parse(source).descriptor,{id:'workspace-shell',inlineTemplate:true}).content
compiled=compiled.replace(/import \{([^}]+)\} from 'lucide-vue-next'/g,(_,names)=>names.split(',').map(name=>`const ${name.trim()}={render:()=>null}`).join(';'))
compiled=compiled.replace(/from ['"]vue['"]/g,`from '${pathToFileURL(require.resolve('vue')).href}'`)
const code=ts.transpileModule(compiled,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText
const component=(await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'))).default
const props={username:'Setter de recette',role:'setter',items:[],active:'overview',pageTitle:'Tableau de bord',accountOpen:false,accessOpen:false,canManage:false}
test('single Assurance access has no space selector or Isolation proposal',async()=>{
 const html=await renderToString(createSSRApp(component,{...props,workspace:'assurance',spaces:[{workspace:'assurance',role:'setter'}]}))
 assert.doesNotMatch(html,/<select/);assert.match(html,/Assurance/);assert.doesNotMatch(html,/Isolation|Choisir un espace/)
})

test('Setter navigation omits Conversations while keeping authorized modules',async()=>{
 const html=await renderToString(createSSRApp(component,{...props,workspace:'assurance',spaces:[{workspace:'assurance',role:'setter'}],items:[{id:'overview',label:'Vue d’ensemble',icon:'overview'},{id:'contacts',label:'Contacts',icon:'contacts'},{id:'followups',label:'Tâches de suivi',icon:'followups'}]}))
 assert.doesNotMatch(html,/Conversations/)
 assert.match(html,/Accueil/);assert.match(html,/Prospects/);assert.match(html,/Tâches/)
 assert.doesNotMatch(html,/Utilisateurs et accès/)
})
test('single Isolation access has no Assurance proposal',async()=>{
 const html=await renderToString(createSSRApp(component,{...props,workspace:'isolation',spaces:[{workspace:'isolation',role:'setter'}]}))
 assert.doesNotMatch(html,/<select/);assert.match(html,/Isolation/);assert.doesNotMatch(html,/Assurance|Choisir un espace/)
})
test('selector is present only for multiple authorized spaces',async()=>{
 const html=await renderToString(createSSRApp(component,{...props,workspace:'assurance',spaces:[{workspace:'assurance',role:'setter'},{workspace:'isolation',role:'setter'}]}))
 assert.match(html,/<select/);assert.match(html,/value="assurance"/);assert.match(html,/value="isolation"/)
})
