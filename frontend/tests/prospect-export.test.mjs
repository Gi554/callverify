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
  parse(readFileSync(new URL('../src/ProspectExport.vue', import.meta.url), 'utf8')).descriptor,
  {
    id: 'prospect-export',
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
function fixture(fail = false) {
  const root = { children: [] },
    requests = [],
    links = [],
    revoked = []
  globalThis.document = {
    createElement: () => {
      const link = { click: () => links.push({ href: link.href, download: link.download }) }
      return link
    },
  }
  globalThis.URL.createObjectURL = (blob) => `blob:${blob}`
  globalThis.URL.revokeObjectURL = (url) => revoked.push(url)
  const app = renderer.createApp(component, {
    path: 'work-queue/export/',
    filters: { search: 'Dupont', owner: '', due: 'true' },
    request: async (path) => {
      requests.push(path)
      if (fail) throw new Error('Plus de 50000 lignes : précisez les filtres avant d’exporter.')
      return 'file'
    },
  })
  app.mount(root)
  return { root, requests, links, revoked, close: () => app.unmount() }
}
const button = (f, match) =>
  all(f.root).find((n) => n.tag === 'button' && match.test(text(n).trim()))

test('CSV and Excel downloads carry the current filters', async () => {
  const f = fixture()
  try {
    button(f, /^CSV$/).props.onClick()
    await flush()
    button(f, /^Excel$/).props.onClick()
    await flush()
    assert.deepEqual(f.requests, [
      'work-queue/export/?file=csv&search=Dupont&due=true',
      'work-queue/export/?file=xlsx&search=Dupont&due=true',
    ])
    assert.deepEqual(f.links, [
      { href: 'blob:file', download: 'prospects.csv' },
      { href: 'blob:file', download: 'prospects.xlsx' },
    ])
    assert.deepEqual(f.revoked, ['blob:file', 'blob:file'])
  } finally {
    f.close()
  }
})

test('a refused export shows the server message', async () => {
  const f = fixture(true)
  try {
    button(f, /^Excel$/).props.onClick()
    await flush()
    assert.match(text(f.root), /précisez les filtres/)
    assert.equal(f.links.length, 0)
    assert.equal(button(f, /^Excel$/).props.disabled, false)
  } finally {
    f.close()
  }
})
