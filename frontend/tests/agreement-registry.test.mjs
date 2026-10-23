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
let code = compileScript(
  parse(readFileSync(new URL('../src/AssuranceAgreementRegistry.vue', import.meta.url), 'utf8'))
    .descriptor,
  {
    id: 'agreement-registry',
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
    .replace(
      /import (\w+) from ['"]\.\/[^'"]+\.vue['"]/g,
      (_, name) =>
        `const ${name}={props:['open','title','contact'],setup(p,{slots,expose}){expose({close(){}});return()=>${JSON.stringify(name)}==='SidePanel'?(p.open?stubH('div',{'data-panel':p.title},slots.default?.()):null):stubH('div',{'data-editor':p.contact?.id})}}`,
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
const summary = (total) => ({
  deadlines: { overdue: 2, upcoming: 3, undated: 1, horizon_days: 30, as_of: '2026-10-23' },
  statistics: {
    total,
    as_of: '2026-10-23',
    horizon_days: 30,
    by_kind: { mandate: 1, contract: total - 1 },
    by_status: { draft: 0, tracking: total, archived: 0 },
    by_deadline: {},
  },
})
function fixture(empty = false) {
  const root = { children: [] },
    requests = []
  const app = renderer.createApp(component, {
    request: async (path) => {
      requests.push(path)
      if (path.startsWith('contacts/')) return { id: 42, name: 'Dossier Alpha' }
      return {
        count: empty ? 0 : 1,
        results: empty
          ? []
          : [
              {
                id: 5,
                reference: 'MAN-001',
                kind: 'mandate',
                status: 'tracking',
                starts_on: '2026-01-01',
                ends_on: '2026-10-30',
                deadline_state: 'upcoming',
                days_to_end: 7,
                document_count: 2,
                contact: { id: 42, name: 'Dossier Alpha' },
              },
            ],
        ...summary(empty ? 0 : 6),
      }
    },
    portal: async () => ({}),
  })
  app.mount(root)
  return { root, requests, close: () => app.unmount() }
}
const button = (f, match) =>
  all(f.root).find((n) => n.tag === 'button' && match.test(text(n).trim()))
const query = (f) => new URLSearchParams(f.requests.at(-1).split('?')[1])

test('alert cards toggle the deadline filter and the type filter applies in one click', async () => {
  const f = fixture()
  try {
    await flush()
    assert.match(text(f.root), /2Date de fin dépassée/)
    assert.match(text(f.root), /3Échéance dans les 30 jours/)
    assert.match(text(f.root), /MAN-001/)
    assert.match(text(f.root), /Dans 7 jour\(s\)/)
    button(f, /Date de fin dépassée/).props.onClick()
    await flush()
    assert.equal(query(f).get('deadline'), 'overdue')
    button(f, /Date de fin dépassée/).props.onClick()
    await flush()
    assert.equal(query(f).get('deadline'), null)
    button(f, /^Contrats$/).props.onClick()
    await flush()
    assert.equal(query(f).get('kind'), 'contract')
    assert.equal(query(f).get('page'), '1')
  } finally {
    f.close()
  }
})

test('advanced filters stay folded and the prospect card opens in a side panel', async () => {
  const f = fixture()
  try {
    await flush()
    assert.ok(!all(f.root).some((n) => n.tag === 'select'))
    button(f, /Plus de filtres/).props.onClick()
    await flush()
    assert.equal(all(f.root).filter((n) => n.tag === 'select').length, 2)
    button(f, /Ouvrir la fiche/).props.onClick()
    await flush()
    const panel = all(f.root).find((n) => n.props?.['data-panel'] === 'Dossier Alpha')
    assert.ok(panel)
    assert.ok(all(panel).some((n) => n.props?.['data-editor'] === 42))
  } finally {
    f.close()
  }
})

test('an empty registry explains where agreements come from', async () => {
  const f = fixture(true)
  try {
    await flush()
    assert.match(text(f.root), /Aucun mandat ni contrat pour ces critères/)
    assert.match(text(f.root), /depuis la fiche d’un prospect/)
    assert.ok(!all(f.root).some((n) => n.tag === 'table'))
  } finally {
    f.close()
  }
})
