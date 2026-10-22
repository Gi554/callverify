import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import test from 'node:test'
import assert from 'node:assert/strict'
import { parse, compileScript } from 'vue/compiler-sfc'
import { createRenderer, h, nextTick } from 'vue'
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
  parse(readFileSync(new URL('../src/IsolationCloserVisits.vue', import.meta.url), 'utf8'))
    .descriptor,
  { id: 'qualification', inlineTemplate: true },
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
code = `import {h} from '${pathToFileURL(require.resolve('vue')).href}';` + code
code = code.replace(/import (\w+) from ['"]\.\/[^'"]+\.vue['"]/g, (_, name) =>
  name === 'SidePanel'
    ? `const SidePanel={props:['open','title','eyebrow','closeDisabled'],emits:['requestClose'],inheritAttrs:false,setup(props,{slots,emit}){return ()=>[h('button',{onClick:()=>emit('requestClose')},'Fermer le panneau'),slots.default?.()]}}`
    : `const ${name}={render:()=>null}`,
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
  parentNode: (n) => n.parent,
  nextSibling: () => null,
  insert(n, p, a) {
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
function fixture({ fail = false, existing = false } = {}) {
  const root = { children: [] },
    writes = []
  const row = {
    id: 7,
    revision: 3,
    status: 'scheduled',
    starts_at: '2020-01-01T10:00:00Z',
    ends_at: '2020-01-01T11:00:00Z',
    timezone: 'America/Toronto',
    prospect: { name: 'Client', phone: '5145550100' },
    original_setter: { name: 'Setter' },
    closer: { name: 'Closer' },
    result: existing ? { performed: true, closed: null, note: 'Ancien résultat' } : null,
  }
  const app = renderer.createApp(component, {
    request: async (path, body) => {
      if (body) {
        writes.push({ path, body })
        if (fail) throw new Error('Visite modifiée')
        row.revision++
        row.result = { performed: body.performed, closed: body.closed, note: body.note }
        return { recorded: true }
      }
      if (path.includes('history/')) return { results: [], count: 0 }
      if (path === 'closer-visits/?page=1') return { results: [row], count: 1 }
      return { ...row }
    },
  })
  app.mount(root)
  return { root, writes, app }
}
async function open(f) {
  all(f.root)
    .find((n) => n.tag === 'button' && n.text === 'Ouvrir la visite')
    .props.onClick()
  await flush()
}
function set(node, value) {
  node.props['onUpdate:modelValue'](value)
}
async function fill(f) {
  const selects = all(f.root).filter((n) => n.tag === 'select')
  set(selects[0], 'yes')
  set(selects[1], 'yes')
  all(f.root)
    .find((n) => n.tag === 'form')
    .props.onInput()
  await flush()
}
async function submit(f) {
  await all(f.root)
    .find((n) => n.tag === 'form')
    .props.onSubmit({ preventDefault() {} })
  await flush()
}

test('closer explicitly declares held and sold with optional notes and the visit revision', async () => {
  const f = fixture()
  try {
    await flush()
    await open(f)
    const selects = all(f.root).filter((n) => n.tag === 'select')
    assert.equal(selects[0].model, '')
    assert.equal(selects[1].model, '')
    await fill(f)
    await submit(f)
    assert.equal(f.writes[0].path, 'closer-visits/7/result/')
    assert.equal(f.writes[0].body.revision, 3)
    assert.equal(f.writes[0].body.performed, true)
    assert.equal(f.writes[0].body.closed, true)
    assert.equal(f.writes[0].body.note, '')
    assert.match(f.writes[0].body.request_id, /^[0-9a-f-]{36}$/)
  } finally {
    f.app.unmount()
  }
})

test('failed closer writes preserve the draft and a rejected close keeps the panel open', async () => {
  const f = fixture({ fail: true })
  try {
    await flush()
    await open(f)
    await fill(f)
    set(
      all(f.root).find((n) => n.tag === 'textarea'),
      'Ne pas perdre',
    )
    await submit(f)
    assert.ok(all(f.root).some((n) => n.props?.role === 'alert' && n.text === 'Visite modifiée'))
    all(f.root)
      .find((n) => n.tag === 'button' && n.text === 'Fermer le panneau')
      .props.onClick()
    await flush()
    assert.ok(all(f.root).some((n) => n.tag === 'form'))
    assert.equal(all(f.root).find((n) => n.tag === 'textarea').model, 'Ne pas perdre')
  } finally {
    f.app.unmount()
  }
})

test('legacy interest does not preselect a sale and correcting it requires a reason', async () => {
  const f = fixture({ existing: true })
  try {
    await flush()
    await open(f)
    const selects = all(f.root).filter((n) => n.tag === 'select')
    assert.equal(selects[0].model, 'yes')
    assert.equal(selects[1].model, '')
    const areas = all(f.root).filter((n) => n.tag === 'textarea')
    assert.equal(areas.length, 2)
    assert.notEqual(areas[1].props.required, undefined)
    set(selects[1], 'no')
    set(areas[1], 'Qualification du résultat')
    await submit(f)
    assert.equal(f.writes[0].body.closed, false)
    assert.equal(f.writes[0].body.reason, 'Qualification du résultat')
  } finally {
    f.app.unmount()
  }
})
