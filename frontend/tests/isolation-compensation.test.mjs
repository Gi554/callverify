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
  parse(readFileSync(new URL('../src/IsolationCompensation.vue', import.meta.url), 'utf8'))
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

function fixture({ unavailable = false, conflict = false } = {}) {
  const root = { children: [] },
    calls = []
  const row = {
    setter_id: 21,
    setter_name: 'Setter A',
    client_id: 72,
    client_name: 'Client',
    calls: unavailable ? null : 5,
    attendance_credits: 1,
    sale_credits: 1,
    attendance_unpriced: 0,
    sale_unpriced: 0,
    attendance_amount: '12.50',
    sale_amount: '40.00',
    amount_cad: '52.50',
    complete: true,
  }
  const data = {
    from: '2026-10-26',
    to: '2026-11-01',
    calls_available: !unavailable,
    totals: row,
    groups: { count: 1, results: [row] },
    definition: 'Un crédit par processus',
  }
  const app = renderer.createApp(component, {
    portal: async (path, body) => {
      calls.push({ path, body, service: 'portal' })
      if (path.startsWith('isolation/setters/'))
        return { results: [{ id: 21, name: 'Setter A' }], count: 1 }
      return {
        proof: 'signed-rate',
        setter: { id: 21, name: 'Setter A' },
        client: { id: 72, name: 'Client' },
      }
    },
    request: async (path, body) => {
      calls.push({ path, body, service: 'core' })
      if (body) {
        if (conflict && path.endsWith('/rates/')) throw new Error('Tarif modifié : rechargez')
        return { valued: 1, remaining: 0 }
      }
      if (path.startsWith('isolation-compensation/rates/'))
        return {
          results: [{ attendance_cad: '12.50', sale_bonus_cad: '40.00', revision: 3 }],
          count: 1,
        }
      return structuredClone(data)
    },
  })
  app.mount(root)
  return { root, calls, close: () => app.unmount() }
}
const button = (f, label) => all(f.root).find((n) => n.tag === 'button' && text(n).trim() === label)
const update = (node, value) => node.props['onUpdate:modelValue'](value)
const editor = (f) =>
  all(f.root).find((n) => n.tag === 'form' && all(n).some((child) => child.tag === 'textarea'))

test('Isolation report distinguishes CAD credits and keeps unavailable calls unknown', async () => {
  const f = fixture({ unavailable: true })
  try {
    await flush()
    assert.match(text(f.root), /Setter A/)
    assert.match(text(f.root), /52,50/)
    assert.match(text(f.root), /momentanément indisponibles/)
    assert.match(text(f.root), /—/)
    assert.match(text(f.root), /Présences rémunérables uniques/)
  } finally {
    f.close()
  }
})

test('two CAD rates are saved with a fresh bound proof, revision and mandatory reason', async () => {
  const f = fixture()
  try {
    await flush()
    await button(f, 'Tarifs').props.onClick()
    await flush()
    const inputs = all(f.root).filter((n) => n.tag === 'input' && n.props.type === 'number')
    update(inputs[0], '18.25')
    update(inputs[1], '60.50')
    update(
      all(f.root).find((n) => n.tag === 'textarea'),
      'Tarifs convenus',
    )
    await flush()
    await editor(f).props.onSubmit({ preventDefault() {} })
    await flush()
    assert.deepEqual(
      f.calls.find((c) => c.service === 'core' && c.path === 'isolation-compensation/rates/').body,
      {
        proof: 'signed-rate',
        attendance_cad: '18.25',
        sale_bonus_cad: '60.50',
        revision: 3,
        reason: 'Tarifs convenus',
      },
    )
    assert.equal(f.calls.filter((c) => c.path === 'isolation/compensation-proof/').length, 2)
    assert.match(text(f.root), /montants déjà valorisés sont conservés/)
  } finally {
    f.close()
  }
})

test('a stale rate retains the draft and valuation uses the applied Québec period', async () => {
  const failed = fixture({ conflict: true })
  try {
    await flush()
    await button(failed, 'Tarifs').props.onClick()
    await flush()
    update(
      all(failed.root).find((n) => n.tag === 'textarea'),
      'Modification',
    )
    await flush()
    await editor(failed).props.onSubmit({ preventDefault() {} })
    await flush()
    assert.match(text(failed.root), /Tarif modifié/)
    assert.ok(editor(failed))
  } finally {
    failed.close()
  }
  const f = fixture()
  try {
    await flush()
    await button(f, 'Valoriser les résultats sans tarif').props.onClick()
    await flush()
    update(
      all(f.root).find((n) => n.tag === 'textarea'),
      'Compléter les tarifs manquants',
    )
    await flush()
    await editor(f).props.onSubmit({ preventDefault() {} })
    await flush()
    assert.deepEqual(f.calls.find((c) => c.path === 'isolation-compensation/value/').body, {
      proof: 'signed-rate',
      rate_revision: 3,
      starts_on: '2026-10-26',
      ends_on: '2026-11-01',
      reason: 'Compléter les tarifs manquants',
    })
    assert.match(text(f.root), /1 résultat\(s\) valorisé/)
  } finally {
    f.close()
  }
})
