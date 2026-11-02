import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import test from 'node:test'
import assert from 'node:assert/strict'
import { parse, compileScript } from 'vue/compiler-sfc'
import { createRenderer, nextTick } from 'vue'
import ts from 'typescript'
import { withStatComponents } from './stat-components.mjs'
const require = createRequire(import.meta.url)
const vue = pathToFileURL(require.resolve('vue')).href
const url = (code) =>
  'data:text/javascript;base64,' +
  Buffer.from(
    ts.transpileModule(code, {
      compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
    }).outputText,
  ).toString('base64')
let code = compileScript(
  parse(readFileSync(new URL('../src/SetterPerformance.vue', import.meta.url), 'utf8')).descriptor,
  {
    id: 'activity',
    inlineTemplate: true,
    templateOptions: { compilerOptions: { hoistStatic: false } },
  },
).content
code = code
  .replace(/from ['"]vue['"]/g, `from '${vue}'`)
  .replace(/import \{([^}]+)\} from 'lucide-vue-next'/g, (_, names) =>
    names
      .split(',')
      .filter((n) => n.trim())
      .map((n) => `const ${n.trim()}={render:()=>null}`)
      .join(';'),
  )
code = code
  .replace(
    /import IsolationPageHeader from ['"]\.\/IsolationPageHeader\.vue['"]/g,
    `const IsolationPageHeader={props:['title'],render(){return this.title}}`,
  )
  .replace(
    /import SidePanel from ['"]\.\/SidePanel\.vue['"]/g,
    `const SidePanel={props:['open'],setup(p,{slots}){return()=>p.open?slots.default?.():null}}`,
  )
code =
  withStatComponents(code)
    .replace(/vModelText as _vModelText,?/g, '')
    .replace(/vModelSelect as _vModelSelect,?/g, '') + ';const _vModelText={},_vModelSelect={};'
const component = (await import(url(code))).default
const renderer = createRenderer({
  createElement: (tag) => ({ tag, children: [], props: {} }),
  createText: (text) => ({ text }),
  createComment: () => ({}),
  setText: (n, t) => (n.text = t),
  setElementText: (n, t) => {
    n.children = []
    n.text = t
  },
  patchProp: (n, k, o, v) => (n.props[k] = v),
  parentNode: (n) => n?.parent || null,
  nextSibling: (n) => {
    const siblings = n?.parent?.children || []
    return siblings[siblings.indexOf(n) + 1] || null
  },
  insert(n, p, a) {
    if (n.parent) {
      const old = n.parent.children.indexOf(n)
      if (old >= 0) n.parent.children.splice(old, 1)
    }
    n.parent = p
    const i = p.children.indexOf(a)
    p.children.splice(i < 0 ? p.children.length : i, 0, n)
  },
  remove(n) {
    const i = n.parent?.children.indexOf(n)
    if (i >= 0) n.parent.children.splice(i, 1)
  },
})
const text = (n) => (n.text || '') + (n.children || []).map(text).join('')
async function flush() {
  for (let i = 0; i < 5; i++) {
    await nextTick()
    await new Promise((resolve) => setImmediate(resolve))
  }
}

function fixture() {
  const root = { children: [] }
  let callFail = true
  const app = renderer.createApp(component, {
    workspace: 'isolation',
    role: 'setter',
    request: async () => ({
      agent_id: 21,
      agent_name: 'Alice',
      totals: {
        assigned_now: 20,
        current_assignments_in_period: 10,
        qualified: 4,
        scheduled: 4,
        held: 3,
        closed: 1,
        not_closed: 2,
        not_held: 1,
        awaiting_result: 0,
        sale_unknown: 0,
        generated_cad: '75',
        unpriced: 0,
      },
      daily: [{ day: '2026-11-02', scheduled: 4, held: 3, closed: 1, generated_cad: '75' }],
      definition: 'Période Québec',
    }),
    portal: async () => {
      if (callFail) throw new Error('Source appels indisponible')
      return {
        totals: { calls: 2, attempts: 3, uncertain: 1 },
        daily: [],
        definition: 'Accepté ne signifie pas prospect joint',
      }
    },
  })
  app.mount(root)
  return {
    root,
    app,
    recover() {
      callFail = false
    },
  }
}
test('business performance remains usable on call source failure and never invents reached prospects', async () => {
  const f = fixture()
  try {
    await flush()
    assert.match(text(f.root), /Alice/)
    assert.match(text(f.root), /Source appels indisponible/)
    assert.match(text(f.root), /Non disponible/)
    assert.match(text(f.root), /75/)
    assert.doesNotMatch(text(f.root), /Aucun setter/)
  } finally {
    f.app.unmount()
  }
})
