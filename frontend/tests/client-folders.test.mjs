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
  parse(readFileSync(new URL('../src/ClientFolders.vue', import.meta.url), 'utf8')).descriptor,
  {
    id: 'client-folders',
    inlineTemplate: true,
    templateOptions: { compilerOptions: { hoistStatic: false } },
  },
).content
code = code
  .replace(/import (\w+) from ['"]\.\/[^'"]+\.vue['"]/g, (_, name) =>
    name === 'ProspectExport'
      ? `const ProspectExport={props:['filters','path','filename','blocked'],setup:props=>{globalThis.__folderExportProps=props;return()=>null}}`
      : name === 'SidePanel'
        ? `const SidePanel={inheritAttrs:false,emits:['requestClose'],props:['open','title','closeDisabled'],setup:(props,ctx)=>()=>{if(props.open){globalThis.__folderPanel={props,close:()=>ctx.emit('requestClose')};return ctx.slots.default?.()}return null}}`
        : ['AssuranceAppointments', 'IsolationVisits'].includes(name)
          ? `const ${name}={props:['appointmentId','visitId','role'],setup:(props,ctx)=>{globalThis.__folderAppointment={props,busy:v=>ctx.emit('busy',v),updated:()=>ctx.emit('updated')};return()=>null}}`
          : `const ${name}={render:()=>null}`,
  )
  .replace(
    /import \{ actorNames \} from ['"]\.\/actor-names['"]/g,
    `const actorNames=async()=>({21:'Synthetic Setter'})`,
  )
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
    scrollIntoView() {
      this.scrolled = true
    },
    focus() {
      this.focused = true
    },
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

const summary = {
  prospects: 20,
  appointments: 20,
  statuses: { performed: 15, absent: 5 },
  sales: 5,
  call_results: 28,
  tasks: 3,
  open_tasks: 2,
  overdue_tasks: 1,
  prospect_statuses: [{ status: 'to_contact', label: 'À contacter', total: 20 }],
}
function mount({ workspace = 'assurance', fail = false, catalogCount = 1 } = {}) {
  const calls = []
  const root = { children: [] }
  const app = renderer.createApp(component, {
    workspace,
    portal: async (path) => {
      calls.push(['portal', path])
      return {
        count: catalogCount,
        results: [{ id: 31, name: 'Synthetic Client', active: true, quota: 20 }],
      }
    },
    request: async (path) => {
      calls.push(['business', path])
      if (fail) throw Error('Statistics unavailable')
      if (path.startsWith('client-folders/?')) return { results: [{ id: 31, ...summary }] }
      if (path.includes('section=appointments'))
        return {
          count: 1,
          summary,
          results: [
            {
              id: 900,
              contact_id: 5,
              name: 'Past cancelled prospect',
              status: 'cancelled',
              starts_at: '2026-01-01T10:00:00Z',
              timezone: 'UTC',
              setter_id: 21,
              booked_by_id: 99,
            },
          ],
        }
      return {
        count: 26,
        summary,
        results: [{ id: 5, name: 'Synthetic Prospect', phone: 'raw', status: 'to_contact' }],
      }
    },
  })
  app.mount(root)
  return { root, calls, app }
}
const button = (root, label) => all(root).find((n) => n.tag === 'button' && text(n).includes(label))
test('admin opens client folder, sees confirmed presence countdown and pages the full portfolio', async () => {
  const { root, calls, app } = mount()
  await flush()
  assert.ok(text(root).includes('Synthetic Client'))
  button(root, 'Synthetic Client').props.onClick()
  await flush()
  assert.ok(text(root).includes('Présences seules décomptées'))
  const metric = all(root).find((n) => n.props?.class === 'metric-peach')
  assert.ok(text(metric).includes('5'))
  assert.ok(text(root).includes('Absent'))
  assert.ok(calls.some(([, path]) => path.includes('client-folders/31/?page=1')))
  button(root, 'Suivant').props.onClick()
  await flush()
  assert.ok(calls.some(([, path]) => path.includes('page=2')))
  assert.ok(calls.every(([, path]) => !path.includes('/calls/')))
  app.unmount()
})

test('returning from a dossier preserves the searched catalog page and distinguishes status filters', async () => {
  const { root, calls, app } = mount({ catalogCount: 30 })
  try {
    await flush()
    all(root)
      .find((n) => n.tag === 'input')
      .props['onUpdate:modelValue']('Synthetic')
    all(root)
      .find((n) => n.tag === 'form')
      .props.onSubmit({ preventDefault() {} })
    await flush()
    button(root, 'Suivant').props.onClick()
    await flush()
    button(root, 'Synthetic Client').props.onClick()
    await flush()
    const heading = all(root).find((n) => n.tag === 'h1')
    assert.equal(heading.scrolled, true)
    assert.equal(heading.focused, true)
    assert.ok(text(root).includes('Résultats des rendez-vous'))
    assert.ok(text(root).includes('Étapes commerciales des prospects'))
    const stage = button(root, 'À contacter')
    stage.props.onClick()
    await flush()
    assert.equal(button(root, 'À contacter').props['aria-pressed'], true)
    button(root, 'Tous les dossiers').props.onClick()
    await flush()
    assert.ok(
      calls.some(([type, path]) => type === 'portal' && path.includes('page=2&search=Synthetic')),
    )
    assert.equal(all(root).find((n) => n.tag === 'input').value, 'Synthetic')
  } finally {
    app.unmount()
  }
})
test('unavailable business data keeps folder access and does not fabricate zero statistics', async () => {
  const { root, app } = mount({ fail: true })
  await flush()
  assert.ok(text(root).includes('Statistics unavailable'))
  assert.ok(text(root).includes('Statistiques indisponibles'))
  assert.ok(button(root, 'Synthetic Client'))
  app.unmount()
})
test('isolation directory uses its own catalog and never creates extra clients', async () => {
  const { root, calls, app } = mount({ workspace: 'isolation' })
  await flush()
  assert.ok(text(root).includes('Client unique · Isolation'))
  assert.ok(calls.some(([, path]) => path.startsWith('isolation/client-folders/')))
  app.unmount()
})

test('export uses the last applied list filters and a separate unfiltered summary', async () => {
  const { root, app } = mount()
  try {
    await flush()
    button(root, 'Synthetic Client').props.onClick()
    await flush()
    assert.equal(globalThis.__folderExportProps.path, 'client-folders/31/export/')
    const input = all(root).find(
      (n) =>
        n.tag === 'input' && n.props['aria-label'] === 'Rechercher un prospect dans le dossier',
    )
    input.props['onUpdate:modelValue']('Draft search')
    await flush()
    assert.equal(globalThis.__folderExportProps.filters.search, '')
    all(root)
      .find((n) => n.tag === 'form')
      .props.onSubmit({ preventDefault() {} })
    await flush()
    assert.equal(globalThis.__folderExportProps.filters.search, 'Draft search')
    const select = all(root).find((n) => n.tag === 'select')
    select.props['onUpdate:modelValue']('summary')
    await flush()
    assert.deepEqual({ ...globalThis.__folderExportProps.filters }, { section: 'summary' })
    assert.match(globalThis.__folderExportProps.filename, /-summary$/)
  } finally {
    app.unmount()
  }
})
for (const workspace of ['assurance', 'isolation']) {
  test(`${workspace}: dossier opens the exact past cancelled appointment and protects pending edits`, async () => {
    const { root, calls, app } = mount({ workspace })
    globalThis.window = { confirm: () => false }
    try {
      await flush()
      button(root, 'Synthetic Client').props.onClick()
      await flush()
      button(root, 'Rendez-vous').props.onClick()
      await flush()
      button(root, 'Voir le rendez-vous').props.onClick()
      await flush()
      const detail = globalThis.__folderAppointment
      assert.equal(detail.props[workspace === 'assurance' ? 'appointmentId' : 'visitId'], 900)
      assert.equal(detail.props.role, 'administrator')
      assert.equal(
        calls.some(([, path]) => path.includes('contacts/5/')),
        false,
      )
      detail.busy(true)
      await flush()
      const panel = globalThis.__folderPanel
      assert.equal(panel.props.closeDisabled, true)
      panel.close()
      await flush()
      assert.equal(panel.props.open, true)
      detail.busy(false)
      await flush()
      all(root)
        .find((n) => n.tag === 'div' && n.props.onInput)
        .props.onInput()
      panel.close()
      await flush()
      assert.equal(panel.props.open, true)
      globalThis.window.confirm = () => true
      panel.close()
      await flush()
      assert.equal(panel.props.open, false)
    } finally {
      app.unmount()
      delete globalThis.window
    }
  })
}
