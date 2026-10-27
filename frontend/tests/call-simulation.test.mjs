import { readFileSync } from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'
import ts from 'typescript'
const source = readFileSync(new URL('../src/call-simulation.ts', import.meta.url), 'utf8')
const code = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
}).outputText
const { createCallSimulation } = await import(
  'data:text/javascript;base64,' + Buffer.from(code).toString('base64')
)

test('call preview uses isolated memory for commands, outcomes, recalls and appointments', async (t) => {
  let network = 0
  t.mock.method(globalThis, 'fetch', () => {
    network++
    throw new Error('Network forbidden')
  })
  const demo = createCallSimulation()
  const path = `contacts/${demo.contact.id}/`
  const options = await demo.portal('assurance/calls/options/')
  assert.equal(options.enabled, true)
  const intent = await demo.request(path + 'call-intent/', { request_id: 'synthetic' })
  const command = await demo.portal('assurance/calls/', intent)
  assert.equal(command.state, 'accepted')
  assert.equal(demo.callCount(), 1)
  await demo.request(path + 'call-outcomes/', {
    result: 'callback',
    note: 'Rappel fictif',
    due_at: '2026-10-29T10:00:00-04:00',
  })
  assert.equal((await demo.request(path + 'follow-ups/')).count, 1)
  await demo.request('appointments/', {
    starts_at: '2026-10-30T10:00:00-04:00',
    ends_at: '2026-10-30T10:30:00-04:00',
    timezone: 'America/Toronto',
  })
  assert.equal((await demo.request('appointments/')).count, 1)
  const second = createCallSimulation()
  assert.notEqual(demo.contact.id, second.contact.id)
  assert.equal((await second.request('appointments/')).count, 0)
  assert.equal(second.callCount(), 0)
  await assert.rejects(demo.request('unsupported/'), /Aucun appel réseau/)
  await assert.rejects(
    demo.portal('assurance/calls/', { proof: 'real-proof' }),
    /aucun appel réseau/,
  )
  assert.equal(network, 0)
})

test('editor lease, qualification and coordinate writes stay in the synthetic instance', async () => {
  const demo = createCallSimulation()
  const path = `contacts/${demo.contact.id}/`
  const lease = await demo.request(path + 'lease/', {})
  assert.equal(lease.token, 'simulation-only')
  const original = await demo.request(path + 'qualification/')
  assert.ok(original.fields.length >= 10)
  const saved = await demo.request(path + 'qualification/', {
    qualification: { ...original.qualification, age: 42 },
  })
  assert.equal(saved.contact_revision, 1)
  assert.equal((await demo.request(path + 'qualification/')).qualification.age, 42)
  const changed = await demo.request(
    path,
    { name: 'Essai', phone: '+10000000001', email: 'test@example.invalid' },
    'PATCH',
  )
  assert.equal(changed.name, 'Essai')
  assert.ok(changed.revision > 0)
  assert.equal(await demo.request(path + 'lease/', { token: lease.token }, 'DELETE'), null)
})
