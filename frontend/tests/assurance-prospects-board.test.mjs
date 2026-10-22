import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import test from 'node:test'
import assert from 'node:assert/strict'
import { parse, compileScript } from 'vue/compiler-sfc'
import { createRenderer, nextTick, h } from 'vue'
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
  parse(readFileSync(new URL('../src/AssuranceProspects.vue', import.meta.url), 'utf8')).descriptor,
  {
    id: 'assurance-prospects',
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
function fixture(role = 'administrator') {
  const root = { children: [] },
    requests = [],
    imported = []
  const request = async (path) => {
    requests.push(path)
    if (path === 'pipeline/')
      return {
        stages: [
          { key: 'new', label: 'Nouveau', active: true },
          { key: 'won', label: 'Gagné', active: true },
        ],
      }
    if (path.startsWith('contacts/?status=new'))
      return {
        count: 1,
        next: null,
        results: [
          {
            id: 11,
            name: 'Dossier Alpha',
            phone: '+15145550000',
            email: '',
            status: 'new',
            updated_at: '2026-10-20T12:00:00Z',
          },
        ],
      }
    return { count: 0, next: null, results: [] }
  }
  const app = renderer.createApp({
    render: () =>
      h(component, {
        role,
        request,
        portal: async () => ({}),
        onImported: (count) => imported.push(count),
      }),
  })
  app.mount(root)
  return { root, requests, imported, close: () => app.unmount() }
}
const button = (f, label) => all(f.root).find((n) => n.tag === 'button' && text(n) === label)
const component_ = (f, name) => all(f.root).find((n) => n.props?.['data-component'] === name)
const callButtons = (f) =>
  all(f.root).filter((n) => String(n.props?.['aria-label'] || '').startsWith('Préparer l’appel'))

test('administrator sees the team board without call commands', async () => {
  const f = fixture()
  try {
    await flush()
    assert.match(text(f.root), /ÉQUIPE ASSURANCE/)
    assert.match(text(f.root), /Tous les prospects de l’équipe/)
    assert.match(text(f.root), /Dossier Alpha/)
    assert.equal(callButtons(f).length, 0)
    assert.ok(all(f.root).some((n) => /Modifier le numéro/.test(n.props?.['aria-label'] || '')))
    assert.equal(component_(f, 'AssuranceContacts'), undefined)
  } finally {
    f.close()
  }
})

test('administrator switches to the list with imports and back to a refreshed board', async () => {
  const f = fixture()
  try {
    await flush()
    button(f, 'Liste et imports').props.onClick()
    await flush()
    const list = component_(f, 'AssuranceContacts')
    assert.ok(list)
    assert.doesNotMatch(text(f.root), /Dossier Alpha/)
    assert.equal(button(f, 'Actualiser'), undefined)
    list.props.onImported(42)
    assert.deepEqual(f.imported, [42])
    const before = f.requests.filter((path) => path === 'pipeline/').length
    button(f, 'Tableau').props.onClick()
    await flush()
    assert.equal(f.requests.filter((path) => path === 'pipeline/').length, before + 1)
    assert.match(text(f.root), /Dossier Alpha/)
  } finally {
    f.close()
  }
})

test('setter keeps call commands and has no list switch', async () => {
  const f = fixture('setter')
  try {
    await flush()
    assert.match(text(f.root), /MON ESPACE ASSURANCE/)
    assert.equal(callButtons(f).length, 1)
    assert.equal(button(f, 'Liste et imports'), undefined)
  } finally {
    f.close()
  }
})
