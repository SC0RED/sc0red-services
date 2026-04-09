import { test, expect } from '@playwright/test'

test.describe('portfolio scan', () => {
    test('portfolio mode is default with PE firm URL input', async ({ page }) => {
        await page.goto('/scan/new')
        await expect(page.getByLabel('PE Firm Website URL')).toBeVisible()
        await expect(page.getByRole('button', { name: 'Discover Portfolio & Analyze' })).toBeVisible()
    })

    test('can switch to single company mode', async ({ page }) => {
        await page.goto('/scan/new')

        const singleButton = page.getByRole('button', { name: /Single Company/i }).first()
        await expect(singleButton).toBeVisible({ timeout: 10000 })
        await singleButton.click()

        await expect(page.getByLabel('Company Website URL')).toBeVisible()
    })
})
