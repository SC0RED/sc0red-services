import { test, expect } from '@playwright/test'

test.describe('navigation', () => {
    test('sidebar links navigate correctly', async ({ page }) => {
        await page.goto('/dashboard')

        // Navigate to New Scan
        await page.getByRole('link', { name: 'New Scan' }).click()
        await expect(page).toHaveURL(/\/scan\/new/)

        // Navigate to Analyses
        await page.getByRole('link', { name: 'Analyses' }).click()
        await expect(page).toHaveURL(/\/analyses/)

        // Navigate to Team
        await page.getByRole('link', { name: 'Team' }).click()
        await expect(page).toHaveURL(/\/team/)

        // Back to Dashboard
        await page.getByRole('link', { name: 'Dashboard' }).click()
        await expect(page).toHaveURL(/\/dashboard/)
    })

    test('breadcrumbs show on non-dashboard pages', async ({ page }) => {
        await page.goto('/analyses')

        const breadcrumb = page.getByLabel('Breadcrumb')
        await expect(breadcrumb).toBeVisible()
        await expect(breadcrumb.getByText('Dashboard')).toBeVisible()
        await expect(breadcrumb.getByText('Analyses')).toBeVisible()
    })

    test('breadcrumb Dashboard link navigates home', async ({ page }) => {
        await page.goto('/analyses')

        await page.getByLabel('Breadcrumb').getByText('Dashboard').click()
        await expect(page).toHaveURL(/\/dashboard/)
    })

    test('landing page accessible without auth', async ({ browser }) => {
        const context = await browser.newContext()
        const page = await context.newPage()

        await page.goto('/')
        await expect(page.getByText('Know Your AI Risk')).toBeVisible()
        await expect(page.getByText('Sign In')).toBeVisible()

        await context.close()
    })
})
