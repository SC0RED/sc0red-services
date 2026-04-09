import { test, expect } from '@playwright/test'

test.describe('analysis detail', () => {
    // These tests assume a completed analysis exists from the scan tests.
    // If running independently, they navigate to an analysis from the dashboard.

    test('analysis page shows risk scores and sections', async ({ page }) => {
        // Navigate to analyses list first
        await page.goto('/analyses')

        // Click on the first analysis if available
        const viewButton = page.getByRole('link', { name: 'View Report' }).first()
        const hasAnalysis = await viewButton.isVisible().catch(() => false)

        if (!hasAnalysis) {
            test.skip(true, 'No analyses available — run scan tests first')
            return
        }

        await viewButton.click()
        await expect(page).toHaveURL(/\/analysis\//)

        // Verify core sections are present
        await expect(page.getByText('Overall AI Risk Score')).toBeVisible()
        await expect(page.getByText('Risk Dimensions')).toBeVisible()
        await expect(page.getByText('Risk Breakdown')).toBeVisible()
    })

    test('analysis shows opportunities section', async ({ page }) => {
        await page.goto('/analyses')

        const viewButton = page.getByRole('link', { name: 'View Report' }).first()
        const hasAnalysis = await viewButton.isVisible().catch(() => false)

        if (!hasAnalysis) {
            test.skip(true, 'No analyses available')
            return
        }

        await viewButton.click()

        await expect(page.getByText('AI Opportunities')).toBeVisible()
    })

    test('analysis shows value chain if present', async ({ page }) => {
        await page.goto('/analyses')

        const viewButton = page.getByRole('link', { name: 'View Report' }).first()
        const hasAnalysis = await viewButton.isVisible().catch(() => false)

        if (!hasAnalysis) {
            test.skip(true, 'No analyses available')
            return
        }

        await viewButton.click()

        // Value chain may or may not be present depending on analysis
        const valueChain = page.getByText('Value Chain Analysis')
        const hasValueChain = await valueChain.isVisible().catch(() => false)
        if (hasValueChain) {
            await expect(page.getByText('Primary Activities')).toBeVisible()
        }
    })
})
