import { test, expect } from '@playwright/test'

test.describe('health checks', () => {
    test('login page loads', async ({ page }) => {
        await page.goto('/login')
        await expect(page.getByText('Welcome back')).toBeVisible({ timeout: 15000 })
    })

    test('signup page loads', async ({ page }) => {
        await page.goto('/signup')
        await expect(page.getByText('Create your account')).toBeVisible({ timeout: 15000 })
    })

    test('unauthenticated access redirects to login', async ({ browser }) => {
        const context = await browser.newContext()
        const page = await context.newPage()
        await page.goto('/dashboard')
        await expect(page).toHaveURL(/\/login/, { timeout: 15000 })
        await context.close()
    })
})
