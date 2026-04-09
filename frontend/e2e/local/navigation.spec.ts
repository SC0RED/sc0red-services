import { test, expect } from '@playwright/test'

test.describe('navigation', () => {
    test('sidebar links navigate correctly', async ({ page }) => {
        await page.goto('/dashboard')

        await page.getByRole('link', { name: 'New Scan' }).click()
        await expect(page).toHaveURL(/\/scan\/new/)

        await page.getByRole('link', { name: 'Analyses' }).click()
        await expect(page).toHaveURL(/\/analyses/)

        await page.getByRole('link', { name: 'Team' }).click()
        await expect(page).toHaveURL(/\/team/)

        await page.getByRole('link', { name: 'Dashboard' }).click()
        await expect(page).toHaveURL(/\/dashboard/)
    })

    test('breadcrumbs show on non-dashboard pages', async ({ page }) => {
        await page.goto('/analyses')

        const breadcrumb = page.getByLabel('Breadcrumb')
        await expect(breadcrumb).toBeVisible()
        await expect(breadcrumb.getByText('Dashboard')).toBeVisible()
    })

    test('landing page accessible without auth', async ({ browser }) => {
        const context = await browser.newContext()
        const page = await context.newPage()

        await page.goto('/')
        await expect(page.getByText('Know Your AI Risk')).toBeVisible()

        await context.close()
    })
})
