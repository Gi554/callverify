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
let code = compileScript(
  parse(readFileSync(new URL('../src/AssuranceCompensation.vue', import.meta.url), 'utf8'))
    .descriptor,
  {
    id: 'advisor-detail',
    inlineTemplate: true,
    templateOptions: { compilerOptions: { hoistStatic: false } },
  },
).content
code = code
  .replace(/import \{([^}]+)\} from 'lucide-vue-next'/g, (_, names) =>
    names
      .split(',')
      .filter((n) => n.trim())
      .map((n) => `const ${n.trim()}={render:()=>null}`)
      .join(';'),
  )
  .replace(/from ['"]vue['"]/g, `from '${vue}'`)
  .replace(
    /import (\w+) from ['"]\.\/[^'"]+\.vue['"]/g,
    (_, name) =>
      `const ${name}={props:['open','title','eyebrow','closeDisabled'],emits:['requestClose'],render(){return this.open ? this.$slots.default?.():null}}`,
  )
for (const directive of ['vModelText', 'vModelSelect', 'vModelRadio', 'vModelCheckbox'])
  code =
    code.replace(new RegExp(directive + ' as _' + directive + ',?', 'g'), '') +
    `;const _${directive}={};`
const component = (await import(url(code))).default
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

function fixture({ callFailure = false, exportPages = false } = {}) {
  const root = { children: [] },
    calls = []
  const row = {
    setter_id: 21,
    setter_name: 'Setter A',
    booked: 3,
    transmitted: 3,
    upcoming: 0,
    attended: 2,
    absent: 1,
    payable: 2,
    unpriced: 1,
    amount_cad: '12.50',
    rate_cad: '12.50',
    rate_revision: 4,
  }
  const data = {
    from: '2026-10-26',
    to: '2026-11-01',
    count: exportPages ? 2 : 1,
    next: exportPages ? 'next' : null,
    previous: null,
    totals: { payable: 2, unpriced: 1, amount_cad: '12.50' },
    results: [row],
    definition: 'Présences uniquement',
  }
  const app = renderer.createApp(component, {
    request: async (path, body) => {
      calls.push({ path, body })
      if (body) return path.endsWith('/value/') ? { valued: 1 } : { recorded: true }
      if (path.includes('/details/'))
        return {
          count: 1,
          results: [
            {
              id: 42,
              starts_at: '2026-11-01T15:30:00Z',
              advisor_name: 'Conseiller',
              performed: true,
              payable: true,
              unit_rate_cad: '12.50',
              amount_cad: '12.50',
            },
          ],
        }
      if (path.endsWith('page=2'))
        return { ...data, results: [{ ...row, setter_id: 22, setter_name: '=danger' }] }
      return structuredClone(data)
    },
    portal: async (path) => {
      calls.push({ path })
      if (callFailure) throw new Error('Service indisponible')
      return {
        results: [{ user_id: 21, calls: 7 }],
        totals: { calls: 7 },
        definition: 'Poste joint',
      }
    },
  })
  app.mount(root)
  return { root, calls, close: () => app.unmount() }
}
const button = (f, label) => all(f.root).find((n) => n.tag === 'button' && text(n).includes(label))
const update = (node, value) => node.props['onUpdate:modelValue'](value)

test('weekly attendance metrics and explicit CAD rate are visible; missing call service stays unknown', async () => {
  const f = fixture({ callFailure: true })
  try {
    await flush()
    assert.match(text(f.root), /Setter A/)
    assert.match(text(f.root), /Appels indisponibles/)
    assert.match(text(f.root), /—/)
    assert.match(text(f.root), /Présences à valoriser/)
    assert.match(text(f.root), /12,50/)
  } finally {
    f.close()
  }
})

test('rate editor sends decimal string, revision and reason', async () => {
  const f = fixture()
  try {
    await flush()
    button(f, 'Tarif / valoriser').props.onClick()
    await flush()
    const amount = all(f.root).find((n) => n.tag === 'input' && n.props.type === 'number')
    update(amount, '18.25')
    update(
      all(f.root).find((n) => n.tag === 'textarea'),
      'Tarif convenu',
    )
    await flush()
    const form = all(f.root).find((n) => n.tag === 'form' && n.props.class === 'rate-form')
    await form.props.onSubmit({ preventDefault() {} })
    await flush()
    assert.deepEqual(f.calls.find((c) => c.path === 'compensation/21/rate/').body, {
      amount_cad: '18.25',
      revision: 4,
      reason: 'Tarif convenu',
    })
    assert.match(text(f.root), /Les montants déjà valorisés sont conservés/)
  } finally {
    f.close()
  }
})

test('valuation uses the applied period rather than unsubmitted date edits and confirms the saved tariff', async () => {
  globalThis.window = { confirm: () => true }
  const f = fixture()
  try {
    await flush()
    update(
      all(f.root).find((n) => n.tag === 'input' && n.props.type === 'date'),
      '2026-09-01',
    )
    button(f, 'Tarif / valoriser').props.onClick()
    await flush()
    update(
      all(f.root).find((n) => n.tag === 'textarea'),
      'Validation période',
    )
    await flush()
    const b = button(f, 'Valoriser au tarif enregistré')
    assert.equal(b.props.disabled, false)
    await b.props.onClick()
    await flush()
    assert.deepEqual(f.calls.find((c) => c.path === 'compensation/21/value/').body, {
      starts_on: '2026-10-26',
      ends_on: '2026-11-01',
      rate_revision: 4,
      reason: 'Validation période',
    })
  } finally {
    f.close()
    delete globalThis.window
  }
})

test('details use Québec date rendering and CSV includes all pages with formula escaping', async () => {
  const f = fixture({ exportPages: true })
  let csv
  const oldCreate = URL.createObjectURL,
    oldRevoke = URL.revokeObjectURL
  URL.createObjectURL = (blob) => {
    csv = blob
    return 'blob:test'
  }
  URL.revokeObjectURL = () => {}
  globalThis.document = { createElement: () => ({ click() {} }) }
  try {
    await flush()
    await button(f, 'Détail').props.onClick()
    await flush()
    assert.match(text(f.root), /10[ h:]+30/)
    await button(f, 'Exporter CSV').props.onClick()
    await flush()
    assert.match(await csv.text(), /'=danger/)
    assert.ok(f.calls.some((c) => c.path.endsWith('page=2')))
  } finally {
    f.close()
    URL.createObjectURL = oldCreate
    URL.revokeObjectURL = oldRevoke
    delete globalThis.document
  }
})
