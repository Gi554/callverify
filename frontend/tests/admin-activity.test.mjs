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
const url = (code) =>
  'data:text/javascript;base64,' +
  Buffer.from(
    ts.transpileModule(code, {
      compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
    }).outputText,
  ).toString('base64')
let code = compileScript(
  parse(readFileSync(new URL('../src/CrmAdminActivity.vue', import.meta.url), 'utf8')).descriptor,
  {
    id: 'activity',
    inlineTemplate: true,
    templateOptions: { compilerOptions: { hoistStatic: false } },
  },
).content
code = code
  .replace(/from ['"]vue['"]/g, `from '${vue}'`)
  .replace(/import \{([^}]+)\} from 'lucide-vue-next'/g, (_, names) =>
    names
      .split(',')
      .filter((n) => n.trim())
      .map((n) => `const ${n.trim()}={render:()=>null}`)
      .join(';'),
  )
code =
  withStatComponents(code)
    .replace(/vModelText as _vModelText,?/g, '')
    .replace(/vModelSelect as _vModelSelect,?/g, '') + ';const _vModelText={},_vModelSelect={};'
const component = (await import(url(code))).default
let tick,
  cleared = false
const realSetInterval = globalThis.setInterval,
  realClearInterval = globalThis.clearInterval
globalThis.setInterval = (fn, ms) => {
  assert.equal(ms, 60000)
  tick = fn
  return 91
}
globalThis.clearInterval = (id) => {
  assert.equal(id, 91)
  cleared = true
}
globalThis.document = { hidden: false }
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

function fixture(workspace = 'isolation', request) {
  const root = { children: [] },
    calls = []
  const app = renderer.createApp(component, {
    workspace,
    request: async (path) => {
      calls.push(path)
      return request
        ? request(path)
        : {
            as_of: '2026-11-02T15:00:00Z',
            totals: {
              scheduled: 20,
              performed: 15,
              closed: 5,
              not_closed: 8,
              not_performed: 3,
              updates_due: 2,
            },
            pending_callbacks: 4,
            filter_options: {
              setter_id: [{ id: 21, name: 'Alice' }],
              client_id: [{ id: 72, name: 'Client' }],
              advisor_id: [{ id: 31, name: 'Conseiller' }],
              closer_id: [{ id: 41, name: 'Closer' }],
              campaign_id: [{ id: 9, name: 'Campagne' }],
            },
          }
    },
  })
  app.mount(root)
  return { root, app, calls }
}
test('admin activity uses its workspace endpoint and sends all selected filters immediately', async () => {
  for (const workspace of ['isolation', 'assurance']) {
    const f = fixture(workspace)
    try {
      await flush()
      assert.ok(
        f.calls[0].startsWith(workspace === 'isolation' ? 'workspace-statistics/' : 'statistics/'),
      )
      assert.match(text(f.root), /20/)
      assert.match(text(f.root), /Rappels en attente/)
      const selects = all(f.root).filter((n) => n.tag === 'select')
      selects[0].props['onUpdate:modelValue']('21')
      await flush()
      selects[1].props['onUpdate:modelValue'](workspace === 'isolation' ? '72' : '31')
      await flush()
      selects.at(-1).props['onUpdate:modelValue']('9')
      await flush()
      const query = new URLSearchParams(f.calls.at(-1).split('?')[1])
      assert.equal(query.get('setter_id'), '21')
      assert.equal(
        query.get(workspace === 'isolation' ? 'client_id' : 'advisor_id'),
        workspace === 'isolation' ? '72' : '31',
      )
      assert.equal(query.get('campaign_id'), '9')
    } finally {
      f.app.unmount()
    }
  }
})
test('default period covers the whole current Québec month, upcoming appointments included', async () => {
  const f = fixture()
  try {
    await flush()
    const query = new URLSearchParams(f.calls[0].split('?')[1])
    const today = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'America/Toronto',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(new Date())
    const [year, month] = today.split('-').map(Number)
    const last = new Date(Date.UTC(year, month, 0)).getUTCDate()
    assert.equal(query.get('from'), today.slice(0, 8) + '01')
    assert.equal(query.get('to'), today.slice(0, 8) + String(last).padStart(2, '0'))
    assert.ok(query.get('to') >= today)
  } finally {
    f.app.unmount()
  }
})
test('auto refresh pauses in hidden tabs and its timer is cleared on unmount', async () => {
  const f = fixture()
  try {
    await flush()
    const n = f.calls.length
    document.hidden = true
    tick()
    await flush()
    assert.equal(f.calls.length, n)
    document.hidden = false
    tick()
    await flush()
    assert.equal(f.calls.length, n + 1)
  } finally {
    f.app.unmount()
    assert.equal(cleared, true)
  }
})
test('unavailable activity exposes an error without fabricating zero metrics', async () => {
  const f = fixture('isolation', async () => {
    throw new Error('Serveur indisponible')
  })
  try {
    await flush()
    assert.match(text(f.root), /Serveur indisponible/)
    assert.match(text(f.root), /—/)
    assert.doesNotMatch(text(f.root), /Mis à jour à/)
  } finally {
    f.app.unmount()
  }
})
process.on('exit', () => {
  globalThis.setInterval = realSetInterval
  globalThis.clearInterval = realClearInterval
})
