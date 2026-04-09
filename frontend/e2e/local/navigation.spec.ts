import { test, expect } from '@playwright/test'

test.describe('navigation — unauthenticated', () => {
    test('landing page renders', async ({ page }) => {
        await page.goto('/')
        await expect(page.getByText('Know Your AI Risk')).toBeVisible()
    })

    test('landing page has sign in and get started links', async ({ page }) => {
        await page.goto('/')
        await expect(page.getByRole('link', { name: 'Sign In' }).first()).toBeVisible()
        await expect(page.getByRole('link', { name: 'Get Started' }).first()).toBeVisible()
    })

    test('sign in link navigates to login', async ({ page }) => {
        await page.goto('/')
        await page.getByRole('link', { name: 'Sign In' }).first().click()
        await expect(page).toHaveURL(/\/login/)
    })

    test('protected routes redirect to login', async ({ page }) => {
        await page.goto('/scan/new')
        await expect(page).toHaveURL(/\/login/, { timeout: 10000 })
    })
})
