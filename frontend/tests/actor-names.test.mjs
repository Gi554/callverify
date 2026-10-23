import { readFileSync } from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'
import ts from 'typescript'
const { actorNames } = await import(
  'data:text/javascript;base64,' +
    Buffer.from(
      ts.transpileModule(readFileSync(new URL('../src/actor-names.ts', import.meta.url), 'utf8'), {
        compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
      }).outputText,
    ).toString('base64')
)
test('audit identity lookup is bounded and ignores unexpected accounts', async () => {
  const calls = []
  const portal = async (path) => {
    calls.push(path)
    return {
      results: [
        { id: 21, name: 'Synthetic Setter' },
        { id: 999, name: 'Foreign' },
      ],
    }
  }
  assert.deepEqual(await actorNames(portal, 'assurance', [21, 21, 0, NaN]), {
    21: 'Synthetic Setter',
  })
  assert.deepEqual(calls, ['assurance/actor-names/?ids=21'])
  await actorNames(
    portal,
    'isolation',
    Array.from({ length: 30 }, (_, i) => i + 1),
  )
  assert.equal(calls.at(-1).split('ids=')[1].split(',').length, 25)
})
test('missing identities or denied lookup leave the stable numeric reference available', async () => {
  assert.deepEqual(await actorNames(undefined, 'assurance', [21]), {})
  assert.deepEqual(
    await actorNames(
      async () => {
        throw Error('denied')
      },
      'assurance',
      [21],
    ),
    {},
  )
  let called = false
  assert.deepEqual(
    await actorNames(
      async () => {
        called = true
      },
      'assurance',
      [],
    ),
    {},
  )
  assert.equal(called, false)
})
