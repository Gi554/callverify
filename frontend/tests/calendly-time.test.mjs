import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
const javascript = ts.transpileModule(
  readFileSync(new URL('../src/calendly-time.ts', import.meta.url), 'utf8'),
  { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } },
).outputText
const { montrealISO } = await import(
  'data:text/javascript;base64,' + Buffer.from(javascript).toString('base64')
)
test('Montréal preserves exact provider instants across spring and repeated autumn hours', () => {
  const cases = [
    ['2026-01-15T15:00:00Z', '2026-01-15T10:00:00-05:00'],
    ['2026-07-15T14:00:00Z', '2026-07-15T10:00:00-04:00'],
    ['2026-03-08T06:30:00Z', '2026-03-08T01:30:00-05:00'],
    ['2026-03-08T07:30:00Z', '2026-03-08T03:30:00-04:00'],
    ['2026-11-01T05:30:00Z', '2026-11-01T01:30:00-04:00'],
    ['2026-11-01T06:30:00Z', '2026-11-01T01:30:00-05:00'],
  ]
  for (const [source, expected] of cases) {
    assert.equal(montrealISO(source), expected)
    assert.equal(Date.parse(montrealISO(source)), Date.parse(source))
  }
})
