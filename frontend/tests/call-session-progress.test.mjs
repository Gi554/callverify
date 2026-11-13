import { readFileSync } from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'
import ts from 'typescript'

const source = readFileSync(new URL('../src/call-session-progress.ts', import.meta.url), 'utf8')
const code = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
}).outputText
const url = 'data:text/javascript;base64,' + Buffer.from(code).toString('base64')
const { callSessionKey, clearCallSession, quebecDay, readCallSession, writeCallSession } =
  await import(url)

function storage() {
  const values = new Map()
  return {
    values,
    getItem: (key) => values.get(key) || null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  }
}

test('session checkpoint stays scoped to its user and workspace', () => {
  assert.notEqual(
    callSessionKey('assurance', 'setter@example.com'),
    callSessionKey('isolation', 'setter@example.com'),
  )
  assert.notEqual(
    callSessionKey('assurance', 'one@example.com'),
    callSessionKey('assurance', 'two@example.com'),
  )
})

test('session checkpoint restores completed prospects for the same Quebec day', () => {
  const store = storage()
  const key = callSessionKey('isolation', 'setter@example.com')
  const progress = { day: '2026-11-13', active: true, visited: [7, 12, 7] }
  writeCallSession(store, key, progress)
  assert.deepEqual(readCallSession(store, key, '2026-11-13'), {
    day: '2026-11-13',
    active: true,
    visited: [7, 12],
  })
})

test('checkpoint expires at the next Quebec day and explicit end clears it', () => {
  const store = storage()
  const key = callSessionKey('assurance', 'setter@example.com')
  writeCallSession(store, key, { day: '2026-11-13', active: true, visited: [7] })
  assert.equal(readCallSession(store, key, '2026-11-14'), null)
  assert.equal(store.values.has(key), false)
  writeCallSession(store, key, { day: '2026-11-14', active: true, visited: [8] })
  clearCallSession(store, key)
  assert.equal(readCallSession(store, key, '2026-11-14'), null)
})

test('Quebec day boundary follows America/Toronto rather than UTC', () => {
  assert.equal(quebecDay(new Date('2026-11-14T04:30:00Z')), '2026-11-13')
  assert.equal(quebecDay(new Date('2026-11-14T06:30:00Z')), '2026-11-14')
})
