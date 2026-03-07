import { resolve } from 'path'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
    plugins: [react()],
    test: {
        globals: true,
        environment: 'jsdom',
        setupFiles: ['./vitest.setup.ts'],
        coverage: {
            provider: 'v8',
            thresholds: { lines: 80, branches: 80 },
        },
        environmentMatchGlobs: [
            ['**/*.test.ts', 'node'],
            ['**/*.test.tsx', 'jsdom'],
        ],
    },
    resolve: { alias: { '@': resolve(__dirname, './src') } },
})
