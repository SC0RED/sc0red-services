import { test, expect } from '@playwright/test'

test.describe('authentication', () => {
    test('login page renders with form', async ({ page }) => {
        await page.goto('/login')
        await expect(page.getByText('Welcome back')).toBeVisible()
        await expect(page.getByLabel('Email')).toBeVisible()
        await expect(page.getByLabel('Password')).toBeVisible()
    })

    test('signup page renders with form', async ({ page }) => {
        await page.goto('/signup')
        await expect(page.getByText('Create your account')).toBeVisible()
        await expect(page.getByLabel('Work email')).toBeVisible()
    })

    test('login page has links to signup and forgot password', async ({ page }) => {
        await page.goto('/login')
        await expect(page.getByRole('link', { name: 'Create one' })).toBeVisible()
        await expect(page.getByRole('link', { name: 'Forgot password?' })).toBeVisible()
    })

    test('authenticated user can access dashboard', async ({ page }) => {
        await page.goto('/dashboard')
        await expect(page).toHaveURL(/\/dashboard/)
        await expect(page.getByText(/Good (morning|afternoon|evening)/)).toBeVisible()
    })
})
