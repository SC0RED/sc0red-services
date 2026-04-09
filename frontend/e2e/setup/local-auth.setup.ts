import { test as setup, expect } from '@playwright/test'

const TEST_USER = {
    name: 'E2E Test User',
    email: `e2e-local-${Date.now()}@janus-test.com`,
    password: 'TestPass123!',
    orgName: 'E2E Test Org',
    orgType: 'pe_firm',
}

setup('register and authenticate', async ({ page }) => {
    // Register a new user
    await page.goto('/signup')
    await page.getByLabel('Your name').fill(TEST_USER.name)
    await page.getByLabel('Firm name').fill(TEST_USER.orgName)
    await page.getByLabel('Work email').fill(TEST_USER.email)
    await page.getByLabel('Password').fill(TEST_USER.password)
    await page.getByRole('button', { name: 'Create Account & Start' }).click()

    // Wait for redirect to dashboard
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 })

    // Save storage state (cookies + localStorage)
    await page.context().storageState({ path: './playwright/.auth/local.json' })
})
