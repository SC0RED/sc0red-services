import { test, expect } from '@playwright/test'

/**
 * Visual regression tests for deployed environments.
 * Captures screenshots of key pages on the real deployed app.
 *
 * Run:   ./scripts/playwright.sh --mode=smoke --url=https://... --visual
 * Update baselines: ./scripts/playwright.sh --mode=smoke --url=https://... --visual-update
 */

test.describe('visual regression — deployed', () => {
    test('login page', async ({ page }) => {
        await page.goto('/login')
        await expect(page.getByText('Welcome back')).toBeVisible({ timeout: 15000 })
        await page.waitForLoadState('networkidle')
        await expect(page).toHaveScreenshot('deployed-login.png')
    })

    test('dashboard', async ({ page }) => {
        await page.goto('/dashboard')
        await expect(page.getByText(/Good (morning|afternoon|evening)/)).toBeVisible({ timeout: 15000 })
        await page.waitForLoadState('networkidle')
        await expect(page).toHaveScreenshot('deployed-dashboard.png')
    })

    test('scan input page', async ({ page }) => {
        await page.goto('/scan/new')
        await expect(page.getByLabel('PE Firm Website URL')).toBeVisible({ timeout: 15000 })
        await page.waitForLoadState('networkidle')
        await expect(page).toHaveScreenshot('deployed-scan-input.png')
    })

    test('team management page', async ({ page }) => {
        await page.goto('/team')
        await expect(page.getByRole('heading', { name: 'Team Management' })).toBeVisible({ timeout: 15000 })
        await page.waitForLoadState('networkidle')
        await expect(page).toHaveScreenshot('deployed-team.png')
    })
})
