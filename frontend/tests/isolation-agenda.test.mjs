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
  parse(readFileSync(new URL('../src/IsolationAgenda.vue', import.meta.url), 'utf8')).descriptor,
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

function fixture({ role = 'client', fail = false } = {}) {
  const root = { children: [] },
    requests = []
  const value = {
    enabled: true,
    revision: 3,
    timezone: 'America/Toronto',
    windows: [{ weekday: 0, start: '09:00', end: '17:00' }],
  }
  const app = renderer.createApp(component, {
    role,
    portal: async () => ({}),
    request: async (path, body) => {
      requests.push({ path, body })
      if (body && fail) throw new Error('Horaires modifiés : rechargez')
      return body ? { ...body, timezone: value.timezone, revision: 4 } : structuredClone(value)
    },
  })
  app.mount(root)
  return { root, requests, close: () => app.unmount() }
}
const button = (f, label) => all(f.root).find((n) => n.tag === 'button' && text(n).includes(label))

test('client hours are visible in Québec and editing sends a versioned weekly policy', async () => {
  const f = fixture()
  try {
    await flush()
    assert.match(text(f.root), /09:00 – 17:00/)
    assert.match(text(f.root), /heure du Québec/)
    button(f, 'Modifier mes horaires').props.onClick()
    await flush()
    const times = all(f.root).filter((n) => n.tag === 'input' && n.props.type === 'time')
    times[0].props['onUpdate:modelValue']('10:00')
    await flush()
    await all(f.root)
      .find((n) => n.tag === 'form')
      .props.onSubmit({ preventDefault() {} })
    await flush()
    assert.deepEqual(f.requests.find((r) => r.body).body, {
      enabled: true,
      revision: 3,
      windows: [{ weekday: 0, start: '10:00', end: '17:00' }],
    })
    assert.match(text(f.root), /Horaires enregistrés/)
  } finally {
    f.close()
  }
})

test('a conflicting hours save retains the form and reports failure', async () => {
  const f = fixture({ fail: true })
  try {
    await flush()
    button(f, 'Modifier mes horaires').props.onClick()
    await flush()
    await all(f.root)
      .find((n) => n.tag === 'form')
      .props.onSubmit({ preventDefault() {} })
    await flush()
    assert.ok(all(f.root).some((n) => n.tag === 'form'))
    assert.match(text(f.root), /Horaires modifiés : rechargez/)
  } finally {
    f.close()
  }
})

test('only the client is offered the personal calendar connection', async () => {
  for (const role of ['client', 'administrator']) {
    const f = fixture({ role })
    try {
      await flush()
      assert.equal(!!button(f, 'Connexion de mon agenda'), role === 'client')
    } finally {
      f.close()
    }
  }
})
