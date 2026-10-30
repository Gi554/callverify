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
  parse(readFileSync(new URL('../src/AssuranceContactFollowups.vue', import.meta.url), 'utf8'))
    .descriptor,
  { id: 'callbacks', inlineTemplate: true },
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
  code.replace(/vModelText as _vModelText,?/g, '').replace(/vModelSelect as _vModelSelect,?/g, '') +
  ';const _vModelText={},_vModelSelect={};'
const component = (await import(url(code))).default
globalThis.document = { activeElement: null }
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
function fixture() {
  const root = { children: [] },
    writes = [],
    events = []
  let exposed
  const app = renderer.createApp({
    setup: () => () =>
      h(component, {
        ref: (ref) => (exposed = ref),
        contactId: 7,
        revision: 3,
        token: 'lease',
        prepare: async () => {},
        request: async (path, body) => {
          if (body) {
            writes.push({ path, body })
            return { id: 5 }
          }
          return { results: [], count: 0 }
        },
        onQualify: () => events.push('qualify'),
        onSaved: () => events.push('saved'),
        onAdvance: () => events.push('advance'),
      }),
  })
  app.mount(root)
  return { root, writes, events, app, exposed: () => exposed }
}
function set(node, value) {
  node.props['onUpdate:modelValue'](value)
}
const event = { preventDefault() {}, target: {} }
test('callback saves a dated declared outcome without calling telephony', async () => {
  const f = fixture()
  try {
    await flush()
    let nodes = all(f.root)
    set(
      nodes.find((n) => n.tag === 'select'),
      'callback',
    )
    await flush()
    nodes = all(f.root)
    set(
      nodes.find((n) => n.tag === 'textarea'),
      'Rappeler demain',
    )
    set(
      nodes.find((n) => n.tag === 'input' && n.props.type === 'datetime-local'),
      '2027-01-14T10:00',
    )
    nodes.find((n) => n.tag === 'form').props.onSubmit(event)
    await flush()
    assert.equal(f.writes.length, 1)
    assert.equal(f.writes[0].path, 'contacts/7/call-outcomes/')
    assert.equal(f.writes[0].body.result, 'callback')
    assert.match(f.writes[0].body.due_at, /10:00:00-05:00$/)
    assert.ok(f.events.includes('saved'))
  } finally {
    f.app.unmount()
  }
})
test('appointment result opens qualification and waits for a successful booking', async () => {
  const f = fixture()
  try {
    await flush()
    const select = all(f.root).find((n) => n.tag === 'select')
    set(select, 'appointment_booked')
    select.props.onChange(event)
    await flush()
    assert.deepEqual(f.events, ['qualify'])
    assert.equal(f.writes.length, 0)
    await f.exposed().booked({ id: 42 })
    await flush()
    assert.equal(f.writes.length, 1)
    assert.equal(f.writes[0].body.appointment_id, 42)
  } finally {
    f.app.unmount()
  }
})

test('non qualifying outcomes save before advancing and keep the seven requested choices', async () => {
  for (const result of ['voicemail', 'invalid_number', 'disconnected']) {
    const f = fixture()
    try {
      await flush()
      const select = all(f.root).find((n) => n.tag === 'select')
      const options = all(select)
        .filter((n) => n.tag === 'option')
        .map((n) => n.props.value)
      assert.ok(options.includes('other'))
      assert.ok(!options.includes('unreachable'))
      set(select, result)
      select.props.onChange(event)
      await flush()
      await all(f.root)
        .find((n) => n.tag === 'form')
        .props.onSubmit(event)
      await flush()
      assert.equal(f.writes[0].body.result, result)
      assert.ok(f.events.includes('advance'))
      assert.ok(!f.events.includes('qualify'))
    } finally {
      f.app.unmount()
    }
  }
})
