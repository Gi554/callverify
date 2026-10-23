import { readFileSync } from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'
import ts from 'typescript'

const { loadQuotas, quotaText } = await import(
  'data:text/javascript;base64,' +
    Buffer.from(
      ts.transpileModule(
        readFileSync(new URL('../src/advisor-quota.ts', import.meta.url), 'utf8'),
        {
          compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
        },
      ).outputText,
    ).toString('base64')
)

test('the countdown subtracts booked appointments from each quota', async () => {
  const calls = []
  const quotas = await loadQuotas(
    async (path) => {
      calls.push(path)
      return {
        results: [
          { id: 1, name: 'a', quota: 10 },
          { id: 2, name: 'b', quota: 3 },
          { id: 3, name: 'c', quota: null },
        ],
      }
    },
    async (path) => {
      calls.push(path)
      return {
        results: [
          { advisor_id: 1, booked: 4 },
          { advisor_id: 2, booked: 5 },
        ],
      }
    },
  )
  assert.deepEqual(calls, ['assurance/advisor-quotas/', 'advisor-usage/'])
  assert.deepEqual(quotas.get(1), { id: 1, name: 'a', quota: 10, booked: 4, remaining: 6 })
  assert.equal(quotas.get(2).remaining, 0)
  assert.equal(quotas.get(3).remaining, null)
  assert.equal(quotaText(quotas.get(1)), '6 prospect(s) restant(s)')
  assert.equal(quotaText(quotas.get(2)), 'Quota atteint')
  assert.equal(quotaText(quotas.get(3)), '')
  assert.equal(quotaText(undefined), '')
})
