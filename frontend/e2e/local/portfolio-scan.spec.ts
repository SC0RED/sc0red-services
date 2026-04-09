import { test, expect } from '@playwright/test'

test.describe('portfolio scan', () => {
    test('discover → confirm → progress → results', async ({ page }) => {
        await page.goto('/scan/new')

        // Portfolio mode should be default
        await expect(page.getByLabel('PE Firm Website URL')).toBeVisible()

        // Enter PE firm URL
        await page.getByLabel('PE Firm Website URL').fill('https://example-pe.com')
        await page.getByRole('button', { name: 'Discover Portfolio & Analyze' }).click()

        // Wait for discovery to complete — should show confirmation
        await expect(page.getByText(/Portfolio companies discovered|Analyze.*Companies/)).toBeVisible({
            timeout: 30000,
        })

        // If confirmation phase, click to start analysis
        const confirmButton = page.getByRole('button', { name: /Analyze.*Companies/ })
        if (await confirmButton.isVisible().catch(() => false)) {
            await confirmButton.click()
        }

        // Wait for progress
        await expect(page.getByText(/Running Portfolio Analysis|Analyzing/)).toBeVisible({ timeout: 15000 })

        // Wait for completion — redirects to portfolio page
        await expect(page).toHaveURL(/\/portfolio\//, { timeout: 120000 })
    })
})
