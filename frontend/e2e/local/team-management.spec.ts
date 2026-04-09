import { test, expect } from '@playwright/test'

test.describe('team management', () => {
    test('team page loads', async ({ page }) => {
        await page.goto('/team')
        // Team page should show either member list or invite form
        await expect(page.getByRole('heading', { name: 'Team Management' })).toBeVisible({ timeout: 10000 })
    })
})
