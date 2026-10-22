import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'

const source = readFileSync(new URL('../src/entrypoint.ts', import.meta.url), 'utf8')
const code = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
const { crmEntryRedirect } = await import(
  'data:text/javascript;base64,' + Buffer.from(code).toString('base64')
)

test('root and every old standalone screen lead to the one central CRM', () => {
  for (const path of [
    '/',
    '/#/dashboard',
    '/#/campaigns',
    '/demo#/admins',
    '/demo#/settings',
    '/reset-password?uid=old&token=legacy',
    '/crm-other',
  ]) {
    assert.equal(crmEntryRedirect(new URL('http://localhost:5174' + path)), '/crm', path)
  }
})
test('central OAuth, invitation and recovery tokens survive entry normalization', () => {
  for (const path of [
    '/crm',
    '/crm/',
    '/crm/oauth/google?code=opaque&state=opaque',
    '/crm/oauth/microsoft?error=denied',
    '/crm#invite=id:token',
    '/crm#reset=id:token',
  ]) {
    assert.equal(crmEntryRedirect(new URL('http://localhost:5174' + path)), null, path)
  }
  for (const hash of ['#invite=id:token', '#reset=id:token']) {
    assert.equal(crmEntryRedirect(new URL('http://localhost:5174/' + hash)), '/crm' + hash)
  }
})
test('the application boot only mounts Portal with no legacy bundle entry', () => {
  const entry = readFileSync(new URL('../src/main.ts', import.meta.url), 'utf8')
  assert.match(entry, /createApp\(Portal\)/)
  assert.doesNotMatch(entry, /App\.vue|Workspace\.vue|isPortal/)
})
