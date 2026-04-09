import { test, expect } from '@playwright/test'

test.describe('authentication', () => {
    test('dashboard loads with greeting', async ({ page }) => {
        await page.goto('/dashboard')
        await expect(page.getByText(/Good (morning|afternoon|evening)/)).toBeVisible({ timeout: 15000 })
    })

    test('dashboard shows stats cards', async ({ page }) => {
        await page.goto('/dashboard')
        await expect(page.getByText('Total Analyses')).toBeVisible({ timeout: 15000 })
        await expect(page.getByText('Average Risk')).toBeVisible()
    })

    test('user name appears in sidebar', async ({ page }) => {
        await page.goto('/dashboard')
        const sidebar = page.getByRole('complementary')
        await expect(sidebar.getByText('E2E Test User')).toBeVisible({ timeout: 15000 })
    })
})
