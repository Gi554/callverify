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
  parse(readFileSync(new URL('../src/PortalAccess.vue', import.meta.url), 'utf8')).descriptor,
  {
    id: 'activity',
    inlineTemplate: true,
    templateOptions: { compilerOptions: { hoistStatic: false } },
  },
).content
code = code.replace(
  /import (Portal\w+) from ['"]\.\/[^'"]+\.vue['"]/g,
  (_, name) => `const ${name}={render:()=>null}`,
)
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
code = code.replace(
  /import \{ actorNames \} from ['"]\.\/actor-names['"]/g,
  `const actorNames=async(portal,workspace,ids)=>portal?Object.fromEntries((await portal(workspace+'/actor-names/?ids='+ids.join(','))).results.map(row=>[row.id,row.name])):{}`,
)
code =
  withStatComponents(code)
    .replace(/vModelText as _vModelText,?/g, '')
    .replace(/vModelSelect as _vModelSelect,?/g, '')
    .replace(/vModelCheckbox as _vModelCheckbox,?/g, '') +
  ';const _vModelText={},_vModelSelect={},_vModelCheckbox={};'
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
function fixture({ fail = false } = {}) {
  const root = { children: [] },
    writes = []
  let removed = false
  const members = [
    {
      id: 1,
      username: 'admin',
      role: 'administrator',
      active: true,
      account_active: true,
      can_delete: false,
    },
    {
      id: 2,
      username: 'setter',
      role: 'setter',
      active: true,
      account_active: true,
      can_delete: true,
    },
    {
      id: 3,
      username: 'other-admin',
      role: 'setter',
      active: false,
      account_active: true,
      can_delete: false,
    },
  ]
  const app = renderer.createApp(component, {
    spaces: ['assurance'],
    username: 'admin',
    request: async (path, body, method) => {
      if (method === 'DELETE') {
        writes.push({ path, body, method })
        if (fail) throw new Error('Compte devenu administrateur')
        removed = true
        return { deleted: true, account_disabled: true }
      }
      return {
        count: removed ? 2 : 3,
        results: members.filter((m) => !removed || m.id !== 2).map((m) => ({ ...m })),
      }
    },
  })
  app.mount(root)
  return { root, app, writes }
}
test('deletion is separate from suspension and requires exact confirmation before DELETE', async () => {
  const f = fixture()
  try {
    await flush()
    const deletes = all(f.root).filter((n) => n.tag === 'button' && text(n).trim() === 'Supprimer')
    assert.equal(deletes.length, 1)
    assert.ok(button(f, 'Suspendre'))
    deletes[0].props.onClick()
    await flush()
    assert.equal(button(f, 'Confirmer la suppression').props.disabled, true)
    const inputs = all(f.root).filter((n) => n.tag === 'input')
    inputs.find((n) => n.props.autocomplete === 'off').props['onUpdate:modelValue']('setter')
    all(f.root)
      .find((n) => n.tag === 'textarea')
      .props['onUpdate:modelValue']('Départ')
    await flush()
    assert.equal(button(f, 'Confirmer la suppression').props.disabled, false)
    const form = all(f.root).find(
      (n) => n.tag === 'form' && all(n).some((x) => x.tag === 'textarea'),
    )
    await form.props.onSubmit({ preventDefault() {} })
    await flush()
    assert.equal(f.writes[0].path, 'workspaces/assurance/users/2/')
    assert.equal(f.writes[0].method, 'DELETE')
    assert.equal(f.writes[0].body.confirm_username, 'setter')
    assert.match(text(f.root), /Historique conservé/)
  } finally {
    f.app.unmount()
  }
})
test('server refusal keeps deletion confirmation open without reporting success', async () => {
  const f = fixture({ fail: true })
  try {
    await flush()
    button(f, 'Supprimer').props.onClick()
    await flush()
    const form = all(f.root).find(
      (n) => n.tag === 'form' && all(n).some((x) => x.tag === 'textarea'),
    )
    await form.props.onSubmit({ preventDefault() {} })
    await flush()
    assert.match(text(f.root), /Compte devenu administrateur/)
    assert.ok(button(f, 'Confirmer la suppression'))
    assert.doesNotMatch(text(f.root), /connexion désactivée/)
  } finally {
    f.app.unmount()
  }
})
