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
  parse(readFileSync(new URL('../src/GeneratedReports.vue', import.meta.url), 'utf8')).descriptor,
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
    `const IsolationPageHeader={props:['title'],emits:['refresh'],setup(p,{slots}){return()=>[p.title,slots.actions?.()]}}`,
  )
  .replace(
    /import SidePanel from ['"]\.\/SidePanel\.vue['"]/g,
    `const SidePanel={props:['open'],setup(p,{slots}){return()=>p.open?slots.default?.():null}}`,
  )
code =
  withStatComponents(code)
    .replace(/vModelText as _vModelText,?/g, '')
    .replace(/vModelSelect as _vModelSelect,?/g, '')
    .replace(/vModelCheckbox as _vModelCheckbox,?/g, '') +
  ';const _vModelText={},_vModelSelect={},_vModelCheckbox={};'
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
    writes = []
  let fail = true
  const app = renderer.createApp(component, {
    workspace: 'assurance',
    request: async (path, body) => {
      if (body) {
        writes.push({ path, body })
        if (fail) {
          fail = false
          throw new Error('Réponse perdue')
        }
        return { id: 1, state: 'queued' }
      }
      if (path.includes('report-plan')) return { enabled: false, hour: 19, revision: 0 }
      return { results: [], count: 0 }
    },
  })
  app.mount(root)
  return { root, app, writes }
}
test('manual report retries reuse their request ID and show queued rather than available', async () => {
  const f = fixture()
  try {
    await flush()
    button(f, 'Nouveau rapport').props.onClick()
    await flush()
    const form = all(f.root).find(
      (n) =>
        n.tag === 'form' &&
        all(n).some((x) => x.tag === 'button' && text(x) === 'Générer PDF et Excel'),
    )
    await form.props.onSubmit({ preventDefault() {} })
    await flush()
    assert.match(text(f.root), /Réponse perdue/)
    await form.props.onSubmit({ preventDefault() {} })
    await flush()
    assert.equal(f.writes.length, 2)
    assert.equal(f.writes[0].body.request_id, f.writes[1].body.request_id)
    assert.match(text(f.root), /après génération/)
    assert.equal(button(f, 'PDF'), undefined)
  } finally {
    f.app.unmount()
  }
})
