import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import test from 'node:test'
import assert from 'node:assert/strict'
import { parse, compileScript } from 'vue/compiler-sfc'
import { createRenderer, nextTick } from 'vue'
import ts from 'typescript'
const require = createRequire(import.meta.url)
const vue = pathToFileURL(require.resolve('vue')).href
const url = (code) =>
  'data:text/javascript;base64,' +
  Buffer.from(
    ts.transpileModule(code, {
      compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
    }).outputText,
  ).toString('base64')
const source = (name) => readFileSync(new URL(`../src/${name}.ts`, import.meta.url), 'utf8')
const bookingSource = url(source('booking-time'))
const { bookingInterval } = await import(bookingSource)
let code = compileScript(
  parse(readFileSync(new URL('../src/AssuranceAppointments.vue', import.meta.url), 'utf8'))
    .descriptor,
  {
    id: 'booking-slots',
    inlineTemplate: true,
    templateOptions: { compilerOptions: { hoistStatic: false } },
  },
).content
code = code
  .replace(/from ['"]vue['"]/g, `from '${vue}'`)
  .replace("'./booking-time'", JSON.stringify(bookingSource))
  .replace("'./appointment-status'", JSON.stringify(url(source('appointment-status'))))
  .replace(
    /import (\w+) from ['"]\.\/[^'"]+\.vue['"]/g,
    (_, name) => `const ${name}={render:()=>null}`,
  )
code =
  code
    .replace(/vModelText as _vModelText,?/g, '')
    .replace(/vModelSelect as _vModelSelect,?/g, '')
    .replace(/vModelDynamic as _vModelDynamic,?/g, '') +
  ';const _vModelText={},_vModelSelect={},_vModelDynamic={};'
const component = (await import(url(code))).default
const renderer = createRenderer({
  createElement: (tag) => ({ tag, children: [], props: {}, style: {} }),
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
  for (let i = 0; i < 6; i++) {
    await nextTick()
    await new Promise((resolve) => setImmediate(resolve))
  }
}
// Tomorrow in Toronto, so slots are never in the past whatever the run time.
const tomorrow = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'America/Toronto',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
}).format(new Date(Date.now() + 86400000))
const busy = bookingInterval(`${tomorrow}T10:00`, 'America/Toronto', 60)
function fixture() {
  const root = { children: [] },
    requests = []
  const request = async (path) => {
    requests.push(path)
    if (path.startsWith('assignments/'))
      return {
        count: 1,
        next: null,
        results: [{ id: 5, setter: { name: 'Setter' }, advisor: { name: 'Conseiller Démo 04' } }],
      }
    if (path.startsWith('appointments/availability/')) return { busy: [busy] }
    return { count: 0, next: null, results: [] }
  }
  const app = renderer.createApp(component, {
    role: 'setter',
    compact: true,
    contactId: 42,
    contactRevision: 3,
    leaseToken: 'lease',
    request,
    portal: async () => ({}),
  })
  app.mount(root)
  return { root, requests, close: () => app.unmount() }
}
const slotButtons = (f) =>
  all(f.root).filter((n) => n.tag === 'button' && /^\d{2}:\d{2}$/.test(text(n).trim()))
const slot = (f, label) => slotButtons(f).find((n) => text(n).trim() === label)

test('setter sees the assigned advisor busy times before booking and picks a free slot', async () => {
  const f = fixture()
  try {
    await flush()
    assert.equal(slotButtons(f).length, 0)
    const select = all(f.root).find((n) => n.tag === 'select')
    select.props['onUpdate:modelValue']('5')
    await flush()
    all(f.root)
      .find((n) => n.props?.['aria-label'] === 'Jour suivant')
      .props.onClick()
    await flush()
    const query = new URLSearchParams(
      f.requests
        .filter((p) => p.startsWith('appointments/availability/'))
        .at(-1)
        .split('?')[1],
    )
    assert.equal(query.get('assignment_id'), '5')
    assert.equal(query.get('contact_id'), '42')
    assert.equal(
      query.get('start'),
      bookingInterval(`${tomorrow}T00:00`, 'America/Toronto', 15).starts_at,
    )
    assert.equal(slot(f, '10:00').props.disabled, true)
    assert.equal(slot(f, '10:30').props.disabled, true)
    assert.equal(slot(f, '11:00').props.disabled, false)
    assert.equal(slotButtons(f).length, 24)
    slot(f, '11:00').props.onClick()
    await flush()
    assert.equal(slot(f, '11:00').props['aria-pressed'], true)
    assert.match(text(f.root), /vérifié à la confirmation/)
  } finally {
    f.close()
  }
})
