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
const keys = url(readFileSync(new URL('../src/settings-key.ts', import.meta.url), 'utf8'))
const { keyFromLabel, uniqueKey } = await import(keys)
function compile(name) {
  let code = compileScript(
    parse(readFileSync(new URL(`../src/${name}.vue`, import.meta.url), 'utf8')).descriptor,
    {
      id: name,
      inlineTemplate: true,
      templateOptions: { compilerOptions: { hoistStatic: false } },
    },
  ).content
  code =
    code
      .replace(/import \{([^}]+)\} from 'lucide-vue-next'/g, (_, names) =>
        names
          .split(',')
          .filter((item) => item.trim())
          .map((item) => `const ${item.trim()}={render:()=>null}`)
          .join(';'),
      )
      .replace(/from ['"]vue['"]/g, `from '${vue}'`)
      .replace("'./settings-key'", JSON.stringify(keys))
      .replace(
        /import (\w+) from ['"]\.\/[^'"]+\.vue['"]/g,
        (_, component) => `const ${component}={render:()=>null}`,
      )
      .replace(/vModelText as _vModelText,?/g, '')
      .replace(/vModelSelect as _vModelSelect,?/g, '')
      .replace(/vModelCheckbox as _vModelCheckbox,?/g, '') +
    ';const _vModelText={},_vModelSelect={},_vModelCheckbox={};'
  return import(url(code)).then((module) => module.default)
}
const pipeline = await compile('AssurancePipelineSettings')
const fieldsComponent = await compile('AssuranceFieldSettings')
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
function mount(component, data) {
  const root = { children: [] },
    writes = []
  const app = renderer.createApp(component, {
    request: async (path, body) => {
      if (body) writes.push([path, body])
      return structuredClone(data)
    },
  })
  app.mount(root)
  return { root, writes, close: () => app.unmount() }
}
const button = (f, label) =>
  all(f.root).find(
    (n) => n.tag === 'button' && (text(n).trim() === label || n.props['aria-label'] === label),
  )
const type = (input, value) => {
  input.props.onInput?.({ target: { value } })
  input.props['onUpdate:modelValue'](value)
}

test('stable keys come from labels, without accents and without collisions', () => {
  assert.equal(keyFromLabel('Rendez-vous planifié', 'statut'), 'rendez_vous_planifie')
  assert.equal(keyFromLabel('2e relance', 'statut'), 'statut_2e_relance')
  assert.equal(keyFromLabel('  Échéance !  ', 'champ'), 'echeance')
  assert.match(keyFromLabel('x'.repeat(60), 'champ'), /^x{40}$/)
  assert.equal(uniqueKey('suivi', ['suivi', 'suivi_2']), 'suivi_3')
})

test('pipeline edits show a save bar and keep the same payload', async () => {
  const f = mount(pipeline, {
    revision: 4,
    stages: [
      { key: 'to_contact', label: 'À contacter', active: true },
      { key: 'won', label: 'Gagné', active: true },
    ],
  })
  try {
    await flush()
    assert.match(text(f.root), /Aucune modification/)
    assert.match(text(f.root), /to_contact/)
    button(f, 'Descendre À contacter').props.onClick()
    button(f, 'Ajouter un statut').props.onClick()
    await flush()
    const inputs = all(f.root).filter(
      (n) => n.tag === 'input' && n.props.placeholder === 'Libellé du statut',
    )
    type(inputs.at(-1), 'À relancer')
    await flush()
    assert.match(text(f.root), /Modifications non enregistrées/)
    assert.match(text(f.root), /a_relancer/)
    const reason = all(f.root).find((n) => n.props?.['aria-label'] === 'Motif de la modification')
    reason.props['onUpdate:modelValue']('Nouveau suivi')
    all(f.root)
      .find((n) => n.tag === 'form')
      .props.onSubmit({ preventDefault() {} })
    await flush()
    assert.deepEqual(f.writes[0], [
      'pipeline/',
      {
        revision: 4,
        reason: 'Nouveau suivi',
        stages: [
          { key: 'won', label: 'Gagné', active: true },
          { key: 'to_contact', label: 'À contacter', active: true },
          { key: 'a_relancer', label: 'À relancer', active: true },
        ],
      },
    ])
  } finally {
    f.close()
  }
})

test('custom fields sit in their own tab and new fields get a generated key', async () => {
  const f = mount(fieldsComponent, {
    revision: 2,
    fields: [
      {
        key: 'budget',
        label: 'Budget',
        type: 'text',
        required: false,
        active: true,
        advisor_visible: true,
        choices: [],
      },
    ],
  })
  try {
    await flush()
    assert.ok(all(f.root).some((n) => n.props?.role === 'tab' && n.props['aria-selected'] === true))
    assert.doesNotMatch(text(f.root), /Budget/)
    button(f, 'Champs personnalisés').props.onClick()
    await flush()
    assert.match(text(f.root), /budget/)
    button(f, 'Ajouter un champ').props.onClick()
    await flush()
    const inputs = all(f.root).filter(
      (n) => n.tag === 'input' && n.props.placeholder === 'Libellé du champ',
    )
    type(inputs.at(-1), 'Date de naissance')
    await flush()
    assert.match(text(f.root), /date_de_naissance/)
    const reason = all(f.root).find((n) => n.props?.['aria-label'] === 'Motif de la modification')
    reason.props['onUpdate:modelValue']('Ajout')
    all(f.root)
      .find((n) => n.tag === 'form')
      .props.onSubmit({ preventDefault() {} })
    await flush()
    assert.equal(f.writes[0][0], 'contact-fields/')
    assert.equal(f.writes[0][1].fields.at(-1).key, 'date_de_naissance')
    assert.deepEqual(f.writes[0][1].fields[0], {
      key: 'budget',
      label: 'Budget',
      type: 'text',
      required: false,
      active: true,
      advisor_visible: true,
      choices: [],
    })
  } finally {
    f.close()
  }
})
