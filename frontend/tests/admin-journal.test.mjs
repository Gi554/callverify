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
  parse(readFileSync(new URL('../src/AdminJournal.vue', import.meta.url), 'utf8')).descriptor,
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
code = code.replace(
  /import \{ actorNames \} from ['"]\.\/actor-names['"]/g,
  `const actorNames=async(portal,workspace,ids)=>portal?Object.fromEntries((await portal(workspace+'/actor-names/?ids='+ids.join(','))).results.map(row=>[row.id,row.name])):{}`,
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
const all = (n) => [n, ...(n.children || []).flatMap(all)]
const text = (n) => (n.text || '') + (n.children || []).map(text).join('')
async function flush() {
  for (let i = 0; i < 5; i++) {
    await nextTick()
    await new Promise((resolve) => setImmediate(resolve))
  }
}

const button = (f, label) => all(f.root).find((n) => n.tag === 'button' && text(n).trim() === label)
function fixture({ fail = false } = {}) {
  const root = { children: [] },
    calls = []
  const app = renderer.createApp(component, {
    workspace: 'isolation',
    portal: async () => ({ results: [{ id: 21, name: 'Alice' }] }),
    request: async (path) => {
      calls.push(path)
      if (fail) throw new Error('Service indisponible')
      return {
        count: 26,
        actions: ['isolation.visit.changed'],
        results: [
          {
            id: 1,
            created_at: '2026-11-02T14:00:00Z',
            actor_id: 21,
            actor_label: 'Compte #21',
            action: 'isolation.visit.changed',
            object_id: '12',
            metadata: { before: { performed: false }, after: { performed: true } },
          },
        ],
      }
    },
  })
  app.mount(root)
  return { root, app, calls }
}
test('journal paginates and opens recorded before and after without sending mutations', async () => {
  const f = fixture()
  try {
    await flush()
    assert.equal(f.calls.length, 1)
    assert.match(f.calls[0], /^admin-journal\/\?/)
    button(f, 'Consulter').props.onClick()
    await flush()
    assert.match(text(f.root), /Avant/)
    assert.match(text(f.root), /Après/)
    assert.match(text(f.root), /Alice · #21/)
    button(f, 'Suivant').props.onClick()
    await flush()
    assert.match(f.calls[1], /page=2/)
    assert.equal(f.calls.length, 2)
  } finally {
    f.app.unmount()
  }
})
test('journal failure stays visible without a false empty history', async () => {
  const f = fixture({ fail: true })
  try {
    await flush()
    assert.match(text(f.root), /Service indisponible/)
    assert.doesNotMatch(text(f.root), /Aucun événement/)
  } finally {
    f.app.unmount()
  }
})
