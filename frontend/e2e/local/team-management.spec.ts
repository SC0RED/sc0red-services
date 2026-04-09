import { test, expect } from '@playwright/test'

test.describe('team management', () => {
    test('team page loads', async ({ page }) => {
        await page.goto('/team')
        await expect(page.getByText('Team Members')).toBeVisible()
    })

    test('invite form is visible for admin', async ({ page }) => {
        await page.goto('/team')
        await expect(page.getByText('Invite Team Member')).toBeVisible()
    })
})
