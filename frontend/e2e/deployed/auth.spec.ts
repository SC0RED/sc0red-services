import { test, expect } from '@playwright/test'

test.describe('authentication', () => {
    test('dashboard loads with greeting', async ({ page }) => {
        await page.goto('/dashboard')
        await expect(page.getByText(/Good (morning|afternoon|evening)/)).toBeVisible({ timeout: 15000 })
    })

    test('dashboard shows content after loading', async ({ page }) => {
        await page.goto('/dashboard')
        // Wait for dashboard to fully load — greeting confirms data is rendered
        await expect(page.getByText(/Good (morning|afternoon|evening)/)).toBeVisible({ timeout: 15000 })
        // Verify either stats cards or empty state is present
        await expect(page.locator('text=/Companies Analyzed|Run your first analysis/').first()).toBeVisible()
    })

    test('user name appears in sidebar', async ({ page }) => {
        await page.goto('/dashboard')
        const sidebar = page.getByRole('complementary')
        // `.first()` guards a strict-mode flake: during hydration the name text
        // can momentarily match more than one node, which fails strict mode
        // instantly. We only need to confirm the name renders in the sidebar.
        await expect(sidebar.getByText('E2E Test User').first()).toBeVisible({ timeout: 15000 })
    })
})
