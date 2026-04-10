import { test, expect } from '@playwright/test'

/**
 * Session expiry tests — uses auth state with a valid NextAuth cookie
 * containing an expired Cognito ID token (created by local-auth-expired.setup.ts).
 *
 * This reproduces the exact scenario that caused an infinite redirect loop:
 * middleware sees expired idToken → redirects to /login → (old bug: blank page
 * because useSession() returned "authenticated") → redirect back to /dashboard → loop.
 *
 * The fix: login/signup pages always render their forms regardless of session state.
 */

test.describe('session expiry handling', () => {
    test('expired token redirects /dashboard to /login', async ({ page }) => {
        await page.goto('/dashboard')
        await expect(page).toHaveURL(/\/login/, { timeout: 10000 })
    })

    test('login page renders form with expired session (not blank)', async ({ page }) => {
        // This is the core regression test for the infinite loop bug.
        // The old behavior: login page returned null (blank) when session existed.
        await page.goto('/login')

        await expect(page.getByText('Welcome back')).toBeVisible({ timeout: 10000 })
        await expect(page.getByLabel('Email')).toBeVisible()
        await expect(page.getByLabel('Password')).toBeVisible()
        await expect(page.getByRole('button', { name: 'Sign In' })).toBeVisible()
    })

    test('signup page renders form with expired session', async ({ page }) => {
        await page.goto('/signup')
        await expect(page.getByText('Create your account')).toBeVisible({ timeout: 10000 })
        await expect(page.getByLabel('Work email')).toBeVisible()
    })

    test('all protected routes redirect to /login', async ({ page }) => {
        const protectedRoutes = ['/dashboard', '/analyses', '/team', '/scan/new']

        for (const route of protectedRoutes) {
            await page.goto(route)
            await expect(page).toHaveURL(/\/login/, {
                timeout: 10000,
            })
        }
    })

    test('no redirect loop — page stays on /login', async ({ page }) => {
        // Navigate to a protected page, get redirected to /login,
        // then wait a bit to verify no further redirects happen.
        await page.goto('/dashboard')
        await expect(page).toHaveURL(/\/login/, { timeout: 10000 })

        // Wait and confirm we stay on /login (no loop back to /dashboard)
        await page.waitForTimeout(3000)
        await expect(page).toHaveURL(/\/login/)
        await expect(page.getByText('Welcome back')).toBeVisible()
    })
})
