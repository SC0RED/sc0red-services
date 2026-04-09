import { test, expect } from '@playwright/test'

test.describe('team management', () => {
    test('team page loads', async ({ page }) => {
        await page.goto('/team')
        await expect(page.getByText('Team Members')).toBeVisible()
    })

    test('invite form is visible for admin', async ({ page }) => {
        await page.goto('/team')
        await expect(page.getByText('Invite Team Member')).toBeVisible()
        await expect(page.getByPlaceholder(/email/i)).toBeVisible()
    })

    test('invite with invalid email shows error', async ({ page }) => {
        await page.goto('/team')

        const emailInput = page.getByPlaceholder(/email/i)
        await emailInput.fill('')
        await page.getByRole('button', { name: /send invite/i }).click()

        // Should show validation or error
        await expect(page.getByText(/required|invalid|error/i)).toBeVisible({ timeout: 5000 })
    })
})
