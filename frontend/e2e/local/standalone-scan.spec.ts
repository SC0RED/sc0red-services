import { test, expect } from '@playwright/test'

test.describe('standalone scan', () => {
    test('full scan flow: enter URL → progress → results', async ({ page }) => {
        await page.goto('/scan/new')

        // Select standalone mode
        await page.getByText('Single Company').click()

        // Enter URL and start scan
        await page.getByLabel('Company Website URL').fill('https://example.com')
        await page.getByRole('button', { name: 'Analyze Company' }).click()

        // Wait for progress phase
        await expect(page.getByText(/Analyzing|Scraping|Processing/)).toBeVisible({ timeout: 15000 })

        // Wait for completion (mock AI is fast)
        await expect(page).toHaveURL(/\/analysis\//, { timeout: 60000 })

        // Verify analysis page loaded
        await expect(page.getByText('Overall AI Risk Score')).toBeVisible()
    })

    test('shows error for invalid URL', async ({ page }) => {
        await page.goto('/scan/new')
        await page.getByText('Single Company').click()

        await page.getByLabel('Company Website URL').fill('not-a-url')
        await page.getByRole('button', { name: 'Analyze Company' }).click()

        await expect(page.getByText(/invalid|error|required/i)).toBeVisible({ timeout: 10000 })
    })
})
