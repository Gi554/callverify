// Compiles the real dashboard pieces so statistics harnesses render their figures.
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import { parse, compileScript } from 'vue/compiler-sfc'
import ts from 'typescript'

const require = createRequire(import.meta.url)
const vue = pathToFileURL(require.resolve('vue')).href
const names = ['StatKpi', 'StatDonut', 'StatBars']

function compile(name) {
  const code = compileScript(
    parse(readFileSync(new URL(`../src/${name}.vue`, import.meta.url), 'utf8')).descriptor,
    {
      id: name,
      inlineTemplate: true,
      templateOptions: { compilerOptions: { hoistStatic: false } },
    },
  ).content.replace(/from ['"]vue['"]/g, `from '${vue}'`)
  return (
    'data:text/javascript;base64,' +
    Buffer.from(
      ts.transpileModule(code, {
        compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
      }).outputText,
    ).toString('base64')
  )
}

const compiled = Object.fromEntries(names.map((name) => [name, compile(name)]))

export function withStatComponents(code) {
  return names.reduce(
    (source, name) => source.replace(`'./${name}.vue'`, JSON.stringify(compiled[name])),
    code,
  )
}
