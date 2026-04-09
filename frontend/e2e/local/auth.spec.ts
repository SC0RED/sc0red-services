import { test, expect } from '@playwright/test'

test.describe('authentication', () => {
    test('login page renders', async ({ page }) => {
        await page.goto('/login')
        await expect(page.getByText('Welcome back')).toBeVisible()
        await expect(page.getByLabel('Email')).toBeVisible()
        await expect(page.getByLabel('Password')).toBeVisible()
    })

    test('signup page renders', async ({ page }) => {
        await page.goto('/signup')
        await expect(page.getByText('Create your account')).toBeVisible()
        await expect(page.getByLabel('Work email')).toBeVisible()
    })

    test('invalid login shows error', async ({ page }) => {
        await page.goto('/login')
        await page.getByLabel('Email').fill('wrong@test.com')
        await page.getByLabel('Password').fill('WrongPass123')
        await page.getByRole('button', { name: 'Sign In' }).click()

        await expect(page.getByText('Invalid email or password')).toBeVisible({ timeout: 10000 })
    })

    test('authenticated user can access dashboard', async ({ page }) => {
        await page.goto('/dashboard')
        await expect(page).toHaveURL(/\/dashboard/)
        await expect(page.getByText(/Good (morning|afternoon|evening)/)).toBeVisible()
    })

    test('unauthenticated user redirected to login', async ({ browser }) => {
        // Fresh context without stored auth
        const context = await browser.newContext()
        const page = await context.newPage()

        await page.goto('/dashboard')
        await expect(page).toHaveURL(/\/login/)

        await context.close()
    })
})
