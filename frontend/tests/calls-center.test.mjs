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
  parse(readFileSync(new URL('../src/CallsCenter.vue', import.meta.url), 'utf8')).descriptor,
  {
    id: 'calls-center',
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
globalThis.Document = class {}
globalThis.ShadowRoot = class {}
const renderer = createRenderer({
  // Real v-model directives listen to DOM events and read select options.
  createElement: (tag) => ({
    tag,
    children: [],
    props: {},
    style: {},
    listeners: {},
    addEventListener(name, fn) {
      ;(this.listeners[name] ||= []).push(fn)
    },
    removeEventListener() {},
    getRootNode: () => null,
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
    if (k === 'value') n.value = v
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
const text = (n) => (n.text || '') + (n.children || []).map(text).join('')
async function flush() {
  for (let i = 0; i < 6; i++) {
    await nextTick()
    await new Promise((resolve) => setImmediate(resolve))
  }
}
const call = (id, label, state, username = 'setter.demo01') => ({
  request_id: `req-${id}`,
  created_at: '2026-10-23T09:30:00Z',
  updated_at: '2026-10-23T09:30:05Z',
  state,
  contact_id: id,
  contact_label: label,
  caller: { id: 9, username },
  extension: '501',
})
function fixture({ role = 'setter', workspace = 'assurance', options, contacts = [], calls = [] }) {
  const root = { children: [] },
    requests = [],
    portals = [],
    opened = []
  const app = renderer.createApp(component, {
    workspace,
    role,
    request: async (path) => {
      requests.push(path)
      return { results: contacts }
    },
    portal: async (path) => {
      portals.push(path)
      if (path.endsWith('/calls/options/')) return options
      if (path.endsWith('/call-history/reconcile/'))
        return { checked: 3, matched: 1, ambiguous: 1, not_found: 1 }
      if (path.includes('/call-history/')) return { count: calls.length, results: calls }
      return { results: [{ id: 9, name: 'setter.demo01' }] }
    },
    onOpenProspect: (value) => opened.push(value),
  })
  app.mount(root)
  return { root, requests, portals, opened, close: () => app.unmount() }
}
const button = (f, match) =>
  all(f.root).find((n) => n.tag === 'button' && match.test(text(n).trim()))

test('the dialer finds the prospect card and launches the call from it', async () => {
  const f = fixture({
    options: { enabled: false, post_associated: true },
    contacts: [
      { id: 4, name: 'Dossier Alpha', phone: '+15145550101' },
      { id: 5, name: 'Dossier Beta', phone: '' },
    ],
  })
  try {
    await flush()
    assert.match(text(f.root), /appels réels ne sont pas encore activés/)
    for (const key of ['5', '1', '4']) button(f, new RegExp(`^${key}$`)).props.onClick()
    await flush()
    const input = all(f.root).find((n) => n.tag === 'input')
    assert.equal(input.value, '514')
    button(f, /Trouver la fiche/).props.onClick()
    await flush()
    assert.deepEqual(f.requests, ['contacts/?search=514'])
    const calls = all(f.root).filter((n) => n.tag === 'button' && /Appeler/.test(text(n)))
    assert.equal(calls.length, 2)
    assert.equal(calls[1].props.disabled, true)
    calls[0].props.onClick()
    assert.deepEqual(f.opened, [{ id: 4, mode: 'call' }])
  } finally {
    f.close()
  }
})

test('an unknown number points to the import and Isolation searches the work queue', async () => {
  const f = fixture({ workspace: 'isolation', options: { enabled: true, post_associated: true } })
  try {
    await flush()
    assert.doesNotMatch(text(f.root), /pas encore activés/)
    button(f, /^0$/).props.onClick()
    await flush()
    button(f, /Trouver la fiche/).props.onClick()
    await flush()
    assert.deepEqual(f.requests, ['work-queue/?search=0'])
    assert.match(text(f.root), /Aucune fiche ne correspond/)
    assert.match(text(f.root), /par import/)
  } finally {
    f.close()
  }
})

test('a setter reads only their own history, without caller details', async () => {
  const f = fixture({
    options: { enabled: true, post_associated: false },
    calls: [call(4, 'Dossier Alpha', 'accepted')],
  })
  try {
    await flush()
    assert.match(text(f.root), /Aucun poste téléphonique/)
    button(f, /Mon historique/).props.onClick()
    await flush()
    assert.ok(f.portals.includes('assurance/call-history/?page=1'))
    assert.match(text(f.root), /Mes appels/)
    assert.match(text(f.root), /Dossier Alpha/)
    assert.match(text(f.root), /Poste joint/)
    assert.doesNotMatch(text(f.root), /Appelant/)
    button(f, /Ouvrir la fiche/).props.onClick()
    assert.deepEqual(f.opened, [{ id: 4, mode: 'edit' }])
  } finally {
    f.close()
  }
})

test('an administrator sees the team history with callers and filters', async () => {
  const f = fixture({
    role: 'administrator',
    workspace: 'isolation',
    calls: [call(7, '', 'rejected', 'setter.demo02')],
  })
  try {
    await flush()
    assert.ok(f.portals.some((path) => path.endsWith('/calls/options/')))
    assert.ok(f.portals.includes('isolation/setters/?page=1'))
    assert.ok(button(f, /Composer/))
    assert.match(text(f.root), /Appels de l’équipe/)
    assert.match(text(f.root), /Fiche n° 7/)
    assert.match(text(f.root), /setter\.demo02 · poste 501/)
    assert.match(text(f.root), /Échec du poste/)
    const selects = all(f.root).filter((n) => n.tag === 'select')
    for (const option of selects[1].options) option.selected = option.value === '9'
    for (const fn of selects[1].listeners.change) fn()
    selects[1].props.onChange()
    await flush()
    assert.equal(f.portals.at(-1), 'isolation/call-history/?page=1&user_id=9')
  } finally {
    f.close()
  }
})

test('the history shows the NEWT duration and administrators reconcile the journal', async () => {
  const f = fixture({
    role: 'administrator',
    calls: [
      { ...call(1, 'Dossier Alpha', 'accepted'), journal_status: 'matched', journal_duration: 125 },
      { ...call(2, 'Dossier Beta', 'accepted'), journal_status: 'matched', journal_duration: 4 },
      { ...call(3, 'Dossier Gamma', 'unknown'), journal_status: 'pending' },
      { ...call(4, 'Dossier Delta', 'rejected'), journal_status: 'pending' },
      { ...call(5, 'Dossier Epsilon', 'accepted'), journal_status: 'ambiguous' },
    ],
  })
  try {
    await flush()
    const cells = all(f.root)
      .filter((n) => n.tag === 'td' && n.props['data-label'] === 'Durée')
      .map((n) => text(n).trim())
    assert.deepEqual(cells, ['2 min 05 s', '4 s', 'En attente du journal', '—', 'À vérifier'])
    button(f, /Rapprocher le journal NEWT/).props.onClick()
    await flush()
    assert.ok(f.portals.includes('assurance/call-history/reconcile/'))
    const status = all(f.root).find((n) => n.props?.class === 'calls-reconciled')
    assert.equal(
      text(status),
      '1 durée(s) récupérée(s) sur 3 appel(s) vérifié(s), 1 à vérifier, 1 absent(s) du journal.',
    )
    assert.equal(f.portals.at(-1), 'assurance/call-history/?page=1')
  } finally {
    f.close()
  }
})

test('setters read durations without the reconciliation button', async () => {
  const f = fixture({ options: { enabled: true, post_associated: true } })
  try {
    await flush()
    button(f, /Mon historique/).props.onClick()
    await flush()
    assert.equal(button(f, /Rapprocher/), undefined)
  } finally {
    f.close()
  }
})

test('administrator opens the composer and prepares a call without posting a command', async () => {
  const f = fixture({
    role: 'administrator',
    options: { enabled: true, post_associated: true },
    contacts: [{ id: 4, name: 'Synthetic', phone: '+15145550101' }],
  })
  try {
    await flush()
    button(f, /^Composer$/).props.onClick()
    await flush()
    button(f, /^5$/).props.onClick()
    await flush()
    button(f, /Trouver la fiche/).props.onClick()
    await flush()
    button(f, /Appeler/).props.onClick()
    assert.deepEqual(f.opened, [{ id: 4, mode: 'call' }])
    assert.ok(f.portals.every((path) => !path.endsWith('/calls/')))
  } finally {
    f.close()
  }
})
