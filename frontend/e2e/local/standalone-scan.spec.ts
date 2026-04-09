import { test, expect } from '@playwright/test'

// In docker-compose E2E, the mock AI server provides a scrapable company page.
// The worker container resolves ai-mock via docker DNS.
const MOCK_COMPANY_URL = process.env.MOCK_COMPANY_URL || 'http://ai-mock:8080/company'

test.describe('standalone scan', () => {
    test('scan page loads with input form', async ({ page }) => {
        await page.goto('/scan/new')
        await page.getByText('Single Company').click()

        await expect(page.getByLabel('Company Website URL')).toBeVisible()
        await expect(page.getByRole('button', { name: 'Analyze Company' })).toBeVisible()
    })

    test('full scan flow: enter URL → progress → results', async ({ page }) => {
        await page.goto('/scan/new')
        await page.getByText('Single Company').click()

        await page.getByLabel('Company Website URL').fill(MOCK_COMPANY_URL)
        await page.getByRole('button', { name: 'Analyze Company' }).click()

        // Wait for progress phase
        await expect(page.getByText(/Analyzing|Scraping|Processing/)).toBeVisible({ timeout: 15000 })

        // Wait for completion (mock AI is fast)
        await expect(page).toHaveURL(/\/analysis\//, { timeout: 120000 })

        // Verify analysis page loaded
        await expect(page.getByText('Overall AI Risk Score')).toBeVisible()
    })
})
