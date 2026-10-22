import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import test from 'node:test'
import assert from 'node:assert/strict'
import { parse, compileScript } from 'vue/compiler-sfc'
import { createRenderer, nextTick, h } from 'vue'
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
  parse(readFileSync(new URL('../src/CrmOverview.vue', import.meta.url), 'utf8')).descriptor,
  {
    id: 'admin-home',
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
  .replace(/from ['"]vue['"]/g, `from '${pathToFileURL(require.resolve('vue')).href}'`)
const component = (await import(url(code))).default
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
const text = (n) => (n.text || '') + (n.children || []).map(text).join('')
const today = new Date(Date.now() + 86400000).toISOString()
function fixture({
  workspace = 'assurance',
  role = 'administrator',
  summary = {},
  fail = '',
} = {}) {
  const root = { children: [] },
    requests = [],
    navigations = []
  const request = async (path) => {
    requests.push(path)
    if (fail && path.startsWith(fail)) throw new Error('Service indisponible')
    if (path === 'follow-ups/summary/') return { open: 7, overdue: 2, closed: 4, total: 11 }
    if (path.startsWith('follow-ups/?state=overdue')) return { count: 4, results: [] }
    if (path === 'statistics/')
      return {
        from: '2026-09-22',
        to: '2026-10-22',
        totals: { performed: 0, not_performed: 0, cancelled: 0, upcoming: 0 },
      }
    return {
      results: [
        {
          id: 1,
          status: 'scheduled',
          starts_at: today,
          timezone: 'America/Toronto',
          contact: { name: 'Dossier Alpha' },
          prospect: { name: 'Dossier Alpha' },
        },
      ],
    }
  }
  const app = renderer.createApp({
    render: () =>
      h(
        component,
        {
          workspace,
          role,
          username: 'Admin de recette',
          summary: { contacts: 40, prospects: 40, ...summary },
          request,
          onNavigate: (value) => navigations.push(value),
        },
        { default: () => h('div', 'Alertes des mandats') },
      ),
  })
  app.mount(root)
  return { root, requests, navigations, close: () => app.unmount() }
}
const button = (f, label) => all(f.root).find((n) => n.tag === 'button' && text(n).includes(label))

test('Assurance administrator home shows team counters, agenda and alerts without writing', async () => {
  const f = fixture()
  try {
    await flush()
    const page = text(f.root)
    assert.match(page, /Assurance · Administration/)
    assert.match(page, /Prospects.*40/)
    assert.match(page, /Tâches ouvertes.*7/)
    assert.match(page, /Tâches en retard.*2/)
    assert.match(page, /Prochains rendez-vous de l’équipe/)
    assert.match(page, /Dossier Alpha/)
    assert.match(page, /Alertes des mandats/)
    assert.ok(f.requests.includes('follow-ups/summary/'))
    assert.ok(!f.requests.includes('statistics/'))
    button(f, 'Tâches en retard').props.onClick()
    button(f, 'Affectations').props.onClick()
    assert.deepEqual(f.navigations, ['followups', 'assignments'])
  } finally {
    f.close()
  }
})

test('Isolation administrator home counts overdue reminders and unassigned prospects', async () => {
  const f = fixture({ workspace: 'isolation', summary: { open_follow_ups: 5, unassigned: 3 } })
  try {
    await flush()
    const page = text(f.root)
    assert.match(page, /Isolation · Administration/)
    assert.match(page, /Tâches ouvertes.*5/)
    assert.match(page, /Tâches en retard.*4/)
    assert.match(page, /3 prospect\(s\).*Sans affectation/)
    assert.match(page, /Prochaines visites de l’équipe/)
    assert.doesNotMatch(page, /Alertes des mandats/)
    assert.ok(f.requests.includes('follow-ups/?state=overdue'))
    assert.ok(!f.requests.includes('follow-ups/summary/'))
  } finally {
    f.close()
  }
})

test('failed task counters are shown as unavailable rather than zero', async () => {
  const f = fixture({ fail: 'follow-ups/' })
  try {
    await flush()
    const page = text(f.root)
    assert.match(page, /Tâches ouvertes.*Indisponible/)
    assert.match(page, /Tâches en retard.*Indisponible/)
    assert.match(page, /Compteurs de tâches indisponibles : Service indisponible/)
    assert.match(page, /Dossier Alpha/)
  } finally {
    f.close()
  }
})

test('setter home keeps its own view and loads no team counters', async () => {
  const f = fixture({ role: 'setter' })
  try {
    await flush()
    assert.doesNotMatch(text(f.root), /Administration/)
    assert.ok(!f.requests.some((path) => path.startsWith('follow-ups/')))
  } finally {
    f.close()
  }
})
