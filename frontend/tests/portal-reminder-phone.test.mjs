import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import test from 'node:test'
import assert from 'node:assert/strict'
import { parse, compileScript } from 'vue/compiler-sfc'
import ts from 'typescript'
import { createRenderer, nextTick } from 'vue'

const require = createRequire(import.meta.url)
const source = readFileSync(new URL('../src/PortalReminderPhone.vue', import.meta.url), 'utf8')
let code = compileScript(parse(source).descriptor, {
  id: 'portal-reminder-phone',
  inlineTemplate: true,
  templateOptions: { compilerOptions: { hoistStatic: false } },
}).content
code =
  code
    .replace(/from ['"]vue['"]/g, `from '${pathToFileURL(require.resolve('vue')).href}'`)
    .replace(/vModelText as _vModelText,?/g, '') + ';const _vModelText={};'
code = ts.transpileModule(code, {
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
const all = (n) => [n, ...(n.children || []).flatMap(all)]
const text = (n) => (n.text || '') + (n.children || []).map(text).join('')
async function flush() {
  for (let i = 0; i < 5; i++) {
    await nextTick()
    await new Promise((resolve) => setImmediate(resolve))
  }
}
function fixture(reply) {
  const calls = []
  const root = { children: [] }
  const request = async (path, body, method) => {
    calls.push({ path, body, method })
    return method === 'PUT' ? { available: true, mobile: body.mobile } : reply
  }
  const app = renderer.createApp(component, { request })
  app.mount(root)
  return { root, calls, close: () => app.unmount() }
}

test('the Isolation client sees the field, empty by default, and saves a number', async () => {
  const f = fixture({ available: true, mobile: '' })
  try {
    await flush()
    assert.match(text(f.root), /Numéro mobile pour les rappels/)
    const form = all(f.root).find((n) => n.tag === 'form')
    await form.props.onSubmit({ preventDefault() {} })
    await flush()
    assert.deepEqual(f.calls.at(-1), {
      path: 'reminder-phone/',
      body: { mobile: '' },
      method: 'PUT',
    })
    assert.match(text(f.root), /Aucun SMS de rappel ne sera envoyé/)
  } finally {
    f.close()
  }
})

test('every other account sees nothing', async () => {
  const f = fixture({ available: false, mobile: '' })
  try {
    await flush()
    assert.doesNotMatch(text(f.root), /Numéro mobile/)
  } finally {
    f.close()
  }
})
