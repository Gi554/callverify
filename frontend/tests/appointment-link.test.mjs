import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'

const code = ts.transpileModule(
  readFileSync(new URL('../src/appointment-link.ts', import.meta.url), 'utf8'),
  {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  },
).outputText
const { appointmentLink } = await import(
  'data:text/javascript;base64,' + Buffer.from(code).toString('base64')
)

test('reminder link accepts only an exact positive safe identifier in Assurance', () => {
  assert.equal(
    appointmentLink(new URL('https://orvia-crm.com/crm?workspace=assurance&appointment=42')),
    42,
  )
  for (const value of ['', '0', '-1', '1.5', '1e3', '42/other', '9007199254740992']) {
    assert.equal(
      appointmentLink(
        new URL(
          `https://orvia-crm.com/crm?workspace=assurance&appointment=${encodeURIComponent(value)}`,
        ),
      ),
      null,
    )
  }
  assert.equal(
    appointmentLink(new URL('https://orvia-crm.com/crm?workspace=isolation&appointment=42')),
    null,
  )
})
