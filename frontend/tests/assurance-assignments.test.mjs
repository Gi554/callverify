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
const quota =
  'data:text/javascript;base64,' +
  Buffer.from(
    ts.transpileModule(readFileSync(new URL('../src/advisor-quota.ts', import.meta.url), 'utf8'), {
      compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
    }).outputText,
  ).toString('base64')
let code = compileScript(
  parse(readFileSync(new URL('../src/AssuranceAssignments.vue', import.meta.url), 'utf8'))
    .descriptor,
  {
    id: 'assurance-assignments',
    inlineTemplate: true,
    templateOptions: { compilerOptions: { hoistStatic: false } },
  },
).content
code =
  `import {h as stubH} from '${vue}';` +
  code
    .replace(/import \{([^}]+)\} from 'lucide-vue-next'/g, (_, names) =>
      names
        .split(',')
        .filter((name) => name.trim())
        .map((name) => `const ${name.trim()}={render:()=>null}`)
        .join(';'),
    )
    .replace(/from ['"]vue['"]/g, `from '${vue}'`)
    .replace("'./advisor-quota'", JSON.stringify(quota))
    .replace(
      /import (\w+) from ['"]\.\/[^'"]+\.vue['"]/g,
      (_, name) =>
        `const ${name}={props:['open','title','subtitle'],setup(p,{slots}){return()=>p.open?stubH('div',{'data-panel':p.title,'data-subtitle':p.subtitle},slots.default?.()):null}}`,
    )
    .replace(/vModelText as _vModelText,?/g, '')
    .replace(/vModelSelect as _vModelSelect,?/g, '') +
  ';const _vModelText={},_vModelSelect={};'
const component = (
  await import(
    'data:text/javascript;base64,' +
      Buffer.from(
        ts.transpileModule(code, {
          compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
        }).outputText,
      ).toString('base64')
  )
).default
const renderer = createRenderer({
  createElement: (tag) => ({ tag, children: [], props: {}, style: {} }),
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
const row = {
  id: 7,
  revision: 2,
  active: true,
  setter: { id: 21, name: 'Setter Démo 01' },
  advisor: { id: 31, name: 'Conseiller Démo 01' },
}
function fixture(role = 'administrator') {
  const root = { children: [] },
    requests = [],
    portal = [],
    navigations = []
  const app = renderer.createApp(component, {
    role,
    onNavigate: (target) => navigations.push(target),
    request: async (path, body, method) => {
      requests.push([path, body, method])
      if (path === 'advisor-usage/')
        return { results: [{ advisor_id: 31, booked: 3, attended: 3 }] }
      if (path.includes('/history/'))
        return {
          count: 2,
          results: [
            {
              id: 1,
              action: 'assignment.updated',
              actor_id: 1,
              created_at: '2026-10-22T10:00:00Z',
              metadata: { after: { active: false } },
            },
            {
              id: 2,
              action: 'assignment.created',
              actor_id: 1,
              created_at: '2026-10-21T10:00:00Z',
              metadata: { after: { active: true } },
            },
          ],
        }
      return { count: 1, results: [row] }
    },
    portal: async (path, body) => {
      portal.push([path, body])
      if (path === 'assurance/advisor-quotas/')
        return { results: [{ id: 31, name: 'Conseiller Démo 01', quota: 10 }] }
      return body ? { proof: 'proof' } : { count: 1, results: [{ id: 99, name: 'Nouveau' }] }
    },
  })
  app.mount(root)
  return { root, requests, portal, navigations, close: () => app.unmount() }
}
const button = (f, label) => all(f.root).find((n) => n.tag === 'button' && text(n).trim() === label)
const panel = (f, title) => all(f.root).find((n) => n.props?.['data-panel'] === title)

test('administrator filters by state in one click and reads a plain history', async () => {
  const f = fixture()
  try {
    await flush()
    assert.match(text(f.root), /Setter Démo 01/)
    assert.match(text(f.root), /Active/)
    assert.equal(panel(f, 'Nouvelle association'), undefined)
    button(f, 'Suspendues').props.onClick()
    await flush()
    assert.match(f.requests.at(-1)[0], /assignments\/\?page=1&search=&active=false/)
    button(f, 'Historique').props.onClick()
    await flush()
    const history = panel(f, 'Historique de l’association')
    assert.equal(history.props['data-subtitle'], 'Setter Démo 01 → Conseiller Démo 01')
    assert.match(text(history), /Association suspendue/)
    assert.match(text(history), /Association créée/)
    assert.doesNotMatch(text(history), /\{|metadata/)
  } finally {
    f.close()
  }
})

test('creation lives in a side panel and closes after associating', async () => {
  const f = fixture()
  try {
    await flush()
    button(f, 'Nouvelle association').props.onClick()
    await flush()
    const create = panel(f, 'Nouvelle association')
    assert.ok(create)
    const selects = all(create).filter((n) => n.tag === 'select')
    selects[0].props['onUpdate:modelValue']('99')
    selects[1].props['onUpdate:modelValue']('99')
    await flush()
    all(create)
      .find((n) => n.tag === 'form')
      .props.onSubmit({ preventDefault() {} })
    await flush()
    assert.deepEqual(f.portal.at(-1), [
      'assurance/participants/',
      { setter_id: 99, advisor_id: 99 },
    ])
    assert.deepEqual(f.requests.find(([path, body]) => path === 'assignments/' && body)[1], {
      proof: 'proof',
    })
    assert.equal(panel(f, 'Nouvelle association'), undefined)
    assert.match(text(f.root), /Conseiller associé au setter/)
  } finally {
    f.close()
  }
})

test('setter only sees the advisors available for booking', async () => {
  const f = fixture('setter')
  try {
    await flush()
    assert.match(text(f.root), /vous pouvez réserver/)
    assert.equal(button(f, 'Nouvelle association'), undefined)
    assert.equal(button(f, 'Historique'), undefined)
    assert.doesNotMatch(text(f.root), /lot dédié/)
    // Only the quota board, readable by every Assurance member, comes from the portal.
    assert.deepEqual(f.portal, [['assurance/advisor-quotas/', undefined]])
    assert.match(text(f.root), /7 restant\(s\) sur\s+10/)
    button(f, 'Préparer un rendez-vous').props.onClick()
    assert.deepEqual(f.navigations, ['contacts'])
    const filter = all(f.root).find((n) => n.tag === 'select')
    filter.props['onUpdate:modelValue']('false')
    filter.props.onChange()
    await flush()
    assert.match(f.requests.at(-1)[0], /assignments\/\?page=1&search=&active=false/)
    assert.ok(!f.requests.some(([path, body]) => body || path.includes('calls/')))
  } finally {
    f.close()
  }
})
