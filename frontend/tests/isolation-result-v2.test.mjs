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
  parse(readFileSync(new URL('../src/IsolationVisitResult.vue', import.meta.url), 'utf8'))
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
function fixture() {
  const root = { children: [] },
    writes = [],
    saved = []
  const app = renderer.createApp(component, {
    visit: { id: 7, revision: 2, prospect: { name: 'Client' } },
    request: async (path, body) => {
      writes.push({ path, body })
      return {}
    },
    onSaved: () => saved.push(true),
  })
  app.mount(root)
  return { root, writes, saved, close: () => app.unmount() }
}
const set = (node, value) => node.props['onUpdate:modelValue'](value)
async function submit(f) {
  await all(f.root)
    .find((n) => n.tag === 'form')
    .props.onSubmit({ preventDefault() {} })
  await flush()
}

test('attendance and sale require an explicit choice with optional notes', async () => {
  const f = fixture()
  try {
    await flush()
    await submit(f)
    assert.equal(f.writes.length, 0)
    const selects = all(f.root).filter((n) => n.tag === 'select')
    set(selects[0], 'yes')
    set(selects[1], 'no')
    await flush()
    await submit(f)
    assert.deepEqual(f.writes[0].body, {
      revision: 2,
      performed: true,
      closed: false,
      outcome: 'completed',
      note: '',
    })
  } finally {
    f.close()
  }
})

test('a sale requires attendance and a no-show cannot silently become a sale', async () => {
  const f = fixture()
  try {
    await flush()
    let selects = all(f.root).filter((n) => n.tag === 'select')
    set(selects[0], 'no')
    set(selects[1], 'yes')
    await flush()
    await submit(f)
    assert.equal(f.writes.length, 0)
    set(selects[1], 'no')
    await flush()
    await submit(f)
    assert.equal(f.writes[0].body.performed, false)
    assert.equal(f.writes[0].body.closed, false)
  } finally {
    f.close()
  }
})
