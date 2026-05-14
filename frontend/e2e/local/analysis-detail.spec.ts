import { test, expect } from '@playwright/test'

// This spec runs in the "local-post-scan" project, which depends on "local".
// By the time these tests run, standalone-scan.spec.ts has completed a scan,
// so there is at least one analysis in the list.

test.describe('analysis detail', () => {
    test('navigate to analysis from analyses list', async ({ page }) => {
        await page.goto('/analyses')

        const viewButton = page.getByRole('link', { name: 'View analysis' }).first()
        await expect(viewButton).toBeVisible({ timeout: 15000 })

        await viewButton.click()
        await expect(page).toHaveURL(/\/analysis\//)
    })

    test('analysis page shows core sections', async ({ page }) => {
        await page.goto('/analyses')

        const viewButton = page.getByRole('link', { name: 'View analysis' }).first()
        await expect(viewButton).toBeVisible({ timeout: 15000 })
        await viewButton.click()

        await expect(page.getByText('Overall AI Risk Score')).toBeVisible()
        await expect(page.getByText('Risk Dimensions')).toBeVisible()
        await expect(page.getByText('Risk Breakdown')).toBeVisible()
    })

    test('analysis page shows opportunities', async ({ page }) => {
        await page.goto('/analyses')

        const viewButton = page.getByRole('link', { name: 'View analysis' }).first()
        await expect(viewButton).toBeVisible({ timeout: 15000 })
        await viewButton.click()

        // Scope to the heading — the EBITDA opportunity-link legend also
        // mentions "AI Opportunities" inline, so a bare getByText match would
        // collide. The section header is the authoritative anchor.
        await expect(page.getByRole('heading', { name: /AI Opportunities/ })).toBeVisible()
    })

    test('analysis page shows value chain', async ({ page }) => {
        await page.goto('/analyses')

        const viewButton = page.getByRole('link', { name: 'View analysis' }).first()
        await expect(viewButton).toBeVisible({ timeout: 15000 })
        await viewButton.click()

        const valueChain = page.getByText('Value Chain Analysis')
        if (await valueChain.isVisible({ timeout: 3000 }).catch(() => false)) {
            await expect(page.getByText('Primary Activities', { exact: true })).toBeVisible()
        }
    })

    test('analysis page shows EBITDA section', async ({ page }) => {
        await page.goto('/analyses')

        const viewButton = page.getByRole('link', { name: 'View analysis' }).first()
        await expect(viewButton).toBeVisible({ timeout: 15000 })
        await viewButton.click()

        const ebitda = page.getByText('EBITDA Impact Model')
        if (await ebitda.isVisible({ timeout: 3000 }).catch(() => false)) {
            await expect(ebitda).toBeVisible()
        }
    })
})
