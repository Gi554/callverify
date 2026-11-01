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
const display = await import(
  url(readFileSync(new URL('../src/isolation-visit-display.ts', import.meta.url), 'utf8'))
)
let code = compileScript(
  parse(readFileSync(new URL('../src/IsolationClientHome.vue', import.meta.url), 'utf8'))
    .descriptor,
  { id: 'home', inlineTemplate: true },
).content
code = code
  .replace(/from ['"]vue['"]/g, `from '${vue}'`)
  .replace(/import \{([^}]+)\} from 'lucide-vue-next'/g, (_, names) =>
    names
      .split(',')
      .filter((n) => n.trim())
      .map((n) => `const ${n.trim()}={render:()=>null}`)
      .join(';'),
  )
  .replace(/import (\w+) from ['"]\.\/[^'"]+\.vue['"]/g, (_, name) =>
    name === 'IsolationVisitCard'
      ? `const ${name}={props:['visit'],emits:['open'],setup(p,{emit}){return()=>h('button',{onClick:()=>emit('open')},p.visit.prospect.name)}}`
      : `const ${name}={render:()=>null}`,
  )
const component = (await import(url(`import {h} from '${vue}';` + code))).default
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

test('home reads scoped live counters, navigates and opens the exact upcoming visit', async () => {
  const paths = [],
    opened = [],
    navigated = [],
    root = { children: [] }
  const app = renderer.createApp(component, {
    summary: { upcoming: 20, results_due: 3, reported: 7, prospects: 25 },
    username: 'Test',
    request: async (path) => {
      paths.push(path)
      return path.startsWith('visits/')
        ? { results: [{ id: 42, prospect: { name: 'Jade' } }] }
        : { count: 4 }
    },
    onOpen: (id) => opened.push(id),
    onNavigate: (id) => navigated.push(id),
  })
  app.mount(root)
  try {
    await flush()
    assert.deepEqual(paths, ['visits/?period=upcoming&page_size=3', 'client-follow-ups/?page=1'])
    const text = all(root)
      .map((n) => n.text || '')
      .join(' ')
    assert.match(text, /20/)
    assert.match(text, /4 relance/)
    all(root)
      .find((n) => n.tag === 'button' && n.text === 'Jade')
      .props.onClick()
    assert.deepEqual(opened, [42])
    const button = all(root).find(
      (n) => n.tag === 'button' && all(n).some((x) => x.text === 'Rendez-vous à venir'),
    )
    button.props.onClick()
    assert.deepEqual(navigated, ['appointments'])
  } finally {
    app.unmount()
  }
})
test('home exposes an unavailable visits service and never invents a zero callback count', async () => {
  const root = { children: [] }
  const app = renderer.createApp(component, {
    summary: {},
    username: 'Test',
    request: async () => {
      throw new Error('Indisponible')
    },
  })
  app.mount(root)
  try {
    await flush()
    assert.ok(all(root).some((n) => n.props?.role === 'alert' && n.text === 'Indisponible'))
    const text = all(root)
      .map((n) => n.text || '')
      .join(' ')
    assert.match(text, /Dates et notes de rappel/)
    assert.doesNotMatch(text, /0 relance/)
  } finally {
    app.unmount()
  }
})
test('visit states preserve cancellations, absence, missing sale and explicit unqualification', () => {
  assert.equal(
    display.visitStatus({
      status: 'cancelled',
      next_visit_id: 2,
      result: { performed: true, closed: true },
    }),
    'Reprogrammé',
  )
  assert.equal(
    display.visitStatus({ result: { outcome: 'unqualified', performed: false } }),
    'Non qualifié',
  )
  assert.equal(display.visitStatus({ result: { performed: false } }), 'Non présenté')
  assert.equal(
    display.visitStatus({ result: { performed: true, closed: null } }),
    'Vente à préciser',
  )
  assert.equal(display.visitTone({ result_due: true }), 'amber')
})
test('visit tiles use the Quebec date across midnight and daylight saving changes', () => {
  assert.equal(display.visitDay('2026-11-02T02:30:00Z'), '01')
  assert.match(display.visitTime('2026-11-01T05:30:00Z'), /01.*30/)
  assert.match(display.visitTime('2026-11-01T06:30:00Z'), /01.*30/)
})
