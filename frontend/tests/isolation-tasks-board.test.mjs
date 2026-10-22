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
  parse(readFileSync(new URL('../src/IsolationTasksBoard.vue', import.meta.url), 'utf8'))
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
    `const ${name}={props:['open','title','autoOpen','role','initialClose'],setup(p,{slots}){return()=>(${JSON.stringify(name)}==='SidePanel'&&!p.open)?null:stubH('div',{'data-component':${JSON.stringify(name)},'data-title':p.title,'data-auto-open':p.autoOpen,'data-initial-close':p.initialClose},slots.default?.())}}`,
)
code = "import {h as stubH} from '" + pathToFileURL(require.resolve('vue')).href + "';" + code
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
function fixture(role = 'setter') {
  const root = { children: [] },
    requests = []
  const task = {
    id: 5,
    prospect_id: 7,
    prospect_name: 'Prospect Démo',
    due_at: '2030-01-01T15:00:00Z',
    note: 'Rappel de démonstration',
    closed_at: null,
    revision: 2,
  }
  const app = renderer.createApp(component, {
    role,
    request: async (path, body) => {
      requests.push({ path, body })
      if (!path.startsWith('follow-ups/?')) return task
      const q = new URLSearchParams(path.split('?')[1]),
        state = q.get('state')
      return {
        count: state === 'upcoming' ? 30 : state === 'overdue' ? 2 : 1,
        next: state === 'upcoming' && q.get('page') === '1' ? 'next' : null,
        results: [
          {
            ...task,
            id: state === 'closed' ? 8 : 5,
            closed_at: state === 'closed' ? '2026-01-01T00:00:00Z' : null,
            overdue: state === 'overdue',
          },
        ],
      }
    },
  })
  app.mount(root)
  return { root, requests, app }
}
test('Isolation task board loads scoped buckets and opens finishing in the right drawer', async () => {
  const f = fixture()
  try {
    await flush()
    assert.equal(f.requests.length, 3)
    assert.ok(text(f.root).includes('À traiter'))
    assert.ok(text(f.root).includes('En retard'))
    assert.ok(text(f.root).includes('Terminées'))
    await all(f.root)
      .find((n) => n.tag === 'button' && text(n).trim() === 'Terminer')
      .props.onClick()
    await flush()
    assert.ok(f.requests.some((r) => r.path === 'follow-ups/5/?state=all'))
    assert.ok(
      all(f.root).some(
        (n) =>
          n.props?.['data-component'] === 'IsolationFollowUps' &&
          n.props['data-initial-close'] === true,
      ),
    )
    assert.equal(
      f.requests.some((r) => r.body !== undefined),
      false,
    )
  } finally {
    f.app.unmount()
  }
})
test('pagination keeps the applied search and administration uses the same task board', async () => {
  const f = fixture('administrator')
  try {
    await flush()
    assert.ok(text(f.root).includes('Tâches de l’équipe'))
    all(f.root)
      .find((n) => n.tag === 'input')
      .props['onUpdate:modelValue']('nouvelle recherche')
    await flush()
    await all(f.root)
      .find((n) => n.tag === 'button' && text(n).includes('Afficher plus'))
      .props.onClick()
    await flush()
    const path = f.requests.at(-1).path
    assert.equal(new URLSearchParams(path.split('?')[1]).get('search'), '')
    assert.equal(new URLSearchParams(path.split('?')[1]).get('page'), '2')
  } finally {
    f.app.unmount()
  }
})
