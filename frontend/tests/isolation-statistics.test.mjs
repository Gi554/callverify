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
  parse(readFileSync(new URL('../src/IsolationStatistics.vue', import.meta.url), 'utf8'))
    .descriptor,
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
const clicks = []
globalThis.document.createElement = () => ({
  click() {
    clicks.push(this.download)
  },
})
URL.createObjectURL = () => 'blob:statistics-test'
URL.revokeObjectURL = () => {}
function fixture() {
  const root = { children: [] },
    requests = [],
    state = { fail: false }
  const app = renderer.createApp(component, {
    role: 'administrator',
    request: async (path) => {
      requests.push(path)
      const query = new URL(path, 'http://test').searchParams
      if (state.fail) throw new Error('Rapport indisponible')
      if (query.has('export')) return new Blob(['csv'])
      const group = query.get('group')
      return {
        from: '2026-10-19',
        to: '2026-10-25',
        timezone: query.get('timezone'),
        group,
        as_of: '2026-10-22T12:00:00Z',
        definition: 'Définition du rapport',
        totals: {
          visits: 20,
          performed: 15,
          not_performed: 5,
          closed: 5,
          closing_rate: 33.33,
          performed_rate: 75,
          closure_unknown: 0,
        },
        [group + 's']: {
          count: 27,
          results: [],
          next: 'page2',
          previous: query.get('page') === '2' ? 'page1' : null,
        },
      }
    },
  })
  app.mount(root)
  return { root, requests, state, app }
}
function set(node, value) {
  node.props['onUpdate:modelValue'](value)
}
async function apply(f) {
  await all(f.root)
    .find((n) => n.tag === 'form')
    .props.onSubmit({ preventDefault() {} })
  await flush()
}

test('weekly Canadian report exports the applied grouping even when draft filters change', async () => {
  const f = fixture()
  try {
    await flush()
    const first = new URL(f.requests[0], 'http://test').searchParams
    assert.ok(first.has('week_of'))
    assert.equal(first.get('timezone'), 'America/Toronto')
    const selects = all(f.root).filter((n) => n.tag === 'select')
    set(selects.at(-1), 'closer')
    await flush()
    assert.equal(f.requests.length, 1)
    await all(f.root)
      .find((n) => n.tag === 'button' && n.text === 'Télécharger CSV')
      .props.onClick()
    await flush()
    const exported = new URL(f.requests.at(-1), 'http://test').searchParams
    assert.equal(exported.get('export'), 'csv')
    assert.equal(exported.get('group'), 'setter')
    assert.equal(clicks.at(-1), 'statistiques-isolation-2026-10-19-2026-10-25.csv')
    await apply(f)
    assert.equal(new URL(f.requests.at(-1), 'http://test').searchParams.get('group'), 'closer')
  } finally {
    f.app.unmount()
  }
})

test('custom range replaces week and pagination keeps applied criteria', async () => {
  const f = fixture()
  try {
    await flush()
    set(all(f.root).filter((n) => n.tag === 'select')[0], 'custom')
    await flush()
    const dates = all(f.root).filter((n) => n.tag === 'input' && n.props.type === 'date')
    set(dates[0], '2026-10-01')
    set(dates[1], '2026-10-20')
    await apply(f)
    let query = new URL(f.requests.at(-1), 'http://test').searchParams
    assert.equal(query.has('week_of'), false)
    assert.equal(query.get('from'), '2026-10-01')
    assert.equal(query.get('to'), '2026-10-20')
    set(dates[0], '2026-09-01')
    await flush()
    await all(f.root)
      .find((n) => n.tag === 'button' && n.text === 'Suivant')
      .props.onClick()
    await flush()
    query = new URL(f.requests.at(-1), 'http://test').searchParams
    assert.equal(query.get('page'), '2')
    assert.equal(query.get('from'), '2026-10-01')
  } finally {
    f.app.unmount()
  }
})

test('a failed recalculation removes stale figures and download actions', async () => {
  const f = fixture()
  try {
    await flush()
    f.state.fail = true
    await apply(f)
    assert.ok(
      all(f.root).some((n) => n.props?.role === 'alert' && n.text === 'Rapport indisponible'),
    )
    assert.equal(
      all(f.root).some((n) => n.tag === 'button' && n.text === 'Télécharger Excel'),
      false,
    )
  } finally {
    f.app.unmount()
  }
})
