import { test, expect } from '@playwright/test'

test.describe('authenticated access', () => {
    test('dashboard loads with greeting', async ({ page }) => {
        await page.goto('/dashboard')
        await expect(page.getByText(/Good (morning|afternoon|evening)/)).toBeVisible({ timeout: 15000 })
    })

    test('can navigate to analyses page', async ({ page }) => {
        await page.goto('/analyses')
        await expect(page.getByText('All Analyses')).toBeVisible({ timeout: 15000 })
    })

    test('can navigate to scan page', async ({ page }) => {
        await page.goto('/scan/new')
        await expect(page.getByLabel('PE Firm Website URL')).toBeVisible({ timeout: 15000 })
    })

    test('can navigate to team page', async ({ page }) => {
        await page.goto('/team')
        await expect(page.getByRole('heading', { name: 'Team Management' })).toBeVisible({ timeout: 15000 })
    })
})
