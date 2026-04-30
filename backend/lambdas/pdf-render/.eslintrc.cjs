/* eslint-disable @typescript-eslint/no-require-imports */
module.exports = {
    root: true,
    parser: '@typescript-eslint/parser',
    parserOptions: {
        ecmaVersion: 2022,
        sourceType: 'module',
        // Lints both src/ and tests/ — must use the wider tsconfig that
        // includes tests, since the build tsconfig deliberately excludes
        // them (vitest transforms tests at runtime; we don't ship them
        // in the Lambda asset).
        project: './tsconfig.eslint.json',
    },
    plugins: ['@typescript-eslint'],
    extends: ['eslint:recommended', 'plugin:@typescript-eslint/recommended'],
    env: {
        node: true,
        es2022: true,
    },
    rules: {
        '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
        '@typescript-eslint/no-explicit-any': 'warn',
        '@typescript-eslint/no-require-imports': 'error',
    },
}
