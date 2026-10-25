import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import test from 'node:test'
import assert from 'node:assert/strict'
import { parse, compileScript } from 'vue/compiler-sfc'
import ts from 'typescript'
import { createRenderer, nextTick } from 'vue'

const require = createRequire(import.meta.url)
const source = readFileSync(new URL('../src/PortalCallRules.vue', import.meta.url), 'utf8')
let code = compileScript(parse(source).descriptor, {
  id: 'portal-call-rules',
  inlineTemplate: true,
  templateOptions: { compilerOptions: { hoistStatic: false } },
}).content
code =
  code
    .replace(/from ['"]vue['"]/g, `from '${pathToFileURL(require.resolve('vue')).href}'`)
    .replace(/vModelText as _vModelText,?/g, '')
    .replace(/vModelCheckbox as _vModelCheckbox,?/g, '') +
  ';const _vModelText={},_vModelCheckbox={};'
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
function fixture() {
  const calls = []
  const root = { children: [] }
  const request = async (path, body, method) => {
    calls.push({ path, body, method })
    if (path.endsWith('call-rules/'))
      return {
        enforce_hours: true,
        timezone: 'America/Montreal',
        weekday_start: '09:30',
        weekday_end: '21:30',
        weekend_start: '10:00',
        weekend_end: '18:00',
        revision: 3,
        allowed_now: false,
        message: 'Appels autorisés de 09:30 à 21:30.',
      }
    if (path.includes('call-exclusions/?'))
      return {
        count: 1,
        results: [{ id: 7, number: '15145550101', reason: 'Demande du client' }],
      }
    return {}
  }
  const app = renderer.createApp(component, { space: 'assurance', request })
  app.mount(root)
  return { root, calls, close: () => app.unmount() }
}

test('administrator sees the hours rules, the current state and the exclusion list', async () => {
  const f = fixture()
  try {
    await flush()
    const page = text(f.root)
    assert.match(page, /appels interdits/)
    assert.match(page, /15145550101/)
    assert.match(page, /Demande du client/)
    assert.deepEqual(
      f.calls.map((c) => c.path.split('?')[0]),
      ['workspaces/assurance/call-rules/', 'workspaces/assurance/call-exclusions/'],
    )
  } finally {
    f.close()
  }
})

test('removing an excluded number asks for confirmation then deletes it', async () => {
  const f = fixture()
  const asked = []
  globalThis.confirm = (message) => {
    asked.push(message)
    return true
  }
  try {
    await flush()
    const remove = all(f.root).find((n) => n.tag === 'button' && text(n).trim() === 'Retirer')
    await remove.props.onClick()
    await flush()
    assert.match(asked[0], /15145550101/)
    const deletion = f.calls.find((c) => c.method === 'DELETE')
    assert.equal(deletion.path, 'workspaces/assurance/call-exclusions/7/')
  } finally {
    f.close()
  }
})
