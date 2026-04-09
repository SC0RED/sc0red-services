import { test, expect } from '@playwright/test'

test.describe('navigation', () => {
    test('sidebar links navigate correctly', async ({ page }) => {
        await page.goto('/dashboard')
        const sidebar = page.getByRole('complementary')

        await sidebar.getByRole('link', { name: 'New Scan' }).first().click()
        await expect(page).toHaveURL(/\/scan\/new/)

        await sidebar.getByRole('link', { name: 'Analyses' }).first().click()
        await expect(page).toHaveURL(/\/analyses/)

        await sidebar.getByRole('link', { name: 'Team' }).first().click()
        await expect(page).toHaveURL(/\/team/)

        await sidebar.getByRole('link', { name: 'Dashboard' }).first().click()
        await expect(page).toHaveURL(/\/dashboard/)
    })

    test('breadcrumbs show on non-dashboard pages', async ({ page }) => {
        await page.goto('/analyses')

        const breadcrumb = page.getByLabel('Breadcrumb')
        await expect(breadcrumb).toBeVisible()
        await expect(breadcrumb.getByText('Dashboard')).toBeVisible()
    })
})
