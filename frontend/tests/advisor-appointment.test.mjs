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
let code = compileScript(
  parse(readFileSync(new URL('../src/AssuranceAdvisorAppointment.vue', import.meta.url), 'utf8'))
    .descriptor,
  {
    id: 'advisor-detail',
    inlineTemplate: true,
    templateOptions: { compilerOptions: { hoistStatic: false } },
  },
).content
code = code
  .replace(/import \{([^}]+)\} from 'lucide-vue-next'/g, (_, names) =>
    names
      .split(',')
      .filter((n) => n.trim())
      .map((n) => `const ${n.trim()}={render:()=>null}`)
      .join(';'),
  )
  .replace(/from ['"]vue['"]/g, `from '${vue}'`)
  .replace(
    /import (\w+) from ['"]\.\/[^'"]+\.vue['"]/g,
    (_, name) => `const ${name}={props:['snapshot'],render:()=>null}`,
  )
for (const directive of ['vModelText', 'vModelSelect', 'vModelRadio', 'vModelCheckbox'])
  code =
    code.replace(new RegExp(directive + ' as _' + directive + ',?', 'g'), '') +
    `;const _${directive}={};`
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
  for (let i = 0; i < 5; i++) {
    await nextTick()
    await new Promise((resolve) => setImmediate(resolve))
  }
}

function fixture({ legacy = false, reject = false } = {}) {
  const root = { children: [] },
    calls = [],
    updates = []
  const appt = {
    id: 7,
    revision: 0,
    status: 'scheduled',
    starts_at: '2020-01-01T14:00:00Z',
    ends_at: '2020-01-01T15:00:00Z',
    timezone: 'America/Toronto',
    advisor: { name: 'Advisor' },
    contact: { name: 'Client', phone: 'raw' },
    qualification_snapshot: { original: true },
  }
  const record = {
    revision: 3,
    name: 'Client',
    phone: 'raw',
    email: 'raw import',
    fields: [{ key: 'age', label: 'Âge', type: 'number', min: 0, max: 120 }],
    qualification: { age: 45 },
  }
  const report = legacy
    ? {
        performed: true,
        outcome: 'performed',
        problem: false,
        note: 'Old note',
        sale_concluded: null,
      }
    : null
  const app = renderer.createApp(component, {
    appointmentId: 7,
    request: async (path, body) => {
      calls.push({ path, body })
      if (body && reject) throw new Error('Fiche modifiée : rechargez')
      if (path.endsWith('/client-record/'))
        return body ? { ...record, ...body } : structuredClone(record)
      if (path.endsWith('/advisor-result/'))
        return body ? { result: body, revision: 1 } : { result: report }
      return structuredClone(appt)
    },
    onUpdated: (row) => updates.push(row),
  })
  const exposed = app.mount(root)
  return { root, calls, updates, exposed, close: () => app.unmount() }
}
const button = (f, label) => all(f.root).find((n) => n.tag === 'button' && text(n).includes(label))
const input = (f, name, value) =>
  all(f.root).find((n) => n.tag === 'input' && n.props.name === name && n.props.value === value)
const forms = (f) => all(f.root).filter((n) => n.tag === 'form')

test('advisor explicitly records attendance and sale without an implicit yes/no default', async () => {
  const f = fixture()
  try {
    await flush()
    assert.equal(button(f, 'Enregistrer le résultat').props.disabled, true)
    input(f, 'attendance', 'true').props['onUpdate:modelValue']('true')
    input(f, 'sale', 'false').props['onUpdate:modelValue']('false')
    await flush()
    await forms(f)[0].props.onSubmit({ preventDefault() {} })
    await flush()
    const sent = f.calls.find((c) => c.body)?.body
    assert.equal(sent.performed, true)
    assert.equal(sent.sale_concluded, false)
    assert.equal(sent.revision, 0)
    assert.match(text(f.root), /Résultat du rendez-vous enregistré/)
    assert.equal(f.updates[0].revision, 1)
  } finally {
    f.close()
  }
})
test('legacy report shows unknown sale and asks for a correction reason', async () => {
  const f = fixture({ legacy: true })
  try {
    await flush()
    assert.match(text(f.root), /Vente non renseignée/)
    assert.match(text(f.root), /Motif de la correction/)
    assert.equal(button(f, 'Enregistrer la correction').props.disabled, true)
  } finally {
    f.close()
  }
})
test('client conflict retains edits and panel close protects unsaved work', async () => {
  const f = fixture({ reject: true })
  const previous = globalThis.window
  try {
    await flush()
    const name = all(f.root).find((n) => n.tag === 'input' && n.props.maxlength === '250')
    name.props['onUpdate:modelValue']('Changed name')
    await flush()
    await forms(f)[1].props.onSubmit({ preventDefault() {} })
    await flush()
    assert.match(text(f.root), /Fiche modifiée/)
    globalThis.window = { confirm: () => false }
    assert.equal(f.exposed.close(), false)
    globalThis.window = { confirm: () => true }
    assert.equal(f.exposed.close(), true)
    const sent = f.calls.find((c) => c.body)?.body
    assert.equal(sent.name, 'Changed name')
    assert.equal(sent.revision, 3)
  } finally {
    globalThis.window = previous
    f.close()
  }
})
