import { test, expect } from '@playwright/test'

// Testing environment uses real AI — scans take longer
const SCAN_TIMEOUT = 180_000

test.describe('standalone scan (real AI)', () => {
    test('scan page loads with input form', async ({ page }) => {
        await page.goto('/scan/new')
        await page.getByText('Single Company').click()

        await expect(page.getByLabel('Company Website URL')).toBeVisible()
        await expect(page.getByRole('button', { name: 'Analyze Company' })).toBeVisible()
    })

    test('full scan flow: enter URL → progress → results', async ({ page }) => {
        test.setTimeout(SCAN_TIMEOUT)

        await page.goto('/scan/new')
        await page.getByText('Single Company').click()

        // Use a real, lightweight company URL
        await page.getByLabel('Company Website URL').fill('https://stripe.com')
        await page.getByRole('button', { name: 'Analyze Company' }).click()

        // Wait for progress phase
        await expect(page.getByText(/Analyzing|Scraping|Processing/)).toBeVisible({ timeout: 30000 })

        // Wait for completion — real AI takes longer
        await expect(page).toHaveURL(/\/analysis\//, { timeout: SCAN_TIMEOUT })

        // Verify analysis page loaded with real data
        await expect(page.getByText('Overall AI Risk Score')).toBeVisible()
        await expect(page.getByText('Risk Dimensions')).toBeVisible()
    })
})
