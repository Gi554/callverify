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
  parse(readFileSync(new URL('../src/PhoneHistory.vue', import.meta.url), 'utf8')).descriptor,
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
function fixture({ fail = false } = {}) {
  const root = { children: [] },
    requests = [],
    portalCalls = []
  const app = renderer.createApp(component, {
    workspace: 'isolation',
    resourceId: 7,
    request: async (path, body) => {
      requests.push({ path, body })
      return { proof: 'signed-history' }
    },
    portal: async (path, body) => {
      portalCalls.push({ path, body })
      if (fail) throw new Error('Historique indisponible')
      return {
        count: 27,
        page: body.page,
        has_next: body.page === 1,
        starts_on: body.starts_on,
        ends_on: body.ends_on,
        timezone: 'America/Toronto',
        extension: '501',
        assignment_since: '2026-10-01T00:00:00Z',
        checked_at: '2026-10-22T12:00:00Z',
        source: 'NEWT 511',
        definition: 'Pas une preuve de décrochage',
        results: [{ local_date: body.starts_on, local_time: '10:00:00', duration_raw: '8' }],
      }
    },
  })
  app.mount(root)
  return { root, requests, portalCalls, app }
}
function set(node, value) {
  node.props['onUpdate:modelValue'](value)
}
async function submit(f) {
  await all(f.root)
    .find((n) => n.tag === 'form')
    .props.onSubmit({ preventDefault() {} })
  await flush()
}

test('history is loaded only on explicit consultation with a read-only proof and applied dates', async () => {
  const f = fixture()
  try {
    await flush()
    assert.equal(f.requests.length, 0)
    assert.equal(f.portalCalls.length, 0)
    const inputs = all(f.root).filter((n) => n.tag === 'input')
    set(inputs[0], '2026-10-15')
    set(inputs[1], '2026-10-16')
    await submit(f)
    assert.equal(f.requests[0].path, 'work-queue/7/phone-history-proof/')
    assert.deepEqual(f.requests[0].body, {})
    assert.equal(f.portalCalls[0].path, 'isolation/phone-history/')
    assert.equal(f.portalCalls[0].body.proof, 'signed-history')
    assert.equal(f.portalCalls[0].body.starts_on, '2026-10-15')
    set(inputs[0], '2026-10-01')
    await flush()
    await all(f.root)
      .find((n) => n.tag === 'button' && n.text === 'Suivant')
      .props.onClick()
    await flush()
    assert.equal(f.portalCalls[1].body.page, 2)
    assert.equal(f.portalCalls[1].body.starts_on, '2026-10-15')
    assert.equal(f.requests.length, 2)
  } finally {
    f.app.unmount()
  }
})

test('provider errors are displayed as unavailable, never as an empty successful history', async () => {
  const f = fixture({ fail: true })
  try {
    await flush()
    await submit(f)
    assert.ok(
      all(f.root).some((n) => n.props?.role === 'alert' && n.text === 'Historique indisponible'),
    )
    assert.equal(
      all(f.root).some((n) => n.tag === 'table'),
      false,
    )
    assert.equal(f.portalCalls.length, 1)
  } finally {
    f.app.unmount()
  }
})
