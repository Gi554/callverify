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
const grid = url(source('calendar-grid').replace("'./booking-time'", JSON.stringify(booking)))
const status = url(source('appointment-status'))
let code = compileScript(
  parse(readFileSync(new URL('../src/CrmAppointmentsCalendar.vue', import.meta.url), 'utf8'))
    .descriptor,
  {
    id: 'admin-calendar',
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
  .replace(/from ['"]vue['"]/g, `from '${vue}'`)
  .replace("'./calendar-grid'", JSON.stringify(grid))
  .replace("'./appointment-status'", JSON.stringify(status))
  .replace(
    /import (\w+) from ['"]\.\/[^'"]+\.vue['"]/g,
    (_, name) =>
      `const ${name}={props:['open','title','role'],setup(p,{slots}){return()=>(${JSON.stringify(name)}==='SidePanel'&&!p.open)?null:stubH('div',{'data-component':${JSON.stringify(name)}},slots.default?.())}}`,
  )
code =
  `import {h as stubH} from '${vue}';` +
  code.replace(/vModelText as _vModelText,?/g, '').replace(/vModelSelect as _vModelSelect,?/g, '') +
  ';const _vModelText={},_vModelSelect={};'
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
// Fixed mid-month dates keep both rows inside the displayed month whatever the run date.
const month = new Date().toISOString().slice(0, 7)
const at = (day, hour) => `${month}-${day}T${hour}:00:00Z`
const assuranceRows = [
  {
    id: 1,
    status: 'scheduled',
    starts_at: at(14, 15),
    ends_at: at(14, 16),
    timezone: 'America/Toronto',
    contact: { name: 'Dossier Alpha' },
    advisor: { id: 7, name: 'Chloé Conseil' },
    setter: { id: 1, name: 'Alice Setter' },
  },
  {
    id: 2,
    status: 'scheduled',
    starts_at: at(15, 15),
    ends_at: at(15, 16),
    timezone: 'America/Toronto',
    contact: { name: 'Dossier Beta' },
    advisor: { id: 7, name: 'Chloé Conseil' },
    setter: { id: 2, name: 'Bruno Setter' },
  },
]
const isolationRows = [
  {
    id: 3,
    status: 'scheduled',
    starts_at: at(14, 15),
    ends_at: at(14, 16),
    timezone: 'America/Toronto',
    prospect: { name: 'Maison Gamma' },
    client: { id: 9, name: 'Client Isolation' },
    original_setter: { id: 1, name: 'Alice Setter' },
    closer: { id: 5, name: 'Dan Closer' },
  },
  {
    id: 4,
    status: 'scheduled',
    starts_at: at(15, 15),
    ends_at: at(15, 16),
    timezone: 'America/Toronto',
    prospect: { name: 'Maison Delta' },
    client: { id: 9, name: 'Client Isolation' },
    original_setter: { id: 1, name: 'Alice Setter' },
    closer: null,
  },
]
function fixture({ workspace = 'assurance', role = 'administrator' } = {}) {
  const root = { children: [] },
    requests = []
  const rows = workspace === 'assurance' ? assuranceRows : isolationRows
  const app = renderer.createApp(component, {
    workspace,
    role,
    request: async (path) => {
      requests.push(path)
      // Mirrors the API: participant parameters narrow the returned rows.
      const query = new URLSearchParams(path.split('?')[1])
      const of = {
        setter_id: (row) => (row.setter || row.original_setter)?.id,
        advisor_id: (row) => row.advisor?.id,
        closer_id: (row) => row.closer?.id,
        client_id: (row) => row.client?.id,
      }
      const results = rows.filter((row) =>
        Object.entries(of).every(
          ([param, get]) => !query.has(param) || String(get(row)) === query.get(param),
        ),
      )
      return { results, count: results.length, next: null }
    },
    portal: async () => ({}),
  })
  app.mount(root)
  return { root, requests, close: () => app.unmount() }
}
const memberSelect = (f) =>
  all(f.root).find((n) => n.tag === 'select' && all(n).some((o) => o.tag === 'optgroup'))
const count = (f) => text(f.root).match(/(\d+) (rendez-vous|visite\(s\)) sur ce mois/)?.[1]
const button = (f, label) => all(f.root).find((n) => n.tag === 'button' && text(n) === label)

test('administrator filters the Assurance team calendar by setter or advisor', async () => {
  const f = fixture()
  try {
    await flush()
    assert.match(text(f.root), /ÉQUIPE ASSURANCE/)
    assert.match(text(f.root), /L’agenda de toute l’équipe/)
    const select = memberSelect(f)
    const groups = all(select).filter((n) => n.tag === 'optgroup')
    assert.deepEqual(
      groups.map((g) => g.props.label),
      ['Setters', 'Conseillers'],
    )
    assert.deepEqual(
      groups.map((g) => text(g)),
      ['Alice SetterBruno Setter', 'Chloé Conseil'],
    )
    assert.equal(count(f), '2')
    select.props['onUpdate:modelValue']('setter:2')
    await flush()
    assert.equal(count(f), '1')
    select.props['onUpdate:modelValue']('advisor:7')
    await flush()
    assert.equal(count(f), '2')
    assert.equal(f.requests.length, 3)
    assert.match(f.requests[0], /[?&]page_size=100(&|$)/)
    assert.doesNotMatch(f.requests[0], /_id=/)
    assert.match(f.requests[1], /[?&]setter_id=2(&|$)/)
    assert.match(f.requests[2], /[?&]advisor_id=7(&|$)/)
    assert.doesNotMatch(f.requests[2], /setter_id/)
    // Members met in earlier loads stay selectable after a filtered load.
    select.props['onUpdate:modelValue']('setter:2')
    await flush()
    const options = all(memberSelect(f))
      .filter((n) => n.tag === 'option')
      .map(text)
    assert.ok(options.includes('Alice Setter') && options.includes('Bruno Setter'))
  } finally {
    f.close()
  }
})

test('administrator can switch to the existing list and back to the calendar', async () => {
  const f = fixture()
  try {
    await flush()
    assert.ok(text(f.root).includes('Réserver un rendez-vous'))
    button(f, 'Liste').props.onClick()
    await flush()
    assert.ok(all(f.root).some((n) => n.props?.['data-component'] === 'AssuranceAppointments'))
    assert.ok(!all(f.root).some((n) => n.props?.class === 'calendar-surface'))
    assert.ok(!text(f.root).includes('Réserver un rendez-vous'))
    button(f, 'Calendrier').props.onClick()
    await flush()
    assert.ok(text(f.root).includes('Réserver un rendez-vous'))
  } finally {
    f.close()
  }
})

test('Isolation team calendar offers setters, closers and clients', async () => {
  const f = fixture({ workspace: 'isolation' })
  try {
    await flush()
    const select = memberSelect(f)
    assert.deepEqual(
      all(select)
        .filter((n) => n.tag === 'optgroup')
        .map((g) => g.props.label),
      ['Setters', 'Closers', 'Clients'],
    )
    select.props['onUpdate:modelValue']('closer:5')
    await flush()
    assert.equal(count(f), '1')
    assert.match(text(f.root), /Maison Gamma/)
    assert.doesNotMatch(text(f.root), /Maison Delta/)
  } finally {
    f.close()
  }
})

test('setter calendar has no team filter or list switch', async () => {
  const f = fixture({ role: 'setter' })
  try {
    await flush()
    assert.equal(memberSelect(f), undefined)
    assert.equal(button(f, 'Liste'), undefined)
    assert.match(text(f.root), /MON ESPACE ASSURANCE/)
  } finally {
    f.close()
  }
})
