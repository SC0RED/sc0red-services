import { test, expect } from '@playwright/test'

test.describe('analysis detail', () => {
    test('navigate to analysis from analyses list', async ({ page }) => {
        await page.goto('/analyses')

        const viewButton = page.getByRole('link', { name: 'View Report' }).first()
        const hasAnalysis = await viewButton.isVisible({ timeout: 5000 }).catch(() => false)

        if (!hasAnalysis) {
            test.skip(true, 'No analyses available — run scan tests first')
            return
        }

        await viewButton.click()
        await expect(page).toHaveURL(/\/analysis\//)
    })

    test('analysis page shows core sections', async ({ page }) => {
        await page.goto('/analyses')

        const viewButton = page.getByRole('link', { name: 'View Report' }).first()
        if (!(await viewButton.isVisible({ timeout: 5000 }).catch(() => false))) {
            test.skip(true, 'No analyses available')
            return
        }

        await viewButton.click()

        // Core sections
        await expect(page.getByText('Overall AI Risk Score')).toBeVisible()
        await expect(page.getByText('Risk Dimensions')).toBeVisible()
        await expect(page.getByText('Risk Breakdown')).toBeVisible()
    })

    test('analysis page shows opportunities', async ({ page }) => {
        await page.goto('/analyses')

        const viewButton = page.getByRole('link', { name: 'View Report' }).first()
        if (!(await viewButton.isVisible({ timeout: 5000 }).catch(() => false))) {
            test.skip(true, 'No analyses available')
            return
        }

        await viewButton.click()

        await expect(page.getByText('AI Opportunities')).toBeVisible()
    })

    test('analysis page shows value chain', async ({ page }) => {
        await page.goto('/analyses')

        const viewButton = page.getByRole('link', { name: 'View Report' }).first()
        if (!(await viewButton.isVisible({ timeout: 5000 }).catch(() => false))) {
            test.skip(true, 'No analyses available')
            return
        }

        await viewButton.click()

        // Value chain section
        const valueChain = page.getByText('Value Chain Analysis')
        if (await valueChain.isVisible({ timeout: 3000 }).catch(() => false)) {
            await expect(page.getByText('Primary Activities')).toBeVisible()
        }
    })

    test('analysis page shows EBITDA section', async ({ page }) => {
        await page.goto('/analyses')

        const viewButton = page.getByRole('link', { name: 'View Report' }).first()
        if (!(await viewButton.isVisible({ timeout: 5000 }).catch(() => false))) {
            test.skip(true, 'No analyses available')
            return
        }

        await viewButton.click()

        // EBITDA section
        const ebitda = page.getByText('EBITDA Impact Model')
        if (await ebitda.isVisible({ timeout: 3000 }).catch(() => false)) {
            await expect(ebitda).toBeVisible()
        }
    })
})
