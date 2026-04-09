import { test, expect } from '@playwright/test'

test.describe('authentication', () => {
    test('dashboard loads with greeting', async ({ page }) => {
        await page.goto('/dashboard')
        await expect(page.getByText(/Good (morning|afternoon|evening)/)).toBeVisible({ timeout: 15000 })
    })

    test('dashboard shows empty state or stats', async ({ page }) => {
        await page.goto('/dashboard')
        // New user sees empty state; returning user sees stats cards
        await expect(page.getByText(/Run your first analysis|Companies Analyzed/)).toBeVisible({
            timeout: 15000,
        })
    })

    test('user name appears in sidebar', async ({ page }) => {
        await page.goto('/dashboard')
        const sidebar = page.getByRole('complementary')
        await expect(sidebar.getByText('E2E Test User')).toBeVisible({ timeout: 15000 })
    })
})
