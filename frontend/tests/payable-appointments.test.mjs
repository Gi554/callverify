import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import test from 'node:test'
import assert from 'node:assert/strict'
import { parse, compileScript } from 'vue/compiler-sfc'
import ts from 'typescript'
import { createRenderer, nextTick } from 'vue'

const require = createRequire(import.meta.url)
const vue = pathToFileURL(require.resolve('vue')).href
const source = readFileSync(new URL('../src/PayableAppointments.vue', import.meta.url), 'utf8')
let code = compileScript(parse(source).descriptor, {
  id: 'payable-appointments',
  inlineTemplate: true,
  templateOptions: { compilerOptions: { hoistStatic: false } },
}).content
code = code
  .replace(/from ['"]vue['"]/g, `from '${vue}'`)
  .replace(/vModelText as _vModelText,?/g, '')
  .replace(/vModelSelect as _vModelSelect,?/g, '')
  .replace(/import (\w+) from ['"]\.\/[^'"]+\.vue['"]/g, (_, name) =>
    name === 'StatKpi'
      ? `const StatKpi={props:['label','value'],setup(p){return()=>stubH('div',{'data-kpi':p.label},String(p.value))}}`
      : `const ${name}={props:['title'],setup(p){return()=>stubH('h1',{},p.title)}}`,
  )
code = `import {h as stubH} from '${vue}';` + code + ';const _vModelText={},_vModelSelect={};'
code = ts.transpileModule(code, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
}).outputText
const component = (
  await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'))
).default
const renderer = createRenderer({
  createElement: (tag) => ({ tag, children: [], props: {} }),
  createText: (text) => ({ text }),
  createComment: () => ({ text: '' }),
  setText: (node, text) => {
    node.text = text
  },
  setElementText: (node, text) => {
    node.children = []
    node.text = text
  },
  patchProp: (node, key, old, value) => {
    node.props[key] = value
  },
  parentNode: (node) => node.parent,
  nextSibling: () => null,
  insert(node, parent, anchor) {
    if (node.parent) {
      const i = node.parent.children.indexOf(node)
      if (i >= 0) node.parent.children.splice(i, 1)
    }
    node.parent = parent
    const i = parent.children.indexOf(anchor)
    parent.children.splice(i < 0 ? parent.children.length : i, 0, node)
  },
  remove(node) {
    const i = node.parent?.children.indexOf(node)
    if (i >= 0) node.parent.children.splice(i, 1)
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
const assurance = {
  from: '2026-11-02',
  to: '2026-11-08',
  split_sales: false,
  agents: [{ id: 21, name: 'Setter Un' }],
  totals: { presented: 8, payable: 8 },
  rows: [{ agent_id: 21, agent_name: 'Setter Un', presented: 8, payable: 8 }],
  definition: 'Seuls comptent les rendez-vous présentés.',
}
const isolation = {
  from: '2026-11-02',
  to: '2026-11-08',
  split_sales: true,
  agents: [{ id: 21, name: 'Setter Un' }],
  totals: { presented: 2, payable: 2, closed: 2, not_closed: 0 },
  rows: [
    { agent_id: 21, agent_name: 'Setter Un', presented: 2, closed: 2, not_closed: 0, payable: 2 },
  ],
  definition: 'Isolation.',
  changes: [
    {
      id: 1,
      kind: 'sale_status_changed',
      label: 'Statut de vente modifié',
      appointment_id: 5,
      agent_name: 'Setter Un',
      before: 'Non closé',
      after: 'Closé',
      late: true,
      at: '2026-11-11T16:00:00Z',
    },
  ],
}
function fixture(workspace, role, payload) {
  const root = { children: [] },
    paths = []
  const app = renderer.createApp(component, {
    workspace,
    role,
    request: async (path) => {
      paths.push(path)
      return payload
    },
  })
  app.mount(root)
  return { root, paths, close: () => app.unmount() }
}
const kpis = (f) =>
  Object.fromEntries(
    all(f.root)
      .filter((n) => n.props?.['data-kpi'])
      .map((n) => [n.props['data-kpi'], text(n)]),
  )
const button = (f, label) => all(f.root).find((n) => n.tag === 'button' && text(n).trim() === label)

test('Assurance shows attended appointments and the payable total for the week', async () => {
  const f = fixture('assurance', 'administrator', assurance)
  try {
    await flush()
    assert.match(
      f.paths[0],
      /^payable-appointments\/\?from=\d{4}-\d{2}-\d{2}&to=\d{4}-\d{2}-\d{2}$/,
    )
    assert.deepEqual(kpis(f), {
      'Rendez-vous présentés': '8',
      'Total des rendez-vous payables': '8',
    })
    assert.match(text(f.root), /Par setter/)
    assert.match(text(f.root), /Setter Un/)
    assert.doesNotMatch(text(f.root), /CAD|\$|solde|paiement/i)
  } finally {
    f.close()
  }
})

test('Isolation counts closed and not closed apart, with zero when empty, and the total', async () => {
  const f = fixture('isolation', 'administrator', isolation)
  try {
    await flush()
    assert.deepEqual(kpis(f), {
      'Présentés – Non closés': '0',
      'Présentés – Closés': '2',
      'Total des rendez-vous payables': '2',
    })
  } finally {
    f.close()
  }
})

test('the administrator sees the history of status changes, flagged when after the week closed', async () => {
  const f = fixture('isolation', 'administrator', isolation)
  try {
    await flush()
    assert.match(text(f.root), /Historique des modifications/)
    assert.match(text(f.root), /Non closé → Closé/)
    assert.match(text(f.root), /après la clôture de la semaine/)
  } finally {
    f.close()
  }
  const g = fixture('isolation', 'setter', { ...isolation, changes: [] })
  try {
    await flush()
    assert.doesNotMatch(text(g.root), /Historique des modifications/)
  } finally {
    g.close()
  }
})

test('a setter sees only their own figures, without team table or setter filter', async () => {
  const f = fixture('assurance', 'setter', { ...assurance, agents: [] })
  try {
    await flush()
    assert.ok(!f.paths[0].includes('agent='))
    assert.doesNotMatch(text(f.root), /Par setter|Tous les setters/)
    assert.equal(kpis(f)['Total des rendez-vous payables'], '8')
  } finally {
    f.close()
  }
})

test('"Cette semaine" reloads the current week', async () => {
  const f = fixture('assurance', 'administrator', assurance)
  try {
    await flush()
    await button(f, 'Cette semaine').props.onClick()
    await flush()
    assert.equal(f.paths.length, 2)
    assert.equal(f.paths[0], f.paths[1])
  } finally {
    f.close()
  }
})
