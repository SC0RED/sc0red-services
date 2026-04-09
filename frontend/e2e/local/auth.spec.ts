import { test, expect } from '@playwright/test'

test.describe('authentication pages', () => {
    test('login page renders with form', async ({ page }) => {
        await page.goto('/login')
        await expect(page.getByText('Welcome back')).toBeVisible()
        await expect(page.getByLabel('Email')).toBeVisible()
        await expect(page.getByLabel('Password')).toBeVisible()
        await expect(page.getByRole('button', { name: 'Sign In' })).toBeVisible()
    })

    test('signup page renders with form', async ({ page }) => {
        await page.goto('/signup')
        await expect(page.getByText('Create your account')).toBeVisible()
        await expect(page.getByLabel('Work email')).toBeVisible()
        await expect(page.getByLabel('Password')).toBeVisible()
    })

    test('login page has link to signup', async ({ page }) => {
        await page.goto('/login')
        await expect(page.getByRole('link', { name: 'Create one' })).toBeVisible()
    })

    test('signup page has link to login', async ({ page }) => {
        await page.goto('/signup')
        await expect(page.getByRole('link', { name: 'Sign in' })).toBeVisible()
    })

    test('unauthenticated user visiting dashboard redirected to login', async ({ page }) => {
        await page.goto('/dashboard')
        await expect(page).toHaveURL(/\/login/, { timeout: 10000 })
    })

    test('unauthenticated user visiting analyses redirected to login', async ({ page }) => {
        await page.goto('/analyses')
        await expect(page).toHaveURL(/\/login/, { timeout: 10000 })
    })
})
