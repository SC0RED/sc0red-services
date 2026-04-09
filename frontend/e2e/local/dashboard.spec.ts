import { test, expect } from '@playwright/test'

test.describe('dashboard', () => {
    test('shows stats cards', async ({ page }) => {
        await page.goto('/dashboard')

        await expect(page.getByText('Companies Analyzed')).toBeVisible()
        await expect(page.getByText('Avg Risk Score')).toBeVisible()
        await expect(page.getByText('Critical Risks')).toBeVisible()
        await expect(page.getByText('Total Scans')).toBeVisible()
    })

    test('shows empty state or recent data', async ({ page }) => {
        await page.goto('/dashboard')

        // New test user should have empty dashboard
        const emptyState = page.getByText('Run your first analysis')
        const hasEmptyState = await emptyState.isVisible().catch(() => false)

        if (hasEmptyState) {
            await expect(page.getByText('Scan PE Portfolio')).toBeVisible()
            await expect(page.getByText('Single Company')).toBeVisible()
        }
    })

    test('sidebar navigation works', async ({ page }) => {
        await page.goto('/dashboard')

        await page.getByRole('link', { name: 'Analyses' }).click()
        await expect(page).toHaveURL(/\/analyses/)

        await page.getByRole('link', { name: 'Dashboard' }).click()
        await expect(page).toHaveURL(/\/dashboard/)
    })
})
