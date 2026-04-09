import { test as setup, expect } from '@playwright/test'

/**
 * Local auth setup for docker-compose E2E environment.
 *
 * In the E2E environment, COGNITO_USER_POOL_ID is empty — the backend
 * skips Cognito and only creates DynamoDB records. The frontend can't
 * do real Cognito login with fake pool IDs.
 *
 * Strategy: Register a test user via the backend API, then save an
 * unauthenticated storage state. Local E2E tests focus on:
 * - Unauthenticated flows (landing page, login page, signup page)
 * - Auth redirects (unauthenticated → login)
 * - Backend API integration (via the existing E2E script)
 *
 * Authenticated browser flows (dashboard, scan, analysis) are tested
 * in the deployed smoke/full E2E tests which use real Cognito.
 */

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8001'

setup('register test user and save state', async ({ page }) => {
    const timestamp = Date.now()
    const email = `e2e-${timestamp}@janus-test.com`

    // Register via backend API (no Cognito in E2E mode)
    const response = await page.request.post(`${BACKEND_URL}/api/auth/register`, {
        data: {
            name: 'E2E Test User',
            email,
            password: 'TestPass123!',
            orgName: `E2E Org ${timestamp}`,
        },
    })

    expect(response.ok()).toBeTruthy()

    // Verify the landing page loads
    await page.goto('/')
    await expect(page.getByText('Know Your AI Risk')).toBeVisible()

    // Save storage state (unauthenticated — no Cognito login possible locally)
    await page.context().storageState({ path: './playwright/.auth/local.json' })
})
