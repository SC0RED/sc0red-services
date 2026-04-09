import { defineConfig } from '@playwright/test'

const LOCAL_BASE_URL = 'http://localhost:3000'
const DEPLOYED_BASE_URL = process.env.PLAYWRIGHT_BASE_URL || ''

export default defineConfig({
    testDir: './e2e',
    fullyParallel: true,
    forbidOnly: !!process.env.CI,
    retries: process.env.CI ? 2 : 0,
    workers: process.env.CI ? 1 : undefined,
    reporter: process.env.CI ? 'github' : 'html',
    timeout: 60_000,

    use: {
        trace: 'on-first-retry',
        screenshot: 'only-on-failure',
    },

    projects: [
        // ── Local E2E (docker-compose) ──────────────────────────
        {
            name: 'local-setup',
            testDir: './e2e/setup',
            testMatch: 'local-auth.setup.ts',
            use: { baseURL: LOCAL_BASE_URL },
        },
        {
            name: 'local',
            testDir: './e2e/local',
            testIgnore: 'analysis-detail.spec.ts',
            dependencies: ['local-setup'],
            use: {
                baseURL: LOCAL_BASE_URL,
                storageState: './playwright/.auth/local.json',
            },
        },
        {
            name: 'local-post-scan',
            testDir: './e2e/local',
            testMatch: 'analysis-detail.spec.ts',
            dependencies: ['local'],
            use: {
                baseURL: LOCAL_BASE_URL,
                storageState: './playwright/.auth/local.json',
            },
        },

        // ── Smoke (deployed dev) ────────────────────────────────
        {
            name: 'deployed-setup',
            testDir: './e2e/setup',
            testMatch: 'deployed-auth.setup.ts',
            use: { baseURL: DEPLOYED_BASE_URL },
        },
        {
            name: 'smoke',
            testDir: './e2e/smoke',
            dependencies: ['deployed-setup'],
            use: {
                baseURL: DEPLOYED_BASE_URL,
                storageState: './playwright/.auth/deployed.json',
            },
        },

        // ── Full Deployed (testing env) ─────────────────────────
        {
            name: 'deployed',
            testDir: './e2e/deployed',
            dependencies: ['deployed-setup'],
            use: {
                baseURL: DEPLOYED_BASE_URL,
                storageState: './playwright/.auth/deployed.json',
            },
        },
    ],
})
