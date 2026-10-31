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

const link = url(source('appointment-link'))
let code = compileScript(
  parse(readFileSync(new URL('../src/Portal.vue', import.meta.url), 'utf8')).descriptor,
  {
    id: 'portal-reminder-link',
    inlineTemplate: true,
    templateOptions: { compilerOptions: { hoistStatic: false } },
  },
).content
code = code
  .replace(/from ['"]vue['"]/g, `from '${vue}'`)
  .replace("'./appointment-link'", JSON.stringify(link))
  .replace(/import \{([^}]+)\} from 'lucide-vue-next'/g, 'const RefreshCw={render:()=>null}')
  .replace(
    /import (\w+) from ['"]\.\/[^'"]+\.vue['"]/g,
    (_, name) =>
      `const ${name}={inheritAttrs:false,setup(p,{slots,attrs}){return()=>stubH('div',{...attrs,'data-component':${JSON.stringify(name)}},slots.default?.())}}`,
  )
code = `import {h as stubH} from '${vue}';` + code
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
async function flush() {
  for (let i = 0; i < 5; i++) {
    await nextTick()
    await new Promise((resolve) => setImmediate(resolve))
  }
}

async function fixture({
  loggedIn,
  role = 'advisor',
  isolationRole = 'closer',
  isolationLink = false,
}) {
  const saved = new Map(
    ['location', 'history', 'localStorage', 'window', 'fetch'].map((key) => [key, globalThis[key]]),
  )
  const address = new URL(
    isolationLink
      ? 'https://orvia-crm.com/crm?workspace=isolation&visit=42'
      : 'https://orvia-crm.com/crm?workspace=assurance&appointment=42',
  )
  const member = {
    username: 'advisor',
    workspaces: [
      { workspace: 'isolation', role: isolationRole },
      { workspace: 'assurance', role },
    ],
    admin_workspaces: [],
    landing: 'isolation',
  }
  let session = loggedIn
  globalThis.location = address
  globalThis.history = {
    replaceState(_a, _b, path) {
      address.href = new URL(path, address).href
    },
  }
  globalThis.localStorage = { getItem: () => 'isolation', setItem() {} }
  globalThis.window = { scrollTo() {} }
  globalThis.fetch = async (path) => {
    let data = {}
    let status = 200
    if (path === '/api/portal/session/') {
      data = session ? member : { detail: 'Connexion requise' }
      status = session ? 200 : 401
    } else if (path === '/api/portal/login/') {
      session = true
      data = member
    } else if (path === '/api/portal/csrf/') data = { csrfToken: 'test' }
    else if (path.startsWith('/api/portal/access/')) data = { token: 'test' }
    return { ok: status === 200, status, headers: { get: () => null }, json: async () => data }
  }
  const root = { children: [] }
  const app = renderer.createApp(component)
  app.mount(root)
  await flush()
  return {
    root,
    address,
    close() {
      app.unmount()
      for (const [k, v] of saved) {
        if (v === undefined) delete globalThis[k]
        else globalThis[k] = v
      }
    },
  }
}
const find = (f, name) => all(f.root).find((n) => n.props?.['data-component'] === name)

test('authenticated adviser reminder overrides the remembered workspace and opens the appointment', async () => {
  const f = await fixture({ loggedIn: true })
  try {
    const calendar = find(f, 'CrmAppointmentsCalendar')
    assert.deepEqual(
      find(f, 'CrmShell').props.items.map((item) => item.id),
      ['appointments', 'contacts'],
    )
    assert.equal(calendar.props.workspace, 'assurance')
    assert.equal(calendar.props['appointment-id'], 42)
    assert.equal(f.address.search, '')
  } finally {
    f.close()
  }
})

test('login preserves the appointment intention for an adviser with several workspaces', async () => {
  const f = await fixture({ loggedIn: false })
  try {
    const login = find(f, 'PortalLogin')
    assert.ok(login)
    assert.equal(f.address.searchParams.get('appointment'), '42')
    await login.props.onSubmit({ username: 'advisor', password: 'local-test' })
    await flush()
    const calendar = find(f, 'CrmAppointmentsCalendar')
    assert.equal(calendar.props.workspace, 'assurance')
    assert.equal(calendar.props['appointment-id'], 42)
  } finally {
    f.close()
  }
})

test('an adviser link grants no appointment focus to a setter', async () => {
  const f = await fixture({ loggedIn: true, role: 'setter' })
  try {
    assert.equal(find(f, 'CrmAppointmentsCalendar'), undefined)
  } finally {
    f.close()
  }
})

test('Isolation client reminder opens the exact authorised visit after login', async () => {
  for (const loggedIn of [true, false]) {
    const f = await fixture({ loggedIn, isolationRole: 'client', isolationLink: true })
    try {
      if (!loggedIn) {
        await find(f, 'PortalLogin').props.onSubmit({ username: 'client', password: 'test' })
        await flush()
      }
      const visits = find(f, 'IsolationVisits')
      assert.deepEqual(
        find(f, 'CrmShell').props.items.map((item) => item.id),
        ['overview', 'appointments', 'unqualified', 'visit-history', 'isolation-agenda'],
      )
      assert.equal(visits.props['visit-id'], 42)
      assert.equal(f.address.search, '')
    } finally {
      f.close()
    }
  }
})

test('Isolation visit hint does not grant a setter access to a client result panel', async () => {
  const f = await fixture({ loggedIn: true, isolationRole: 'setter', isolationLink: true })
  try {
    assert.equal(find(f, 'IsolationVisits'), undefined)
  } finally {
    f.close()
  }
})
