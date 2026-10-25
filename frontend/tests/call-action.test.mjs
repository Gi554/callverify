import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import test from 'node:test'
import assert from 'node:assert/strict'
import { parse, compileScript } from 'vue/compiler-sfc'
import ts from 'typescript'
import { createRenderer, nextTick } from 'vue'

const require = createRequire(import.meta.url)
const source = readFileSync(new URL('../src/CallAction.vue', import.meta.url), 'utf8')
let compiled = compileScript(parse(source).descriptor, {
  id: 'call-action',
  inlineTemplate: true,
}).content
compiled = compiled.replace(
  /import \{\s*Phone,\s*PhoneCall,\s*RefreshCw,?\s*\} from 'lucide-vue-next'/,
  'const Phone={render:()=>null},PhoneCall={render:()=>null},RefreshCw={render:()=>null}',
)
compiled = compiled.replace(
  /from ['"]vue['"]/g,
  `from '${pathToFileURL(require.resolve('vue')).href}'`,
)
const code = ts.transpileModule(compiled, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
}).outputText
const component = (
  await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'))
).default
const renderer = createRenderer({
  createElement: (tag) => ({ tag, children: [], props: {} }),
  createText: (text) => ({ text }),
  createComment: () => ({ text: '' }),
  setText: (node, text) => {
    node.text = text
  },
  setElementText: (node, text) => {
    node.children = []
    node.text = text
  },
  patchProp: (node, key, old, value) => {
    node.props[key] = value
  },
  parentNode: (node) => node.parent,
  nextSibling: () => null,
  insert(node, parent, anchor) {
    if (node.parent) {
      const i = node.parent.children.indexOf(node)
      if (i >= 0) node.parent.children.splice(i, 1)
    }
    node.parent = parent
    const i = parent.children.indexOf(anchor)
    parent.children.splice(i < 0 ? parent.children.length : i, 0, node)
  },
  remove(node) {
    const i = node.parent?.children.indexOf(node)
    if (i >= 0) node.parent.children.splice(i, 1)
  },
})
const text = (node) => (node.text || '') + (node.children || []).map(text).join('')
function fixture(portal, extra = {}) {
  const saved = new Map()
  globalThis.sessionStorage = {
    getItem: (k) => saved.get(k) || null,
    setItem: (k, v) => saved.set(k, v),
    removeItem: (k) => saved.delete(k),
  }
  const root = { children: [] }
  let intents = 0
  const app = renderer.createApp(component, {
    workspace: 'isolation',
    resourceId: 1,
    phone: 'synthetic number',
    prepare: async () => {
      intents++
      return { proof: 'synthetic proof' }
    },
    portal,
    ...extra,
  })
  app.mount(root)
  const all = (node) => [node, ...(node.children || []).flatMap(all)]
  async function click(label) {
    const button = all(root).find((n) => n.tag === 'button' && text(n).trim() === label)
    assert.ok(button, label)
    assert.ok(!button.props.disabled)
    await button.props.onClick()
    for (let i = 0; i < 5; i++) await nextTick()
  }
  return { root, saved, click, intents: () => intents, close: () => app.unmount() }
}
test('disabled capability never authorizes or sends a call', async () => {
  const paths = []
  const f = fixture(async (path) => {
    paths.push(path)
    return { enabled: false, post_associated: true }
  })
  try {
    await f.click('Appeler')
    assert.match(text(f.root), /désactivés/)
    assert.equal(f.intents(), 0)
    assert.deepEqual(paths, ['isolation/calls/options/'])
  } finally {
    f.close()
  }
})
test('explicit confirmation sends once; status inspection is GET-only', async () => {
  let sends = 0
  const f = fixture(async (path, body) => {
    if (path.endsWith('options/')) return { enabled: true, post_associated: true }
    if (body) {
      sends++
      return { state: 'accepted' }
    }
    return { state: 'accepted' }
  })
  try {
    await f.click('Appeler')
    assert.equal(sends, 0)
    // The confirmation replaces the call button instead of duplicating it.
    assert.match(text(f.root), /Appeler le .+ \?/)
    assert.doesNotMatch(text(f.root), /Appeler(?! le)/)
    await f.click('Lancer l’appel')
    assert.equal(sends, 1)
    await f.click('Vérifier la commande')
    assert.equal(sends, 1)
    assert.equal(f.intents(), 1)
    assert.equal(f.saved.size, 1)
  } finally {
    f.close()
  }
})
test('call session sends once without confirmation when the checks pass', async () => {
  let sends = 0
  const f = fixture(
    async (path, body) => {
      if (path.endsWith('options/')) return { enabled: true, post_associated: true }
      if (body) {
        sends++
        return { state: 'accepted' }
      }
      return { state: 'accepted' }
    },
    { autoOpen: true, autoSend: true },
  )
  try {
    for (let i = 0; i < 10; i++) await nextTick()
    assert.equal(sends, 1)
    assert.equal(f.intents(), 1)
    assert.doesNotMatch(text(f.root), /Appeler le .+ ?/)
  } finally {
    f.close()
  }
})
test('call session never sends when calls are disabled', async () => {
  let sends = 0
  const f = fixture(
    async (path, body) => {
      if (body) sends++
      return { enabled: false, post_associated: true }
    },
    { autoOpen: true, autoSend: true },
  )
  try {
    for (let i = 0; i < 10; i++) await nextTick()
    assert.equal(sends, 0)
    assert.equal(f.intents(), 0)
  } finally {
    f.close()
  }
})
test('outside the permitted hours no intent and no send happen, with the reason shown', async () => {
  let sends = 0
  const f = fixture(async (path, body) => {
    if (body) sends++
    return {
      enabled: true,
      post_associated: true,
      call_window: { allowed: false, message: 'Appels autorisés de 09:30 à 21:30.' },
    }
  })
  try {
    await f.click('Appeler')
    assert.match(text(f.root), /Appels autorisés de 09:30/)
    assert.equal(sends, 0)
    assert.equal(f.intents(), 0)
  } finally {
    f.close()
  }
})
test('lost dispatch response preserves reference and prevents another send', async () => {
  let sends = 0
  const f = fixture(async (path, body) => {
    if (path.endsWith('options/')) return { enabled: true, post_associated: true }
    if (body) {
      sends++
      throw new Error('Network interrupted')
    }
    return { state: 'unknown' }
  })
  try {
    await f.click('Appeler')
    await f.click('Lancer l’appel')
    assert.equal(f.saved.size, 1)
    await f.click('Vérifier la commande')
    assert.equal(sends, 1)
    assert.match(text(f.root), /Aucune relance automatique/)
    assert.doesNotMatch(text(f.root), /Préparer un nouvel appel/)
  } finally {
    f.close()
  }
})
