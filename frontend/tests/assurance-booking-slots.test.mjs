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
function compile(name, stub) {
  let code = compileScript(
    parse(readFileSync(new URL(`../src/${name}.vue`, import.meta.url), 'utf8')).descriptor,
    {
      id: name,
      inlineTemplate: true,
      templateOptions: { compilerOptions: { hoistStatic: false } },
    },
  ).content
  code = code
    .replace(/from ['"]vue['"]/g, `from '${vue}'`)
    .replace("'./booking-time'", JSON.stringify(bookingSource))
    .replace("'./appointment-status'", JSON.stringify(url(source('appointment-status'))))
    .replace("'./advisor-quota'", JSON.stringify(url(source('advisor-quota'))))
    .replace(/import (\w+) from ['"]\.\/[^'"]+\.vue['"]/g, (_, component) => stub(component))
  code =
    code
      .replace(/vModelText as _vModelText,?/g, '')
      .replace(/vModelSelect as _vModelSelect,?/g, '')
      .replace(/vModelDynamic as _vModelDynamic,?/g, '') +
    ';const _vModelText={},_vModelSelect={},_vModelDynamic={};'
  return import(url(code)).then((module) => module.default)
}
// The booking form only wires the shared grid: capture the props it passes.
globalThis.slotProps = null
const appointments = await compile('AssuranceAppointments', (name) =>
  name === 'AvailabilitySlots'
    ? `const AvailabilitySlots={props:['modelValue','zone','duration','load','loadKey','fullDay'],setup(p){return()=>{globalThis.slotProps=p;return null}}}`
    : `const ${name}={render:()=>null}`,
)
const slotsComponent = await compile(
  'AvailabilitySlots',
  (name) => `const ${name}={render:()=>null}`,
)
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
const dayAfter = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'America/Toronto',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
}).format(new Date(Date.now() + 2 * 86400000))
const busy = bookingInterval(`${tomorrow}T10:00`, 'America/Toronto', 60)
const slotButtons = (root) =>
  all(root).filter((n) => n.tag === 'button' && /^\d{2}:\d{2}$/.test(text(n).trim()))
const slot = (root, label) => slotButtons(root).find((n) => text(n).trim() === label)

test('booking form asks the API for the chosen assignment and prospect busy times', async () => {
  const root = { children: [] },
    requests = []
  const request = async (path) => {
    requests.push(path)
    if (path.startsWith('assignments/'))
      return {
        count: 1,
        next: null,
        results: [{ id: 5, setter: { name: 'S' }, advisor: { name: 'C' } }],
      }
    if (path.startsWith('appointments/availability/'))
      return { busy: [busy], working_hours_enabled: true }
    return { count: 0, next: null, results: [] }
  }
  const app = renderer.createApp(appointments, {
    role: 'setter',
    compact: true,
    contactId: 42,
    contactRevision: 3,
    leaseToken: 'lease',
    request,
    portal: async () => ({}),
  })
  app.mount(root)
  try {
    await flush()
    assert.equal(globalThis.slotProps, null)
    all(root)
      .find((n) => n.tag === 'select')
      .props['onUpdate:modelValue']('5')
    await flush()
    assert.equal(globalThis.slotProps.loadKey, '5:42')
    assert.deepEqual(
      await globalThis.slotProps.load('2026-11-02T00:00:00-05:00', '2026-11-03T00:00:00-05:00'),
      [busy],
    )
    const query = new URLSearchParams(requests.at(-1).split('?')[1])
    assert.equal(query.get('assignment_id'), '5')
    assert.equal(query.get('contact_id'), '42')
    assert.equal(query.get('start'), '2026-11-02T00:00:00-05:00')
    await flush()
    assert.equal(globalThis.slotProps.fullDay, true)
  } finally {
    app.unmount()
  }
})

test('shared grid marks busy slots, keeps free ones selectable and reloads per day', async () => {
  const root = { children: [] },
    windows = [],
    chosen = []
  const app = renderer.createApp(slotsComponent, {
    modelValue: '',
    zone: 'America/Toronto',
    duration: 30,
    label: 'Disponibilités',
    note: 'Agenda externe vérifié à la confirmation.',
    loadKey: 'k',
    load: async (start, end) => {
      windows.push([start, end])
      return [busy]
    },
    'onUpdate:modelValue': (value) => chosen.push(value),
  })
  app.mount(root)
  try {
    await flush()
    all(root)
      .find((n) => n.props?.['aria-label'] === 'Jour suivant')
      .props.onClick()
    await flush()
    assert.deepEqual(windows.at(-1), [
      bookingInterval(`${tomorrow}T00:00`, 'America/Toronto', 15).starts_at,
      bookingInterval(`${dayAfter}T00:00`, 'America/Toronto', 15).starts_at,
    ])
    assert.equal(slotButtons(root).length, 24)
    assert.equal(slot(root, '10:00').props.disabled, true)
    assert.equal(slot(root, '10:30').props.disabled, true)
    assert.equal(slot(root, '11:00').props.disabled, false)
    slot(root, '11:00').props.onClick()
    assert.deepEqual(chosen, [`${tomorrow}T11:00`])
    assert.match(text(root), /Agenda externe vérifié à la confirmation/)
  } finally {
    app.unmount()
  }
})

test('configured hours can offer early slots outside the legacy 8-to-20 grid', async () => {
  const root = { children: [] }
  const app = renderer.createApp(slotsComponent, {
    modelValue: '',
    zone: 'America/Toronto',
    duration: 30,
    label: 'Horaires',
    note: '',
    loadKey: 'hours',
    fullDay: true,
    load: async (start) => [
      {
        starts_at: start,
        ends_at: bookingInterval(`${tomorrow}T07:00`, 'America/Toronto', 30).starts_at,
      },
    ],
  })
  app.mount(root)
  try {
    await flush()
    all(root)
      .find((n) => n.props?.['aria-label'] === 'Jour suivant')
      .props.onClick()
    await flush()
    assert.equal(slotButtons(root).length, 48)
    assert.equal(slot(root, '06:30').props.disabled, true)
    assert.equal(slot(root, '07:00').props.disabled, false)
  } finally {
    app.unmount()
  }
})
