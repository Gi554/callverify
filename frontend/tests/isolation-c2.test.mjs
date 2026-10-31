import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import test from 'node:test'
import assert from 'node:assert/strict'
import { parse, compileScript } from 'vue/compiler-sfc'
import { createRenderer, h, nextTick } from 'vue'
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
  parse(readFileSync(new URL('../src/IsolationC2.vue', import.meta.url), 'utf8')).descriptor,
  { id: 'qualification', inlineTemplate: true },
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
  .replace(
    "'./booking-time'",
    JSON.stringify(url(readFileSync(new URL('../src/booking-time.ts', import.meta.url), 'utf8'))),
  )
code =
  code
    .replace(/vModelText as _vModelText,?/g, '')
    .replace(/vModelSelect as _vModelSelect,?/g, '')
    .replace(/vModelDynamic as _vModelDynamic,?/g, '') +
  ';const _vModelText={},_vModelSelect={},_vModelDynamic={};'
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
  parentNode: (n) => n.parent,
  nextSibling: () => null,
  insert(n, p, a) {
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
function fixture({ fail = false, loadFail = false, defaults = {}, draft = {} } = {}) {
  const root = { children: [] },
    writes = [],
    dirty = [],
    saved = []
  let exposed
  const app = renderer.createApp({
    setup: () => () =>
      h(component, {
        ref: (ref) => (exposed = ref),
        prospectId: 7,
        request: async (path, body) => {
          if (body) {
            writes.push({ path, body })
            if (fail) throw new Error('Fiche modifiée')
            return { c2: body.c2, revision: 4 }
          }
          if (loadFail) throw new Error('Chargement indisponible')
          return {
            c2: draft,
            defaults: { full_name: 'Client test', phone: '5145550100', ...defaults },
            revision: 3,
          }
        },
        onSaved: (revision) => saved.push(revision),
        onDirty: (value) => dirty.push(value),
      }),
  })
  app.mount(root)
  return { root, writes, dirty, saved, app, exposed: () => exposed }
}
function set(node, value) {
  node.props['onUpdate:modelValue'](value)
}

test('C2 defaults stay distinct from unknown yes/no, and a saved draft supplies the current revision', async () => {
  const f = fixture()
  try {
    await flush()
    set(
      all(f.root).find((n) => n.tag === 'select'),
      false,
    )
    await flush()
    await f.exposed().ensureSaved()
    assert.equal(f.writes.length, 1)
    assert.equal(f.writes[0].path, 'work-queue/7/c2/')
    assert.equal(f.writes[0].body.revision, 3)
    assert.equal(f.writes[0].body.c2.attic_accessible, false)
    assert.equal(f.writes[0].body.c2.age, null)
    assert.equal(f.writes[0].body.c2.monthly_electricity, null)
    assert.deepEqual(f.saved, [3, 4])
    await flush()
    assert.equal(f.dirty.at(-1), false)
    await f.exposed().ensureSaved()
    assert.equal(f.writes.length, 1)
  } finally {
    f.app.unmount()
  }
})

test('a conflicting C2 save rejects booking preparation and retains the dirty draft', async () => {
  const f = fixture({ fail: true })
  try {
    await flush()
    set(
      all(f.root).find((n) => n.tag === 'input'),
      'Autre nom',
    )
    await flush()
    await assert.rejects(f.exposed().ensureSaved(), /Fiche modifiée/)
    assert.equal(f.writes[0].body.c2.full_name, 'Autre nom')
    assert.equal(f.dirty.at(-1), true)
    assert.deepEqual(f.saved, [3])
    const reload = all(f.root).find(
      (n) => n.tag === 'button' && n.text === 'Recharger la qualification',
    )
    await reload.props.onClick()
    await flush()
    assert.equal(f.exposed().dirty, true)
  } finally {
    f.app.unmount()
  }
})

test('a failed load blocks booking preparation and never sends an empty C2', async () => {
  const f = fixture({ loadFail: true })
  try {
    await flush()
    await assert.rejects(f.exposed().ensureSaved(), /Chargez/)
    assert.equal(f.writes.length, 0)
    assert.equal(f.saved.length, 0)
  } finally {
    f.app.unmount()
  }
})

test('known import fields prefill qualification while saved values and explicit blanks take precedence', async () => {
  const f = fixture({
    defaults: { address: '12 rue Test', city: 'Montréal', postal_code: 'H2X 1Y4' },
    draft: { city: 'Québec', postal_code: '' },
  })
  try {
    await flush()
    set(
      all(f.root).find((n) => n.tag === 'select'),
      false,
    )
    await flush()
    await f.exposed().ensureSaved()
    const fields = f.writes[0].body.c2
    assert.equal(fields.address, '12 rue Test')
    assert.equal(fields.city, 'Québec')
    assert.equal(fields.postal_code, '')
    assert.equal(fields.age, null)
  } finally {
    f.app.unmount()
  }
})
