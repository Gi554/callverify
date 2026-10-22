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
  parse(readFileSync(new URL('../src/AssuranceSetterTasks.vue', import.meta.url), 'utf8'))
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
code =
  code
    .replace(/vModelText as _vModelText,?/g, '')
    .replace(/vModelSelect as _vModelSelect,?/g, '')
    .replace(/vModelDynamic as _vModelDynamic,?/g, '') +
  ';const _vModelText={},_vModelSelect={},_vModelDynamic={};'
code = code.replace(
  /import (\w+) from ['"]\.\/[^'"]+\.vue['"]/g,
  (_, name) =>
    `const ${name}={props:['open','title','autoOpen','role','taskId'],setup(p,{slots}){return()=>(${JSON.stringify(name)}==='SidePanel'&&!p.open)?null:stubH('div',{'data-component':${JSON.stringify(name)},'data-title':p.title,'data-auto-open':p.autoOpen,'data-task-id':p.taskId},slots.default?.())}}`,
)
code = "import {h as stubH} from '" + pathToFileURL(require.resolve('vue')).href + "';" + code
code = code.replace(
  "'./booking-time'",
  JSON.stringify(url(readFileSync(new URL('../src/booking-time.ts', import.meta.url), 'utf8'))),
)
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
const text = (n) => (n.text || '') + (n.children || []).map(text).join('')
function fixture(role) {
  const root = { children: [] },
    writes = [],
    row = {
      id: 5,
      contact_name: 'Prospect',
      due_at: '2030-01-01T15:00:00Z',
      reason: 'Suivi',
      priority: 'normal',
      revision: 2,
    }
  const app = renderer.createApp(component, {
    role,
    portal: async () => ({}),
    request: async (path, body) => {
      if (body) writes.push({ path, body })
      if (path.startsWith('follow-ups/summary/'))
        return { total: 3, open: 2, closed: 1, overdue: 1, open_priorities: { normal: 2 } }
      if (path.startsWith('follow-ups/5/')) return row
      return { results: [row], count: 1, next: null }
    },
  })
  app.mount(root)
  return { root, writes, app }
}
test('Assurance administration opens full management controls and policy without changing data', async () => {
  const f = fixture('administrator')
  try {
    await flush()
    assert.ok(text(f.root).includes('Tâches de l’équipe'))
    assert.ok(text(f.root).includes('Voir l’agenda de l’équipe'))
    await all(f.root)
      .find((n) => n.tag === 'button' && text(n).trim() === 'Ouvrir')
      .props.onClick()
    await flush()
    assert.ok(
      all(f.root).some(
        (n) =>
          n.props?.['data-component'] === 'AssuranceFollowUps' && n.props['data-task-id'] === 5,
      ),
    )
    await all(f.root)
      .find((n) => n.tag === 'button' && text(n).trim() === 'Règles des suivis')
      .props.onClick()
    await flush()
    assert.ok(all(f.root).some((n) => n.props?.['data-component'] === 'AssuranceFollowUpPolicy'))
    assert.equal(f.writes.length, 0)
  } finally {
    f.app.unmount()
  }
})
test('setter keeps the existing task detail without administrator policy or reassignment controls', async () => {
  const f = fixture('setter')
  try {
    await flush()
    assert.equal(text(f.root).includes('Règles des suivis'), false)
    assert.ok(text(f.root).includes('Voir mes rendez-vous'))
    await all(f.root)
      .find((n) => n.tag === 'button' && text(n).trim() === 'Ouvrir')
      .props.onClick()
    await flush()
    assert.equal(
      all(f.root).some((n) => n.props?.['data-component'] === 'AssuranceFollowUps'),
      false,
    )
    assert.ok(text(f.root).includes('Le suivi à réaliser'))
    assert.equal(f.writes.length, 0)
  } finally {
    f.app.unmount()
  }
})
