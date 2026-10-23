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
const source = (name) => readFileSync(new URL(`../src/${name}.ts`, import.meta.url), 'utf8')
const booking = url(source('booking-time'))
const grid = url(source('calendar-grid').replace("'./booking-time'", JSON.stringify(booking)))
const status = url(source('appointment-status'))
let code = compileScript(
  parse(readFileSync(new URL('../src/AssuranceAdvisorProspects.vue', import.meta.url), 'utf8'))
    .descriptor,
  {
    id: 'admin-calendar',
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
  .replace(/from ['"]vue['"]/g, `from '${vue}'`)
  .replace("'./calendar-grid'", JSON.stringify(grid))
  .replace("'./appointment-status'", JSON.stringify(status))
  .replace("'./advisor-quota'", JSON.stringify(url(source('advisor-quota'))))
  .replace(
    /import (\w+) from ['"]\.\/[^'"]+\.vue['"]/g,
    (_, name) =>
      `const ${name}={props:['open','title','role'],setup(p,{slots}){return()=>(${JSON.stringify(name)}==='SidePanel'&&!p.open)?null:stubH('div',{'data-component':${JSON.stringify(name)}},slots.default?.())}}`,
  )
code =
  `import {h as stubH} from '${vue}';` +
  code.replace(/vModelText as _vModelText,?/g, '').replace(/vModelSelect as _vModelSelect,?/g, '') +
  ';const _vModelText={},_vModelSelect={};'
const component = (await import(url(code))).default
const renderer = createRenderer({
  createElement: (tag) => ({ tag, children: [], props: {} }),
  createText: (text) => ({ text }),
  createComment: () => ({}),
  setText: (n, t) => (n.text = t),
  setElementText: (n, t) => {
    n.children = []
    n.text = t
  },
  patchProp: (n, k, o, v) => (n.props[k] = v),
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
const text = (n) => (n.text || '') + (n.children || []).map(text).join('')
async function flush() {
  for (let i = 0; i < 5; i++) {
    await nextTick()
    await new Promise((resolve) => setImmediate(resolve))
  }
}

function fixture() {
  const root = { children: [] },
    requests = []
  const app = renderer.createApp(component, {
    username: 'advisor.demo',
    portal: async () => ({ results: [{ id: 31, name: 'advisor.demo', quota: 20 }] }),
    request: async (path) => {
      requests.push(path)
      if (path === 'advisor-usage/')
        return { results: [{ advisor_id: 31, booked: 18, attended: 1 }] }
      const page = new URLSearchParams(path.split('?')[1]).get('page')
      return {
        count: 26,
        totals: { assigned: 26, attended: 1, absent: 3 },
        results:
          page === '2'
            ? [{ id: 26, name: 'Dernier client', phone: 'raw', attended: 0, appointment_id: null }]
            : [
                {
                  id: 1,
                  name: 'Client affecté',
                  phone: 'raw',
                  email: 'demo@example.invalid',
                  attended: 1,
                  appointment_id: 7,
                },
              ],
      }
    },
  })
  app.mount(root)
  return { root, requests, close: () => app.unmount() }
}
const button = (f, label) => all(f.root).find((n) => n.tag === 'button' && text(n).trim() === label)
test('advisor list separates assigned prospects, attendance and remaining quota, with pagination', async () => {
  const f = fixture()
  try {
    await flush()
    assert.match(text(f.root), /Prospects attribués26/)
    assert.match(text(f.root), /Rendez-vous tenus1/)
    assert.match(text(f.root), /Restant sur l’objectif19/)
    assert.match(text(f.root), /3 absence/)
    assert.match(text(f.root), /Client affecté/)
    button(f, 'Suivant').props.onClick()
    await flush()
    assert.ok(f.requests.some((p) => p.includes('page=2')))
    assert.match(text(f.root), /Dernier client/)
    assert.match(text(f.root), /Aucun rendez-vous attribué/)
    assert.equal(button(f, 'Suivant').props.disabled, true)
  } finally {
    f.close()
  }
})
