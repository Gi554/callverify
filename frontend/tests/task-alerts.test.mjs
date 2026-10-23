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
let code = compileScript(
  parse(readFileSync(new URL('../src/TaskAlerts.vue', import.meta.url), 'utf8')).descriptor,
  {
    id: 'task-alerts',
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
  for (let i = 0; i < 6; i++) {
    await nextTick()
    await new Promise((resolve) => setImmediate(resolve))
  }
}
const notification = (id, name) => ({
  id,
  label: 'Compte rendu nécessitant un suivi',
  contact_name: name,
  priority: 'normal',
  due_at: '2026-10-24T14:00:00Z',
})
// Browser globals used by the component, recreated for every fixture.
function environment({ permission = 'default', hidden = false } = {}) {
  const store = new Map(),
    shown = [],
    ticks = []
  globalThis.sessionStorage = {
    getItem: (key) => (store.has(key) ? store.get(key) : null),
    setItem: (key, value) => store.set(key, String(value)),
  }
  globalThis.document = { hidden }
  globalThis.window = { addEventListener() {}, removeEventListener() {} }
  globalThis.Notification = class {
    static permission = permission
    static requestPermission = async () => 'granted'
    constructor(title, options) {
      shown.push([title, options.body])
    }
  }
  globalThis.setInterval = (fn) => {
    ticks.push(fn)
    return ticks.length
  }
  globalThis.clearInterval = () => {}
  return { store, shown, tick: async () => (ticks.at(-1)(), await flush()) }
}
function fixture(state, options) {
  const env = environment(options)
  const root = { children: [] },
    requests = [],
    navigations = []
  const app = renderer.createApp(component, {
    role: 'setter',
    username: 'setter.demo01',
    request: async (path, body) => {
      requests.push([path, body])
      if (path === 'notifications/summary/') return { unread_open: state.unread.length }
      if (path === 'follow-ups/summary/') return { overdue: state.overdue }
      if (path.startsWith('notifications/?')) return { results: state.unread }
      return {}
    },
    onNavigate: (value) => navigations.push(value),
  })
  app.mount(root)
  return { ...env, root, requests, navigations, close: () => app.unmount() }
}
const button = (f, match) =>
  all(f.root).find((n) => n.tag === 'button' && match.test(text(n).trim()))

test('the bell shows unread count and lists tasks with the prospect name', async () => {
  const state = { unread: [notification(1, 'Dossier Alpha')], overdue: 0 }
  const f = fixture(state)
  try {
    await flush()
    const bell = all(f.root).find((n) => String(n.props?.class).includes('alerts-bell'))
    assert.equal(bell.props['aria-label'], '1 notification(s) non lue(s)')
    assert.match(text(bell), /1/)
    bell.props.onClick()
    await flush()
    assert.match(text(f.root), /Dossier Alpha/)
    assert.match(text(f.root), /Activer les notifications du navigateur/)
    button(f, /Dossier Alpha/).props.onClick()
    await flush()
    assert.ok(f.requests.some(([path, body]) => path === 'notifications/1/read/' && body))
    assert.deepEqual(f.navigations, ['followups'])
  } finally {
    f.close()
  }
})

test('a new task raises a banner and a browser notification when the tab is hidden', async () => {
  const state = { unread: [notification(1, 'Dossier Alpha')], overdue: 0 }
  const f = fixture(state, { permission: 'granted', hidden: true })
  try {
    await flush()
    assert.doesNotMatch(text(f.root), /Nouvelle tâche/)
    state.unread = [notification(2, 'Dossier Beta'), ...state.unread]
    await f.tick()
    assert.match(text(f.root), /Nouvelle tâche · Compte rendu nécessitant un suivi/)
    assert.match(text(f.root), /Dossier Beta/)
    assert.doesNotMatch(text(f.root), /Nouvelle tâche[^·]*· [^·]*Dossier Alpha/)
    assert.deepEqual(f.shown, [['AMX · Compte rendu nécessitant un suivi', 'Dossier Beta']])
    await f.tick()
    assert.equal(f.shown.length, 1)
  } finally {
    f.close()
  }
})

test('overdue tasks prompt once per session and lead to the task board', async () => {
  const state = { unread: [], overdue: 3 }
  const f = fixture(state)
  try {
    await flush()
    assert.match(text(f.root), /3 tâche\(s\)\s+en retard/)
    assert.equal(f.store.get('amx-overdue-prompt:setter.demo01'), '1')
    button(f, /Traiter maintenant/).props.onClick()
    await flush()
    assert.deepEqual(f.navigations, ['followups'])
    assert.equal(button(f, /Traiter maintenant/), undefined)
    await f.tick()
    assert.equal(button(f, /Traiter maintenant/), undefined)
  } finally {
    f.close()
  }
})
