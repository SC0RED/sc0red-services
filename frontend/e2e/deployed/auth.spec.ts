import { test, expect } from '@playwright/test'

test.describe('authentication', () => {
    test('dashboard loads with greeting', async ({ page }) => {
        await page.goto('/dashboard')
        await expect(page.getByText(/Good (morning|afternoon|evening)/)).toBeVisible({ timeout: 15000 })
    })

    test('dashboard shows content after loading', async ({ page }) => {
        await page.goto('/dashboard')
        // Wait for dashboard to fully load — greeting confirms data is rendered
        await expect(page.getByText(/Good (morning|afternoon|evening)/)).toBeVisible({ timeout: 15000 })
        // Verify either stats cards or empty state is present
        await expect(page.locator('text=/Companies Analyzed|Run your first analysis/').first()).toBeVisible()
    })

    test('user name appears in sidebar', async ({ page }) => {
        await page.goto('/dashboard')
        const sidebar = page.getByRole('complementary')
        await expect(sidebar.getByText('E2E Test User')).toBeVisible({ timeout: 15000 })
    })
})
