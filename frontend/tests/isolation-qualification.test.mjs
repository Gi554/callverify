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
  parse(readFileSync(new URL('../src/IsolationQualification.vue', import.meta.url), 'utf8'))
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
function fixture({ fail = false, importPreview = false } = {}) {
  const root = { children: [] },
    requests = [],
    downloads = [],
    confirmations = []
  const blob = new Blob(['synthetic workbook'])
  const originalCreate = URL.createObjectURL,
    originalRevoke = URL.revokeObjectURL
  URL.createObjectURL = (value) => {
    assert.equal(value, blob)
    return 'blob:synthetic'
  }
  URL.revokeObjectURL = () => {}
  globalThis.document = {
    activeElement: null,
    body: { appendChild() {} },
    createElement() {
      return {
        click() {
          downloads.push({ href: this.href, name: this.download })
        },
        remove() {},
      }
    },
  }
  const app = renderer.createApp(component, {
    request: async (path, body) => {
      requests.push(path)
      if (importPreview && path === 'qualification/') {
        return {
          results: [{ id: 7, name: 'Liste test', progress: { checked: 0, total: 0, percent: 0 } }],
        }
      }
      if (importPreview && path === 'qualification/imports/' && body instanceof FormData) {
        return {
          id: 12,
          rows: 1,
          headers: ['Phone', 'Address', 'Delivery', 'Custom ZIP'],
          suggested_mapping: { phone: 'Phone', address: 'Address' },
          preview: [
            {
              Phone: '5145550123',
              Address: 'Adresse proposée',
              Delivery: 'Adresse choisie',
              'Custom ZIP': 'H2X 1Y4',
            },
          ],
        }
      }
      if (path.endsWith('/confirm/')) confirmations.push(body)
      if (path.endsWith('/download/')) {
        if (fail) throw new Error('Accès retiré')
        return blob
      }
      return {
        results:
          path === 'qualification/exports/'
            ? [{ id: 9, campaign: 7, format: 'xlsx', status: 'completed' }]
            : [],
      }
    },
  })
  app.mount(root)
  return {
    root,
    requests,
    downloads,
    confirmations,
    close() {
      app.unmount()
      URL.createObjectURL = originalCreate
      URL.revokeObjectURL = originalRevoke
    },
  }
}
async function click(f, label) {
  const button = all(f.root).find((n) => n.tag === 'button' && text(n).trim() === label)
  assert.ok(button, label)
  await button.props.onClick()
  await flush()
}
test('export download goes through the authorized CRM request, not a public file link', async () => {
  const f = fixture()
  try {
    await flush()
    await click(f, 'Exports')
    assert.equal(
      all(f.root).some((n) => n.tag === 'a'),
      false,
    )
    await click(f, 'Télécharger')
    assert.ok(f.requests.includes('qualification/exports/9/download/'))
    assert.deepEqual(f.downloads, [
      { href: 'blob:synthetic', name: 'qualification-isolation-9.xlsx' },
    ])
  } finally {
    f.close()
  }
})
test('revoked export access displays the failure without downloading', async () => {
  const f = fixture({ fail: true })
  try {
    await flush()
    await click(f, 'Exports')
    await click(f, 'Télécharger')
    assert.equal(f.downloads.length, 0)
    assert.ok(all(f.root).some((n) => n.props?.role === 'alert' && text(n) === 'Accès retiré'))
  } finally {
    f.close()
  }
})

test('import preview and confirmation follow manually chosen columns instead of suggestions', async () => {
  const f = fixture({ importPreview: true })
  try {
    await flush()
    await click(f, 'Importer')
    const input = all(f.root).find((n) => n.tag === 'input' && n.props.type === 'file')
    input.props.onChange({ target: { files: [new File(['synthetic'], 'import.csv')] } })
    const submit = async () => {
      const form = all(f.root).find(
        (n) => n.tag === 'form' && text(n).includes('Importer une liste'),
      )
      await form.props.onSubmit({ preventDefault() {} })
      await flush()
    }
    await submit()
    assert.ok(text(f.root).includes('Adresse proposée'))
    const setColumn = (label, column) => {
      const element = all(f.root).find((n) => n.tag === 'label' && text(n).trim().startsWith(label))
      const select = all(element).find((n) => n.tag === 'select')
      select.props['onUpdate:modelValue'](column)
      select.props.onChange()
    }
    setColumn('Adresse complète', 'Delivery')
    setColumn('Code postal', 'Custom ZIP')
    await flush()
    assert.ok(text(f.root).includes('Adresse choisie'))
    assert.equal(text(f.root).includes('Adresse proposée'), false)
    await submit()
    assert.equal(f.confirmations.length, 1)
    assert.equal(f.confirmations[0].mapping.address, 'Delivery')
    assert.equal(f.confirmations[0].mapping.postal_code, 'Custom ZIP')
    assert.equal(f.confirmations[0].mapping.city, '')
  } finally {
    f.close()
  }
})
