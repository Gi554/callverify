import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import test from 'node:test'
import assert from 'node:assert/strict'
import { parse, compileScript } from 'vue/compiler-sfc'
import { createRenderer, nextTick } from 'vue'
import ts from 'typescript'
import { withStatComponents } from './stat-components.mjs'
const require = createRequire(import.meta.url)
const vue = pathToFileURL(require.resolve('vue')).href
let code = compileScript(
  parse(readFileSync(new URL('../src/AssuranceStatistics.vue', import.meta.url), 'utf8'))
    .descriptor,
  {
    id: 'assurance-statistics',
    inlineTemplate: true,
    templateOptions: { compilerOptions: { hoistStatic: false } },
  },
).content
code =
  code
    .replace(/import \{([^}]+)\} from 'lucide-vue-next'/g, (_, names) =>
      names
        .split(',')
        .filter((name) => name.trim())
        .map((name) => `const ${name.trim()}={render:()=>null}`)
        .join(';'),
    )
    .replace(/from ['"]vue['"]/g, `from '${vue}'`)
    .replace(/vModelText as _vModelText,?/g, '') + ';const _vModelText={};'
code = withStatComponents(code)
const component = (
  await import(
    'data:text/javascript;base64,' +
      Buffer.from(
        ts.transpileModule(code, {
          compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
        }).outputText,
      ).toString('base64')
  )
).default
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
const totals = {
  appointments: 600,
  cancelled: 60,
  upcoming: 0,
  reported: 447,
  performed: 348,
  not_performed: 99,
  absent: 99,
  other_not_performed: 0,
  reports_due: 93,
  problem_reports: 0,
  incidents: 0,
  open_tasks: 4,
  overdue_tasks: 1,
  closed_tasks: 7,
  performed_rate: 77.85,
}
function fixture(role = 'administrator', extra = {}) {
  const root = { children: [] },
    requests = []
  const request = async (path) => {
    requests.push(path)
    return {
      as_of: '2026-10-23T01:52:40Z',
      definition: 'Définition des indicateurs.',
      totals,
      ...extra,
      setters:
        role === 'administrator'
          ? {
              count: 1,
              next: null,
              previous: null,
              results: [
                {
                  setter_id: 4,
                  setter_name: 'Setter Démo 03',
                  appointments: 60,
                  performed: 24,
                  not_performed: 25,
                  absent: 25,
                  other_not_performed: 0,
                  reports_due: 11,
                  open_tasks: 2,
                  overdue_tasks: 1,
                  performed_rate: 48.98,
                },
              ],
            }
          : null,
    }
  }
  const app = renderer.createApp(component, { role, request })
  app.mount(root)
  return { root, requests, close: () => app.unmount() }
}

test('statistics lead with key figures, team detail and a folded methodology', async () => {
  const f = fixture()
  try {
    await flush()
    const page = text(f.root)
    assert.match(page, /Rendez-vous600/)
    assert.match(page, /Taux effectué77,9 %/)
    assert.match(page, /Rendez-vous effectués348Sur 447 comptes rendus renseignés/)
    assert.match(page, /Comptes rendus manquants93/)
    assert.match(page, /4Tâches ouvertes/)
    assert.match(page, /toute l’équipe/)
    assert.match(page, /Setter Démo 03/)
    assert.doesNotMatch(page, /\(4\)/)
    assert.match(page, /dont 25 absents/)
    const badge = all(f.root).find((n) => String(n.props?.class || '').includes('stats-badge'))
    assert.match(String(badge.props.class), /warning/)
    assert.ok(
      all(f.root).some((n) => n.tag === 'details' && /Définition des indicateurs/.test(text(n))),
    )
  } finally {
    f.close()
  }
})

test('a quick period fills the dates and recomputes', async () => {
  const f = fixture()
  try {
    await flush()
    all(f.root)
      .find((n) => n.tag === 'button' && text(n).trim() === '7 jours')
      .props.onClick()
    await flush()
    const query = new URLSearchParams(f.requests.at(-1).split('?')[1])
    const today = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'America/Toronto',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(new Date())
    const expectedFrom = new Date(new Date(today + 'T12:00:00Z').getTime() - 6 * 86400000)
      .toISOString()
      .slice(0, 10)
    assert.equal(query.get('from'), expectedFrom)
    assert.equal(query.get('to'), today)
    assert.equal(query.get('page'), '1')
    const active = all(f.root).find((n) => n.tag === 'button' && n.props['aria-pressed'] === true)
    assert.equal(text(active).trim(), '7 jours')
  } finally {
    f.close()
  }
})

test('setters see their own scope without the team table', async () => {
  const f = fixture('setter')
  try {
    await flush()
    assert.match(text(f.root), /vos rendez-vous/)
    assert.doesNotMatch(text(f.root), /Détail par setter/)
  } finally {
    f.close()
  }
})

test('indicators compare with the previous period and chart each day', async () => {
  const f = fixture('administrator', {
    previous: {
      from: '2026-08-26',
      to: '2026-09-24',
      totals: { ...totals, appointments: 500, performed_rate: 70, reports_due: 100 },
    },
    daily: [
      { day: '2026-10-21', appointments: 3, performed: 1, cancelled: 0 },
      { day: '2026-10-22', appointments: 5, performed: 4, cancelled: 1 },
      { day: '2026-10-23', appointments: 2, performed: 0, cancelled: 0 },
    ],
  })
  try {
    await flush()
    const badges = all(f.root)
      .filter((n) => String(n.props?.class || '').startsWith('kpi-trend'))
      .map((n) => [text(n), n.props.class])
    assert.deepEqual(badges, [
      ['+20 %', 'kpi-trend good'],
      ['0 %', 'kpi-trend flat'],
      ['+7,8 pt', 'kpi-trend good'],
      ['-7 %', 'kpi-trend good'],
    ])
    const groups = all(f.root).filter(
      (n) => n.props?.class?.[0] === 'bars-group' || n.props?.class === 'bars-group',
    )
    assert.equal(groups.length, 3)
    assert.match(groups[1].props['aria-label'], /Réservés 5, Effectués 4/)
    assert.ok(all(f.root).some((n) => n.tag === 'path' && /^M0.0,/.test(n.props.d)))
  } finally {
    f.close()
  }
})

test('month presets use the Québec date when UTC has already crossed midnight', async () => {
  const RealDate = globalThis.Date
  globalThis.Date = class extends RealDate {
    constructor(...args) {
      super(...(args.length ? args : ['2026-11-01T02:30:00Z']))
    }
    static now() {
      return new RealDate('2026-11-01T02:30:00Z').getTime()
    }
  }
  const f = fixture()
  try {
    await flush()
    all(f.root)
      .find((n) => n.tag === 'button' && text(n).trim() === 'Ce mois')
      .props.onClick()
    await flush()
    let query = new URLSearchParams(f.requests.at(-1).split('?')[1])
    assert.equal(query.get('from'), '2026-10-01')
    assert.equal(query.get('to'), '2026-10-31')
    all(f.root)
      .find((n) => n.tag === 'button' && text(n).trim() === 'Mois dernier')
      .props.onClick()
    await flush()
    query = new URLSearchParams(f.requests.at(-1).split('?')[1])
    assert.equal(query.get('from'), '2026-09-01')
    assert.equal(query.get('to'), '2026-09-30')
  } finally {
    f.close()
    globalThis.Date = RealDate
  }
})
