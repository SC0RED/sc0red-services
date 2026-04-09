import { test as setup, expect } from '@playwright/test'

/**
 * Deployed auth setup — registers a real user via the signup UI,
 * which goes through Cognito + backend. Then verifies dashboard access
 * and saves the authenticated storage state for smoke/deployed tests.
 */

const TIMESTAMP = Date.now()
const TEST_EMAIL = `e2e-${TIMESTAMP}@janus-test.com`
const TEST_PASSWORD = 'E2eTestPass123!'
const TEST_NAME = 'E2E Test User'
const TEST_ORG = `E2E Org ${TIMESTAMP}`

setup('register via signup page and create authenticated session', async ({ page }) => {
    // 1. Navigate to signup page
    await page.goto('/signup')
    await expect(page.getByText('Create your account')).toBeVisible({ timeout: 15000 })

    // 2. Fill out registration form
    await page.getByLabel('Your name').fill(TEST_NAME)
    await page.getByLabel(/firm name|company name/i).fill(TEST_ORG)
    await page.getByLabel('Work email').fill(TEST_EMAIL)
    await page.getByLabel('Password').fill(TEST_PASSWORD)

    // 3. Submit registration
    await page.getByRole('button', { name: /Create Account/i }).click()

    // 4. Wait for redirect to dashboard (signup auto-signs in)
    await expect(page.getByText(/Good (morning|afternoon|evening)/)).toBeVisible({ timeout: 30000 })
    await expect(page).toHaveURL(/\/dashboard/)

    // 5. Save storage state for smoke/deployed tests
    await page.context().storageState({ path: './playwright/.auth/deployed.json' })
})
