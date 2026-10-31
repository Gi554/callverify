import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import test from 'node:test'
import assert from 'node:assert/strict'
import { parse, compileScript } from 'vue/compiler-sfc'
import { createRenderer, nextTick } from 'vue'
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
  parse(readFileSync(new URL('../src/IsolationProspectActivity.vue', import.meta.url), 'utf8'))
    .descriptor,
  {
    id: 'qualification',
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
  .replace(
    "'./booking-time'",
    JSON.stringify(url(readFileSync(new URL('../src/booking-time.ts', import.meta.url), 'utf8'))),
  )
code = code.replace(
  /import (\w+) from ['"]\.\/[^'"]+\.vue['"]/g,
  (_, name) =>
    `const ${name}={setup(p,{attrs}){return()=>stubH('div',{'data-component':${JSON.stringify(name)},...attrs})}}`,
)
code = code.replace(
  /import \{ actorNames \} from ['"]\.\/actor-names['"];?/,
  'const actorNames=async()=>({});',
)
code = "import {h as stubH} from '" + pathToFileURL(require.resolve('vue')).href + "';" + code
code =
  code
    .replace(/vModelText as _vModelText,?/g, '')
    .replace(/vModelSelect as _vModelSelect,?/g, '')
    .replace(/vModelDynamic as _vModelDynamic,?/g, '') +
  ';const model={created(el,b){el.model=b.value},beforeUpdate(el,b){el.model=b.value}};const _vModelText=model,_vModelSelect=model,_vModelDynamic=model;'
const component = (await import(url(code))).default
globalThis.document = { activeElement: null }
globalThis.window = {
  addEventListener() {},
  removeEventListener() {},
  confirm() {
    return false
  },
}
const renderer = createRenderer({
  createElement: (tag) => ({
    tag,
    tagName: tag.toUpperCase(),
    style: {},
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
function fixture({ failReload = false } = {}) {
  const root = { children: [] },
    closed = [],
    saved = [],
    requests = []
  let loads = 0
  const app = renderer.createApp(component, {
    prospectId: 7,
    role: 'setter',
    portal: async () => ({}),
    request: async (path) => {
      requests.push(path)
      if (path === 'work-queue/7/') {
        loads++
        if (failReload && loads > 1) throw new Error('Fiche indisponible')
        return { id: 7, revision: loads - 1 }
      }
      return { results: [], count: 0 }
    },
    onClose: () => closed.push(true),
    onSaved: () => saved.push(true),
  })
  app.mount(root)
  return { root, app, closed, saved, requests }
}
const child = (f) => all(f.root).find((n) => n.props?.['data-component'] === 'IsolationCallResult')
for (const outcome of ['voicemail', 'invalid_number', 'disconnected']) {
  test(`${outcome} advances only after a successful refreshed file`, async () => {
    const f = fixture()
    try {
      await flush()
      child(f).props.onBusy(true)
      const saving = child(f).props.onSaved(outcome)
      child(f).props.onBusy(false)
      await saving
      await flush()
      assert.deepEqual(f.closed, [true])
      assert.equal(f.requests.filter((p) => p === 'work-queue/7/').length, 2)
    } finally {
      f.app.unmount()
    }
  })
}

test('reload failure and nonquick results leave the file open', async () => {
  for (const config of [
    { failReload: true, outcome: 'voicemail' },
    { outcome: 'other' },
    { outcome: 'callback' },
  ]) {
    const f = fixture(config)
    try {
      await flush()
      await child(f).props.onSaved(config.outcome)
      await flush()
      assert.deepEqual(f.closed, [])
    } finally {
      f.app.unmount()
    }
  }
})
