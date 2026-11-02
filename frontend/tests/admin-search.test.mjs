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
  parse(readFileSync(new URL('../src/AdminSearch.vue', import.meta.url), 'utf8')).descriptor,
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
  /import ProspectExport from ['"]\.\/ProspectExport\.vue['"]/g,
  `const ProspectExport={props:['filters'],render(){return JSON.stringify(this.filters)}}`,
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
function fixture() {
  const root = { children: [] },
    calls = []
  const app = renderer.createApp(component, {
    workspace: 'assurance',
    request: async (path) => {
      calls.push(path)
      return {
        count: 1,
        results: [
          {
            id: 12,
            name: 'Alice',
            phone: '5145551234',
            contact_status: 'to_contact',
            owner_name: 'Setter',
            appointment_id: null,
          },
        ],
        options: {
          setters: [],
          targets: [],
          campaigns: [],
          contact_statuses: [],
          appointment_statuses: [],
        },
        definition: 'Critères sur le même rendez-vous',
      }
    },
  })
  app.mount(root)
  return { root, app, calls }
}
test('search applies filters only on submission and opens the matching contact', async () => {
  const f = fixture()
  try {
    await flush()
    const input = all(f.root).find(
      (n) => n.tag === 'input' && n.props.placeholder === 'Nom ou prénom',
    )
    input.props['onUpdate:modelValue']('Alice')
    await flush()
    assert.equal(f.calls.length, 1)
    await all(f.root)
      .find((n) => n.tag === 'form')
      .props.onSubmit({ preventDefault() {} })
    await flush()
    assert.match(f.calls[1], /name=Alice/)
    assert.match(text(f.root), /Alice/)
    assert.ok(button(f, 'Ouvrir la fiche'))
    assert.match(text(f.root), /"name":"Alice"/)
  } finally {
    f.app.unmount()
  }
})
