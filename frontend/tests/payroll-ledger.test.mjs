import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import test from 'node:test'
import assert from 'node:assert/strict'
import { parse, compileScript } from 'vue/compiler-sfc'
import { createRenderer, nextTick } from 'vue'
import ts from 'typescript'
import { withStatComponents } from './stat-components.mjs'
const require = createRequire(import.meta.url)
const vue = pathToFileURL(require.resolve('vue')).href
const url = (code) =>
  'data:text/javascript;base64,' +
  Buffer.from(
    ts.transpileModule(code, {
      compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
    }).outputText,
  ).toString('base64')
let code = compileScript(
  parse(readFileSync(new URL('../src/PayrollLedger.vue', import.meta.url), 'utf8')).descriptor,
  {
    id: 'activity',
    inlineTemplate: true,
    templateOptions: { compilerOptions: { hoistStatic: false } },
  },
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
code = code
  .replace(
    /import IsolationPageHeader from ['"]\.\/IsolationPageHeader\.vue['"]/g,
    `const IsolationPageHeader={props:['title'],render(){return this.title}}`,
  )
  .replace(
    /import SidePanel from ['"]\.\/SidePanel\.vue['"]/g,
    `const SidePanel={props:['open'],setup(p,{slots}){return()=>p.open?slots.default?.():null}}`,
  )
code =
  withStatComponents(code)
    .replace(/vModelText as _vModelText,?/g, '')
    .replace(/vModelSelect as _vModelSelect,?/g, '') + ';const _vModelText={},_vModelSelect={};'
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

const button = (f, label) => all(f.root).find((n) => n.tag === 'button' && text(n).trim() === label)
function fixture({ role = 'administrator', fail = false } = {}) {
  const root = { children: [] },
    writes = []
  const state = {
    agent_id: 21,
    agent_name: 'Alice',
    revision: 3,
    currency: 'CAD',
    period: {
      amount_cad: '75.00',
      attendance: 1,
      sales: 1,
      attendance_amount_cad: '25.00',
      sale_bonus_cad: '50.00',
    },
    generated_cad: '75.00',
    paid_cad: '0.00',
    to_pay_cad: '75.00',
    to_regularize_cad: '0.00',
    goal: null,
    unpriced: 0,
    terms: [],
    payments: [],
    payments_count: 0,
    adjustments: [],
    adjustments_count: 0,
    definition: 'Registre sans virement',
  }
  const app = renderer.createApp(component, {
    workspace: 'isolation',
    role,
    portal: async () => ({ proof: 'signed-agent-proof' }),
    request: async (path, body) => {
      if (body) {
        writes.push({ path, body })
        if (fail) throw new Error('Solde modifié')
        return { recorded: true }
      }
      return path.startsWith('payroll/?') ? { results: [state] } : { ...state }
    },
  })
  app.mount(root)
  return { root, app, writes }
}
test('agent payroll is read only while administrator records an external payment with revision and idempotency', async () => {
  const own = fixture({ role: 'setter' })
  try {
    await flush()
    assert.match(text(own.root), /Mes gains et mon objectif/)
    assert.equal(button(own, 'Enregistrer un paiement'), undefined)
    assert.equal(button(own, 'Définir des conditions'), undefined)
  } finally {
    own.app.unmount()
  }
  const f = fixture()
  try {
    await flush()
    button(f, 'Enregistrer un paiement').props.onClick()
    await flush()
    const inputs = all(f.root).filter((n) => n.tag === 'input')
    inputs.find((n) => n.props.type === 'number').props['onUpdate:modelValue']('25.00')
    inputs.find((n) => n.props.maxlength === '150').props['onUpdate:modelValue']('VIR-TEST')
    await flush()
    const form = all(f.root).find(
      (n) =>
        n.tag === 'form' && all(n).some((x) => x.tag === 'input' && x.props.maxlength === '150'),
    )
    await form.props.onSubmit({ preventDefault() {} })
    await flush()
    assert.equal(f.writes[0].path, 'payroll/21/payments/')
    assert.equal(f.writes[0].body.revision, 3)
    assert.equal(f.writes[0].body.amount_cad, '25.00')
    assert.match(f.writes[0].body.request_id, /^[0-9a-f-]{36}$/)
    assert.match(text(f.root), /Aucun virement effectué/)
  } finally {
    f.app.unmount()
  }
})
test('stale payroll save keeps the draft and does not announce a recorded payment', async () => {
  const f = fixture({ fail: true })
  try {
    await flush()
    button(f, 'Enregistrer un paiement').props.onClick()
    await flush()
    const input = all(f.root).find((n) => n.tag === 'input' && n.props.type === 'number')
    input.props['onUpdate:modelValue']('25.00')
    await flush()
    const form = all(f.root).find((n) => n.tag === 'form' && all(n).includes(input))
    await form.props.onSubmit({ preventDefault() {} })
    await flush()
    assert.match(text(f.root), /Solde modifié/)
    assert.ok(button(f, 'Confirmer l’enregistrement'))
    assert.doesNotMatch(text(f.root), /Paiement enregistré dans le registre/)
  } finally {
    f.app.unmount()
  }
})
