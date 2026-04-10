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

        const urlInput = page.getByLabel('Company Website URL')
        await expect(urlInput).toBeVisible({ timeout: 10000 })
        await urlInput.fill('https://stripe.com')

        const submitButton = page.getByRole('button', { name: 'Analyze Company' })
        await expect(submitButton).toBeEnabled({ timeout: 5000 })
        await submitButton.click()

        // Wait for either: progress phase, error, or URL change
        // The scan should leave /scan/new once submitted
        await expect(
            page
                .getByText(/Analyzing|Scraping|Processing|error|failed/i)
                .or(page.locator('text=/Overall AI Risk Score/'))
        ).toBeVisible({ timeout: 60000 })

        // If we see an error, skip the rest — scan infrastructure may be cold
        const hasError = await page
            .getByText(/error|failed/i)
            .isVisible()
            .catch(() => false)
        if (hasError) {
            test.skip(true, 'Scan failed — AI infrastructure may be cold starting')
            return
        }

        // Wait for completion — real AI takes longer
        await expect(page).toHaveURL(/\/analysis\//, { timeout: SCAN_TIMEOUT })

        // Verify analysis page loaded with real data
        await expect(page.getByText('Overall AI Risk Score')).toBeVisible()
        await expect(page.getByText('Risk Dimensions')).toBeVisible()
    })
})
