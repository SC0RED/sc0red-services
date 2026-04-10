import { test, expect } from '@playwright/test'

/**
 * Visual regression for pages that require scan data.
 * Runs after the local project completes a scan, so analysis data exists.
 */

test.describe('visual regression — post-scan', () => {
    test('analysis detail page', async ({ page }) => {
        await page.goto('/analyses')

        const viewButton = page.getByRole('link', { name: 'View analysis' }).first()
        await expect(viewButton).toBeVisible({ timeout: 15000 })
        await viewButton.click()

        await expect(page.getByText('Overall AI Risk Score')).toBeVisible({ timeout: 10000 })
        await page.waitForLoadState('networkidle')
        await expect(page).toHaveScreenshot('analysis-detail.png')
    })

    test('dashboard — with data', async ({ page }) => {
        await page.goto('/dashboard')
        await expect(page.getByText(/Good (morning|afternoon|evening)/)).toBeVisible({ timeout: 15000 })
        await page.waitForLoadState('networkidle')
        await expect(page).toHaveScreenshot('dashboard-with-data.png')
    })
})
