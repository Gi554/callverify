import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import test from 'node:test'
import assert from 'node:assert/strict'
import { parse, compileScript } from 'vue/compiler-sfc'
import { createRenderer, reactive, h, nextTick } from 'vue'
import ts from 'typescript'
const require = createRequire(import.meta.url)
let compiled = compileScript(
  parse(readFileSync(new URL('../src/SidePanel.vue', import.meta.url), 'utf8')).descriptor,
  { id: 'side-panel', inlineTemplate: true },
).content
compiled = compiled.replace(/import \{([^}]+)\} from 'lucide-vue-next'/g, (_, names) =>
  names
    .split(',')
    .filter((name) => name.trim())
    .map((name) => `const ${name.trim()}={render:()=>null}`)
    .join(';'),
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
  createElement: (tag) => ({
    tag,
    children: [],
    props: {},
    open: false,
    showModal() {
      this.open = true
    },
    close() {
      this.open = false
    },
  }),
  createText: (text) => ({ text }),
  createComment: () => ({}),
  setText: (node, text) => (node.text = text),
  setElementText: (node, text) => {
    node.children = []
    node.text = text
  },
  patchProp: (node, key, old, value) => (node.props[key] = value),
  parentNode: (node) => node.parent,
  nextSibling: () => null,
  insert(node, parent, anchor) {
    node.parent = parent
    const i = parent.children.indexOf(anchor)
    parent.children.splice(i < 0 ? parent.children.length : i, 0, node)
  },
  remove(node) {
    const i = node.parent?.children.indexOf(node)
    if (i >= 0) node.parent.children.splice(i, 1)
  },
})
const all = (node) => [node, ...(node.children || []).flatMap(all)]
async function flush() {
  for (let i = 0; i < 4; i++) await nextTick()
}
async function fixture() {
  const root = { children: [] },
    state = reactive({ open: true, closeDisabled: false })
  let requests = 0
  const app = renderer.createApp({
    setup: () => () =>
      h(component, { ...state, title: 'Fiche de recette', onRequestClose: () => requests++ }),
  })
  app.mount(root)
  await flush()
  return {
    state,
    dialog: all(root).find((n) => n.tag === 'dialog'),
    button: all(root).find((n) => n.tag === 'button'),
    requests: () => requests,
    app,
  }
}
test('close requests are controlled by the parent and blocked during an operation', async () => {
  const f = await fixture()
  try {
    assert.equal(f.dialog.open, true)
    f.button.props.onClick()
    assert.equal(f.requests(), 1)
    assert.equal(f.dialog.open, true)
    f.state.closeDisabled = true
    await flush()
    f.button.props.onClick()
    assert.equal(f.requests(), 1)
    let prevented = false
    f.dialog.props.onCancel({
      preventDefault() {
        prevented = true
      },
    })
    assert.equal(prevented, true)
    assert.equal(f.requests(), 1)
    f.state.closeDisabled = false
    await flush()
    f.dialog.props.onCancel({ preventDefault() {} })
    assert.equal(f.requests(), 2)
  } finally {
    f.app.unmount()
  }
})
test('parent controls opening, closing and teardown', async () => {
  const f = await fixture()
  assert.equal(f.dialog.open, true)
  f.state.open = false
  await flush()
  assert.equal(f.dialog.open, false)
  f.state.open = true
  await flush()
  assert.equal(f.dialog.open, true)
  f.app.unmount()
  assert.equal(f.dialog.open, false)
})
