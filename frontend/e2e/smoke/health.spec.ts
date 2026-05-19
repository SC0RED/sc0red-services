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

    test('landing page redirects to login or dashboard', async ({ browser }) => {
        const context = await browser.newContext()
        const page = await context.newPage()
        await page.goto('/')
        // Without a session, the app should show either the login page or
        // marketing landing. The brand string is `sc0red Services` post-
        // Phase-1 rebrand (was `sc0red Services`); kept as an alternation rather than
        // an exact match so a future rename doesn't silently mask a real
        // outage.
        await expect(page.getByText(/Welcome back|Sign in|sc0red Services/)).toBeVisible({
            timeout: 15000,
        })
        await context.close()
    })
})
