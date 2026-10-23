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
  parse(readFileSync(new URL('../src/AssuranceAdvisorAgenda.vue', import.meta.url), 'utf8'))
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
  .replace("'./advisor-quota'", JSON.stringify(url(source('advisor-quota'))))
  .replace(
    /import (\w+) from ['"]\.\/[^'"]+\.vue['"]/g,
    (_, name) =>
      `const ${name}={props:['open','title','role'],setup(p,{slots}){return()=>(${JSON.stringify(name)}==='SidePanel'&&!p.open)?null:stubH('div',{'data-component':${JSON.stringify(name)}},slots.default?.())}}`,
  )
code =
  `import {h as stubH} from '${vue}';` +
  code.replace(/vModelText as _vModelText,?/g, '').replace(/vModelSelect as _vModelSelect,?/g, '') +
  ';const _vModelText={},_vModelSelect={};'
code = code.replace(/vModelCheckbox as _vModelCheckbox,?/g, '') + ';const _vModelCheckbox={};'
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

function fixture(reject = false) {
  const root = { children: [] },
    calls = []
  const app = renderer.createApp(component, {
    portal: async () => ({}),
    request: async (path, body) => {
      if (body) {
        calls.push(JSON.parse(JSON.stringify(body)))
        if (reject) throw new Error('Disponibilités modifiées')
        return { ...body, revision: 1 }
      }
      return { revision: 0, enabled: false, timezone: 'America/Toronto', windows: [] }
    },
  })
  app.mount(root)
  return { root, calls, close: () => app.unmount() }
}
const button = (f, label) => all(f.root).find((n) => n.tag === 'button' && text(n).trim() === label)
async function edit(f) {
  await flush()
  button(f, 'Définir mes horaires').props.onClick()
  await flush()
  all(f.root)
    .find((n) => n.tag === 'input' && n.props.type === 'checkbox')
    .props['onUpdate:modelValue'](true)
  all(f.root)
    .find((n) => n.props?.['aria-label'] === 'Ajouter une plage pour Lundi')
    .props.onClick()
  await flush()
}
test('advisor configures weekly hours and saves the chosen timezone and revision', async () => {
  const f = fixture()
  try {
    await edit(f)
    await all(f.root)
      .find((n) => n.tag === 'form')
      .props.onSubmit({ preventDefault() {} })
    await flush()
    assert.deepEqual(f.calls[0], {
      revision: 0,
      enabled: true,
      timezone: 'America/Toronto',
      windows: [{ weekday: 0, start: '09:00', end: '17:00' }],
    })
    assert.match(text(f.root), /Vos disponibilités sont enregistrées/)
    assert.match(text(f.root), /09:00 – 17:00/)
    assert.ok(button(f, 'Connexion Google / Microsoft'))
  } finally {
    f.close()
  }
})
test('a stale weekly schedule keeps the draft open for correction', async () => {
  const f = fixture(true)
  try {
    await edit(f)
    await all(f.root)
      .find((n) => n.tag === 'form')
      .props.onSubmit({ preventDefault() {} })
    await flush()
    assert.match(text(f.root), /Disponibilités modifiées/)
    assert.ok(button(f, 'Enregistrer mes disponibilités'))
    assert.ok(button(f, 'Recharger les horaires'))
  } finally {
    f.close()
  }
})
let connectionCode = compileScript(
  parse(readFileSync(new URL('../src/PortalCalendars.vue', import.meta.url), 'utf8')).descriptor,
  {
    id: 'calendar-connection',
    inlineTemplate: true,
    templateOptions: { compilerOptions: { hoistStatic: false } },
  },
).content
connectionCode = connectionCode
  .replace(/from ['"]vue['"]/g, `from '${vue}'`)
  .replace("'./booking-time'", JSON.stringify(booking))
for (const directive of ['vModelText', 'vModelSelect', 'vModelDynamic', 'vModelCheckbox'])
  connectionCode =
    connectionCode.replace(new RegExp(directive + ' as _' + directive + ',?', 'g'), '') +
    `;const _${directive}={};`
const connectionComponent = (await import(url(connectionCode))).default

test('calendar connection shows missing OAuth configuration and uses local dates with explicit timezone', async () => {
  const root = { children: [] },
    calls = []
  const app = renderer.createApp(connectionComponent, {
    workspace: 'assurance',
    simple: true,
    request: async (path, body) => {
      calls.push({ path, body })
      if (path === 'calendar/')
        return {
          connections: [
            {
              workspace: 'assurance',
              connected: true,
              revision: 1,
              configured: { google: false, microsoft: false },
            },
          ],
        }
      return { busy: [], counts: {}, results: [], next: null }
    },
  })
  app.mount(root)
  try {
    await flush()
    const google = all(root).find((n) => n.tag === 'button' && text(n).includes('Connecter Google'))
    assert.equal(google.props.disabled, true)
    const dates = all(root).filter((n) => n.tag === 'input' && n.props.type === 'datetime-local')
    assert.equal(dates.length, 2)
    dates[0].props['onUpdate:modelValue']('2026-11-02T09:00')
    dates[1].props['onUpdate:modelValue']('2026-11-02T10:00')
    await flush()
    await all(root)
      .find((n) => n.tag === 'form')
      .props.onSubmit({ preventDefault() {} })
    await flush()
    const sent = calls.find((row) => row.path.endsWith('/busy/')).body
    assert.equal(sent.starts_at, '2026-11-02T09:00:00-05:00')
    assert.equal(sent.ends_at, '2026-11-02T10:00:00-05:00')
  } finally {
    app.unmount()
  }
})
