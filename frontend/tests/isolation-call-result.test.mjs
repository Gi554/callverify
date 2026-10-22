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
  parse(readFileSync(new URL('../src/IsolationCallResult.vue', import.meta.url), 'utf8'))
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
function fixture({ fail = false } = {}) {
  const root = { children: [] },
    writes = [],
    saved = []
  const app = renderer.createApp(component, {
    prospect: { id: 7, revision: 3 },
    request: async (path, body) => {
      if (body) {
        writes.push({ path, body })
        if (fail) throw new Error('Prospect modifié')
        return { recorded: true }
      }
      return { results: [], count: 0 }
    },
    onSaved: () => saved.push(true),
  })
  app.mount(root)
  return { root, writes, saved, app }
}
function set(node, value) {
  node.props['onUpdate:modelValue'](value)
}
async function submit(f) {
  await all(f.root)
    .find((n) => n.tag === 'form')
    .props.onSubmit({ preventDefault() {} })
  await flush()
}

test('declared callback saves a Canadian instant and never requests telephony', async () => {
  const f = fixture()
  try {
    await flush()
    set(
      all(f.root).find((n) => n.tag === 'select'),
      'callback',
    )
    await flush()
    set(
      all(f.root).find((n) => n.tag === 'input'),
      '2030-12-01T10:00',
    )
    set(
      all(f.root).find((n) => n.tag === 'textarea'),
      'Rappeler',
    )
    await submit(f)
    assert.equal(f.writes.length, 1)
    assert.equal(f.writes[0].path, 'work-queue/7/call-result/')
    assert.equal(f.writes[0].body.due_at, '2030-12-01T10:00:00-05:00')
    assert.equal(f.writes[0].body.revision, 3)
    assert.equal(f.writes[0].body.result, 'callback')
    assert.deepEqual(f.saved, [true])
  } finally {
    f.app.unmount()
  }
})

test('a failed declared result retains its note and does not acknowledge success', async () => {
  const f = fixture({ fail: true })
  try {
    await flush()
    set(
      all(f.root).find((n) => n.tag === 'select'),
      'invalid_number',
    )
    set(
      all(f.root).find((n) => n.tag === 'textarea'),
      'Déclaration manuelle',
    )
    await submit(f)
    assert.equal(f.saved.length, 0)
    assert.equal(all(f.root).find((n) => n.tag === 'textarea').model, 'Déclaration manuelle')
    assert.ok(all(f.root).some((n) => n.props?.role === 'alert' && n.text === 'Prospect modifié'))
  } finally {
    f.app.unmount()
  }
})
