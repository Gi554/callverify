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
  parse(readFileSync(new URL('../src/IsolationVisits.vue', import.meta.url), 'utf8')).descriptor,
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
code = code
  .replace(/import (\w+) from ['"]\.\/[^'"]+\.vue['"]/g, (_, name) =>
    name === 'IsolationC2'
      ? `const IsolationC2={setup(props,{expose,emit}){expose({async ensureSaved(){globalThis.c2Booking.events.push('c2');if(globalThis.c2Booking.fail)throw new Error('Conflit C2');emit('saved',7)}});return ()=>null}}`
      : `const ${name}={render:()=>null}`,
  )
  .replace(/vShow as _vShow,?/g, '')
code =
  code
    .replace(/vModelText as _vModelText,?/g, '')
    .replace(/vModelSelect as _vModelSelect,?/g, '')
    .replace(/vModelDynamic as _vModelDynamic,?/g, '') +
  ';const _vModelText={},_vModelSelect={},_vModelDynamic={},_vShow={};'
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
function fixture({ fail = false, google = false, publicationFail = false } = {}) {
  const root = { children: [] },
    writes = [],
    events = []
  globalThis.c2Booking = { fail, events }
  const app = renderer.createApp(component, {
    prospectId: 7,
    role: 'setter',
    portal: async (path) => {
      if (path === 'internal/isolation/publish-visit/') {
        events.push('publication')
        if (publicationFail) throw new Error('Indisponible')
        return { state: 'synced' }
      }
      events.push('proof')
      return { proof: 'signed-proof' }
    },
    request: async (path, body) => {
      if (body) {
        events.push('booking')
        writes.push({ path, body })
        return { id: 42, ...(google ? { publication_proof: 'signed-publication' } : {}) }
      }
      if (path.startsWith('work-queue/'))
        return { id: 7, name: 'Client', revision: 3, assigned_setter: { id: 21 } }
      return { results: [], count: 0 }
    },
  })
  app.mount(root)
  return { root, writes, events, app }
}
async function submit(f) {
  const input = all(f.root).find((n) => n.tag === 'input' && n.props.type === 'datetime-local')
  input.props['onUpdate:modelValue']('2030-12-01T10:00')
  await flush()
  const form = all(f.root).find((n) => n.tag === 'form')
  await form.props.onSubmit({ preventDefault() {} })
  await flush()
}

test('Isolation booking awaits C2 saving and sends its new revision with an explicit Canadian instant', async () => {
  const f = fixture()
  try {
    await flush()
    await submit(f)
    assert.deepEqual(f.events, ['c2', 'proof', 'booking'])
    assert.equal(f.writes[0].path, 'visits/')
    assert.equal(f.writes[0].body.revision, 7)
    assert.equal(f.writes[0].body.prospect_id, 7)
    assert.equal(f.writes[0].body.starts_at, '2030-12-01T10:00:00-05:00')
    assert.equal(f.writes[0].body.ends_at, '2030-12-01T11:00:00-05:00')
    assert.equal(f.writes[0].body.proof, 'signed-proof')
  } finally {
    f.app.unmount()
  }
})

test('a failed C2 save stops booking before any proof or visit request', async () => {
  const f = fixture({ fail: true })
  try {
    await flush()
    await submit(f)
    assert.deepEqual(f.events, ['c2'])
    assert.equal(f.writes.length, 0)
    assert.ok(all(f.root).some((n) => n.props?.role === 'alert' && n.text === 'Conflit C2'))
  } finally {
    f.app.unmount()
  }
})

test('Google publication follows the committed booking and a failure never posts a second visit', async () => {
  for (const publicationFail of [false, true]) {
    const f = fixture({ google: true, publicationFail })
    try {
      await flush()
      await submit(f)
      assert.deepEqual(f.events, ['c2', 'proof', 'booking', 'publication'])
      assert.equal(f.writes.length, 1)
      assert.equal(f.writes[0].body.publication, 'google')
      if (publicationFail)
        assert.ok(
          all(f.root).some(
            (n) => n.props?.role === 'status' && String(n.text).includes('conservée dans Orvia'),
          ),
        )
    } finally {
      f.app.unmount()
    }
  }
})
