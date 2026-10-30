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

const booking = url(source('booking-time'))
let code = compileScript(
  parse(readFileSync(new URL('../src/AssuranceTransmission.vue', import.meta.url), 'utf8'))
    .descriptor,
  {
    id: 'transmission',
    inlineTemplate: true,
    templateOptions: { compilerOptions: { hoistStatic: false } },
  },
)
  .content.replace(/from ['"]vue['"]/g, `from '${vue}'`)
  .replace("'./booking-time'", JSON.stringify(booking))
  .replace(
    /import AssuranceAppointments from [^;]+;/,
    'const AssuranceAppointments={render:()=>null};',
  )
code =
  code
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

function fixture({ multiple = false, failOnce = false } = {}) {
  const root = { children: [] },
    calls = [],
    booked = []
  const assignments = [
    {
      id: 1,
      advisor: { id: 31, name: 'Conseiller' },
      booking_url: 'https://bookings.cloud.microsoft/book/demo@example.com/',
    },
  ]
  if (multiple)
    assignments.push({
      id: 2,
      advisor: { id: 32, name: 'Autre conseiller' },
      booking_url: 'https://calendly.com/other',
    })
  const app = renderer.createApp(component, {
    contactId: 7,
    contactRevision: 2,
    leaseToken: 'lease',
    role: 'setter',
    prepare: async () => {},
    qualification: () => ({ age: 42, advisor_notes: 'Préparer' }),
    portal: async () => ({ proof: 'proof' }),
    request: async (path, body) => {
      calls.push({ path, body })
      if (!body) return { results: assignments, count: assignments.length }
      if (failOnce) {
        failOnce = false
        throw new Error('Réponse interrompue, réessayez')
      }
      return { id: 80, contact_revision: 3, call_outcome_recorded: true }
    },
    onBooked: (row) => booked.push(row),
  })
  app.mount(root)
  return { root, calls, booked, close: () => app.unmount() }
}
const field = (f, label) =>
  all(f.root)
    .find((n) => n.tag === 'label' && text(n).startsWith(label))
    ?.children.find((n) => ['input', 'select'].includes(n.tag))
async function fill(f) {
  field(f, 'Date').props['onUpdate:modelValue']('2031-07-15')
  field(f, 'Heure').props['onUpdate:modelValue']('14:30')
  field(f, ' Le rendez-vous').props['onUpdate:modelValue'](true)
  await flush()
}
const submit = (f) =>
  all(f.root)
    .filter((n) => n.tag === 'form')[1]
    .props.onSubmit({ preventDefault() {} })

test('one advisor is preselected and submission sends qualification and confirmed external meeting together', async () => {
  const f = fixture()
  try {
    await flush()
    const link = all(f.root).find((n) => n.tag === 'a')
    assert.equal(link.props.target, '_blank')
    assert.equal(link.props.href, 'https://bookings.cloud.microsoft/book/demo@example.com/')
    await fill(f)
    await submit(f)
    await flush()
    const sent = f.calls.find((c) => c.path === 'appointments/transmit/').body
    assert.equal(sent.assignment_id, 1)
    assert.equal(sent.qualification.age, 42)
    assert.equal(sent.contact_revision, 2)
    assert.equal(sent.meeting_type, 'video')
    assert.equal(sent.external_confirmed, true)
    assert.equal(Date.parse(sent.starts_at), Date.parse('2031-07-15T18:30:00Z'))
    assert.equal(f.booked.length, 1)
    assert.ok(!f.calls.some((c) => c.path.includes('availability')))
  } finally {
    f.close()
  }
})

test('several advisors require a choice; an unconfirmed booking is never sent', async () => {
  const f = fixture({ multiple: true })
  try {
    await flush()
    assert.equal(
      all(f.root).find((n) => n.tag === 'a'),
      undefined,
    )
    await submit(f)
    await flush()
    assert.ok(!f.calls.some((c) => c.path === 'appointments/transmit/'))
    assert.match(text(f.root), /Réservez dans le lien/)
  } finally {
    f.close()
  }
})

test('a failed response keeps the draft and request id for a safe retry', async () => {
  const f = fixture({ failOnce: true })
  try {
    await flush()
    await fill(f)
    await submit(f)
    await flush()
    assert.match(text(f.root), /Réponse interrompue/)
    assert.equal(f.booked.length, 0)
    await submit(f)
    await flush()
    const sent = f.calls.filter((c) => c.path === 'appointments/transmit/')
    assert.equal(sent[0].body.request_id, sent[1].body.request_id)
    assert.equal(f.booked.length, 1)
  } finally {
    f.close()
  }
})
