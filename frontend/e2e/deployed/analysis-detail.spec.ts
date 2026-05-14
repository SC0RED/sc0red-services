import { test, expect } from '@playwright/test'

// Runs after standalone-scan.spec.ts has created at least one analysis

async function navigateToAnalysis(page: import('@playwright/test').Page) {
    await page.goto('/analyses')
    const viewButton = page.getByRole('link', { name: 'View analysis' }).first()
    await expect(viewButton).toBeVisible({ timeout: 15000 })
    await viewButton.click()
    await expect(page).toHaveURL(/\/analysis\//, { timeout: 15000 })
    await expect(page.getByText('Overall AI Risk Score')).toBeVisible({ timeout: 10000 })
}

test.describe('analysis detail', () => {
    test('navigate to analysis from analyses list', async ({ page }) => {
        await navigateToAnalysis(page)
    })

    test('analysis page shows core sections', async ({ page }) => {
        await navigateToAnalysis(page)
        await expect(page.getByText('Risk Dimensions')).toBeVisible()
        await expect(page.getByText('Risk Breakdown')).toBeVisible()
    })

    test('analysis page shows opportunities', async ({ page }) => {
        await navigateToAnalysis(page)
        // Scope to the heading — the EBITDA opportunity-link legend also
        // mentions "AI Opportunities" inline, so a bare getByText match would
        // collide. The section header is the authoritative anchor.
        await expect(page.getByRole('heading', { name: /AI Opportunities/ })).toBeVisible({
            timeout: 10000,
        })
    })

    test('analysis page shows EBITDA section', async ({ page }) => {
        await navigateToAnalysis(page)
        // Scope to the visible <h2> — EbitdaTree also renders a
        // ``visually-hidden`` <h2>EBITDA Impact Model</h2> for sr-only
        // accessible-name anchoring, so a bare getByText match resolves
        // to two elements. The page-level AnalysisSection heading is the
        // authoritative on-screen anchor.
        await expect(page.getByRole('heading', { name: 'EBITDA Impact Model' }).first()).toBeVisible({
            timeout: 10000,
        })
    })

    test('analysis page shows value chain', async ({ page }) => {
        await navigateToAnalysis(page)
        await expect(page.getByText('Value Chain Analysis')).toBeVisible({ timeout: 10000 })
        await expect(page.getByText('Primary Activities', { exact: true })).toBeVisible()
    })
})
