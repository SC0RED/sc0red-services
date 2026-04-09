import { test, expect } from '@playwright/test'

test.describe('team management', () => {
    test('team page loads with heading', async ({ page }) => {
        await page.goto('/team')
        await expect(page.getByRole('heading', { name: 'Team Management' })).toBeVisible({ timeout: 10000 })
    })

    test('current user shown in members list', async ({ page }) => {
        await page.goto('/team')
        await expect(page.getByText('E2E Test User')).toBeVisible({ timeout: 10000 })
    })

    test('invite form accepts email input', async ({ page }) => {
        await page.goto('/team')
        const emailInput = page.getByPlaceholder(/email/i)
        await expect(emailInput).toBeVisible({ timeout: 10000 })
        await emailInput.fill('invite-test@example.com')
        await expect(emailInput).toHaveValue('invite-test@example.com')
    })
})
