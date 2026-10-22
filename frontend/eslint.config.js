import js from '@eslint/js'
import globals from 'globals'
import tseslint from 'typescript-eslint'
import vue from 'eslint-plugin-vue'

// Correctness rules only: layout belongs to Prettier.
export default tseslint.config(
  { ignores: ['dist/**', 'node_modules/**', 'public/**'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...vue.configs['flat/essential'],
  {
    files: ['**/*.vue'],
    languageOptions: { parserOptions: { parser: tseslint.parser } },
  },
  {
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    rules: {
      // API payloads are typed loosely across the codebase; typing them is a separate effort.
      '@typescript-eslint/no-explicit-any': 'off',
      // Best-effort storage and already-reported failures deliberately swallow errors.
      'no-empty': ['error', { allowEmptyCatch: true }],
    },
  },
  {
    // Root component mounted by main.ts.
    files: ['src/Portal.vue'],
    rules: { 'vue/multi-word-component-names': 'off' },
  },
)
