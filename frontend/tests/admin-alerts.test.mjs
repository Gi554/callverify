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
  parse(readFileSync(new URL('../src/AdminAlerts.vue', import.meta.url), 'utf8')).descriptor,
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
    writes = []
  const app = renderer.createApp(component, {
    workspace: 'isolation',
    request: async (path, body) => {
      if (body) {
        writes.push(body)
        if (fail) throw new Error('Alerte modifiée')
        return { acknowledged: true }
      }
      return {
        checked_at: '2026-11-02T14:00:00Z',
        count: 1,
        kinds: [{ kind: 'missing_results', label: 'Résultats à renseigner', count: 1 }],
        results: [
          {
            kind: 'missing_results',
            id: '12',
            signature: 'a'.repeat(64),
            title: 'Alice · Rendez-vous #12',
            reference: 12,
            details: { setter_id: 21 },
            review: null,
          },
        ],
      }
    },
  })
  app.mount(root)
  return { root, app, writes }
}
test('alert acknowledgement submits a note and source signature without changing business state', async () => {
  const f = fixture()
  try {
    await flush()
    button(f, 'Consulter').props.onClick()
    await flush()
    const input = all(f.root).find((n) => n.tag === 'textarea')
    input.props['onUpdate:modelValue']('Responsable contacté')
    await flush()
    const form = all(f.root).find((n) => n.tag === 'form')
    await form.props.onSubmit({ preventDefault() {} })
    await flush()
    assert.equal(f.writes.length, 1)
    assert.equal(f.writes[0].signature, 'a'.repeat(64))
    assert.equal(f.writes[0].note, 'Responsable contacté')
    assert.equal(f.writes[0].id, '12')
  } finally {
    f.app.unmount()
  }
})
test('stale alert leaves its note open and does not claim acknowledgement', async () => {
  const f = fixture({ fail: true })
  try {
    await flush()
    button(f, 'Consulter').props.onClick()
    await flush()
    const input = all(f.root).find((n) => n.tag === 'textarea')
    input.props['onUpdate:modelValue']('À revoir')
    await flush()
    await all(f.root)
      .find((n) => n.tag === 'form')
      .props.onSubmit({ preventDefault() {} })
    await flush()
    assert.match(text(f.root), /Alerte modifiée/)
    assert.ok(all(f.root).some((n) => n.tag === 'textarea'))
    assert.doesNotMatch(text(f.root), /Prise en charge enregistrée/)
  } finally {
    f.app.unmount()
  }
})
