import { test, expect } from '@playwright/test'

/**
 * Visual regression tests for local mode.
 * Captures screenshots of key pages and compares against baselines.
 *
 * Run:   ./scripts/playwright.sh --mode=local --visual
 * Update baselines: ./scripts/playwright.sh --mode=local --visual-update
 */

test.describe('visual regression — local', () => {
    test('login page', async ({ page }) => {
        await page.goto('/login')
        await expect(page.getByText('Welcome back')).toBeVisible({ timeout: 10000 })
        await page.waitForLoadState('networkidle')
        await expect(page).toHaveScreenshot('login-page.png')
    })

    test('signup page', async ({ page }) => {
        await page.goto('/signup')
        await expect(page.getByText('Create your account')).toBeVisible({ timeout: 10000 })
        await page.waitForLoadState('networkidle')
        await expect(page).toHaveScreenshot('signup-page.png')
    })

    test('dashboard — empty state', async ({ page }) => {
        await page.goto('/dashboard')
        await expect(page.getByText(/Good (morning|afternoon|evening)/)).toBeVisible({ timeout: 15000 })
        await page.waitForLoadState('networkidle')
        await expect(page).toHaveScreenshot('dashboard-empty.png')
    })

    test('scan input page', async ({ page }) => {
        await page.goto('/scan/new')
        await expect(page.getByLabel('PE Firm Website URL')).toBeVisible({ timeout: 10000 })
        await page.waitForLoadState('networkidle')
        await expect(page).toHaveScreenshot('scan-input.png')
    })

    test('team management page', async ({ page }) => {
        await page.goto('/team')
        await expect(page.getByRole('heading', { name: 'Team Management' })).toBeVisible({ timeout: 10000 })
        await page.waitForLoadState('networkidle')
        await expect(page).toHaveScreenshot('team-page.png')
    })
})
