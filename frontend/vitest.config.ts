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
            include: [
                'src/components/**',
                'src/lib/**',
                'src/app/**/AnalysisDetail.tsx',
                'src/app/**/PortfolioView.tsx',
                'src/app/login/**',
                'src/app/signup/**',
                'src/app/scan/new/page.tsx',
            ],
            exclude: [
                'src/**/*.test.*',
                'src/types/**',
                'src/app/api/**',
                'src/app/layout.tsx',
                'src/app/page.tsx',
                'src/middleware.ts',
                'src/lib/auth/**',
                'src/lib/api/serverToken.ts',
                'src/lib/types/**',
                'src/components/SessionWrapper.tsx',
            ],
            thresholds: { lines: 80, branches: 70 },
        },
        environmentMatchGlobs: [
            ['**/*.test.ts', 'node'],
            ['**/*.test.tsx', 'jsdom'],
        ],
    },
    resolve: { alias: { '@': resolve(__dirname, './src') } },
})
