import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import test from 'node:test'
import assert from 'node:assert/strict'
import { parse, compileScript } from 'vue/compiler-sfc'
import { createRenderer, nextTick } from 'vue'
import ts from 'typescript'
const require = createRequire(import.meta.url)
const url = (code) =>
  'data:text/javascript;base64,' +
  Buffer.from(
    ts.transpileModule(code, {
      compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
    }).outputText,
  ).toString('base64')
let code = compileScript(
  parse(readFileSync(new URL('../src/IsolationWorkQueue.vue', import.meta.url), 'utf8')).descriptor,
  {
    id: 'qualification',
    inlineTemplate: true,
    templateOptions: { compilerOptions: { hoistStatic: false } },
  },
).content
code = code
  .replace(/import \{([^}]+)\} from 'lucide-vue-next'/g, (_, names) =>
    names
      .split(',')
      .filter((name) => name.trim())
      .map((name) => `const ${name.trim()}={render:()=>null}`)
      .join(';'),
  )
  .replace(/from ['"]vue['"]/g, `from '${pathToFileURL(require.resolve('vue')).href}'`)
code =
  code
    .replace(/vModelText as _vModelText,?/g, '')
    .replace(/vModelSelect as _vModelSelect,?/g, '')
    .replace(/vModelCheckbox as _vModelCheckbox,?/g, '')
    .replace(/vModelDynamic as _vModelDynamic,?/g, '') +
  ';const _vModelText={},_vModelSelect={},_vModelDynamic={},_vModelCheckbox={};'
code = code.replace(
  /import (\w+) from ['"]\.\/[^'"]+\.vue['"]/g,
  (_, name) =>
    `const ${name}={props:['open','title','autoOpen','role'],setup(p,{slots}){return()=>(${JSON.stringify(name)}==='SidePanel'&&!p.open)?null:stubH('div',{'data-component':${JSON.stringify(name)},'data-title':p.title,'data-auto-open':p.autoOpen},slots.default?.())}}`,
)
code = "import {h as stubH} from '" + pathToFileURL(require.resolve('vue')).href + "';" + code
const component = (await import(url(code))).default
globalThis.document = { activeElement: null }
globalThis.window = {
  addEventListener() {},
  removeEventListener() {},
  confirm() {
    return false
  },
}
const renderer = createRenderer({
  createElement: (tag) => ({
    tag,
    tagName: tag.toUpperCase(),
    children: [],
    props: {},
    addEventListener() {},
    get options() {
      return this.children.filter((n) => n.tag === 'option')
    },
  }),
  createText: (text) => ({ text }),
  createComment: () => ({}),
  setText: (n, t) => (n.text = t),
  setElementText: (n, t) => {
    n.children = []
    n.text = t
  },
  patchProp: (n, k, o, v) => {
    n.props[k] = v
    if (k === 'value') {
      n.value = v
      n._value = v
    }
  },
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
async function flush() {
  for (let i = 0; i < 5; i++) {
    await nextTick()
    await new Promise((resolve) => setImmediate(resolve))
  }
}
const text = (n) => (n.text || '') + (n.children || []).map(text).join('')
function fixture(role = 'setter') {
  const root = { children: [] },
    requests = [],
    portalCalls = []
  const row = (id, status) => ({
    id,
    name: 'Prospect ' + id,
    phone: '+10000000001',
    raw_phone: '+10000000001',
    campaign: { name: 'Campagne Démo' },
    commercial_status: status,
    commercial_label: status,
    assigned_setter: { id: 1, name: 'Setter' },
    revision: 2,
  })
  const app = renderer.createApp(component, {
    role,
    request: async (path, body) => {
      requests.push({ path, body })
      if (path === 'workspace-dashboard/') return { callbacks_due: 2 }
      if (path.startsWith('work-queue/?')) {
        const q = new URLSearchParams(path.split('?')[1]),
          status = q.get('commercial_status'),
          page = Number(q.get('page'))
        return status === 'to_contact'
          ? {
              count: 27,
              next: page === 1 ? 'next' : null,
              results: page === 1 ? [row(1, status), row(2, status)] : [row(3, status)],
            }
          : status === 'interested'
            ? { count: 1, next: null, results: [row(4, status)] }
            : { count: 0, next: null, results: [] }
      }
      return row(Number(path.split('/')[1]), 'to_contact')
    },
    portal: async (path) => {
      portalCalls.push(path)
      return { results: [{ id: 1, name: 'Setter' }], count: 1 }
    },
  })
  app.mount(root)
  return { root, requests, portalCalls, app }
}
async function click(f, label) {
  const button = all(f.root).find((n) => n.tag === 'button' && text(n).trim() === label)
  assert.ok(button, label)
  await button.props.onClick()
  await flush()
}
test('Isolation cards hide empty stages, paginate per stage and keep applied search', async () => {
  const f = fixture()
  try {
    await flush()
    const columns = () =>
      all(f.root).filter((n) => n.tag === 'section' && n.props.class === 'prospect-column')
    assert.equal(columns().length, 2)
    assert.equal(
      all(f.root).some((n) => n.tag === 'table'),
      false,
    )
    assert.equal(f.portalCalls.length, 0)
    const search = all(f.root).find((n) => n.props?.placeholder === 'Nom, téléphone ou référence')
    search.props['onUpdate:modelValue']('non appliqué')
    await flush()
    await click(f, 'Afficher plus · 2 / 27')
    assert.ok(text(f.root).includes('Prospect 3'))
    const more = f.requests.filter((r) => r.path.includes('page=2')).at(-1)
    assert.equal(new URLSearchParams(more.path.split('?')[1]).get('search'), '')
    assert.equal(
      f.requests.some((r) => r.body !== undefined),
      false,
    )
  } finally {
    f.app.unmount()
  }
})
test('phone opens the prospect drawer in preparation mode without posting a call', async () => {
  const f = fixture()
  try {
    await flush()
    const phone = all(f.root).find((n) => n.props?.title === 'Préparer l’appel')
    assert.ok(phone)
    await phone.props.onClick()
    await flush()
    assert.ok(
      all(f.root).some(
        (n) => n.props?.['data-component'] === 'CallAction' && n.props['data-auto-open'] === true,
      ),
    )
    assert.ok(f.requests.some((r) => r.path === 'work-queue/1/'))
    assert.equal(
      f.requests.some((r) => r.body !== undefined),
      false,
    )
    assert.equal(
      all(f.root).some((n) => n.props?.title === 'Affecter ou réattribuer'),
      false,
    )
  } finally {
    f.app.unmount()
  }
})
test('administrator retains assignment drawer and can prepare calls', async () => {
  const f = fixture('administrator')
  try {
    await flush()
    assert.equal(f.portalCalls.length, 1)
    assert.equal(
      all(f.root).some((n) => n.props?.title === 'Préparer l’appel'),
      true,
    )
    await all(f.root)
      .find((n) => n.props?.title === 'Affecter ou réattribuer')
      .props.onClick()
    await flush()
    assert.ok(all(f.root).some((n) => n.props?.['data-title'] === 'Affecter le prospect'))
    assert.ok(text(f.root).includes('Confirmer l’affectation'))
  } finally {
    f.app.unmount()
  }
})
