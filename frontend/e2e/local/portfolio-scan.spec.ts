import { test, expect } from '@playwright/test'

const MOCK_COMPANY_URL = process.env.MOCK_COMPANY_URL || 'http://ai-mock:8080/company'

test.describe('portfolio scan', () => {
    test('portfolio mode is default with PE firm URL input', async ({ page }) => {
        await page.goto('/scan/new')
        await expect(page.getByLabel('PE Firm Website URL')).toBeVisible()
        await expect(page.getByRole('button', { name: 'Discover Portfolio & Analyze' })).toBeVisible()
    })

    test('portfolio scan: discover → confirm → progress', async ({ page }) => {
        await page.goto('/scan/new')

        await page.getByLabel('PE Firm Website URL').fill(MOCK_COMPANY_URL)
        await page.getByRole('button', { name: 'Discover Portfolio & Analyze' }).click()

        // Wait for discovery — either shows confirmation or goes to progress
        await expect(
            page.getByText(/Portfolio companies discovered|Running Portfolio Analysis|Analyzing/)
        ).toBeVisible({ timeout: 30000 })

        // If confirmation phase, confirm and wait for progress
        const confirmButton = page.getByRole('button', { name: /Analyze.*Compan/ })
        if (await confirmButton.isVisible({ timeout: 3000 }).catch(() => false)) {
            await confirmButton.click()

            // Wait for portfolio progress or completion
            await expect(page.getByText(/Running Portfolio Analysis|Analyzing|complete/i)).toBeVisible({
                timeout: 15000,
            })
        }

        // Wait for completion — redirects to portfolio page
        await expect(page).toHaveURL(/\/portfolio\//, { timeout: 120000 })
    })
})
