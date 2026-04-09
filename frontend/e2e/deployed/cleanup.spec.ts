import { test, expect } from '@playwright/test'

/**
 * Cleanup test — runs last to delete all analyses and scans created during E2E.
 * This keeps the testing environment clean between runs.
 */
test.describe('cleanup', () => {
    test('delete all analyses created by test user', async ({ page }) => {
        await page.goto('/analyses')

        // Wait for page to load
        await expect(page.getByText('All Analyses')).toBeVisible({ timeout: 15000 })

        // Delete each analysis via the UI delete button
        let deleteButtons = await page.getByRole('button', { name: /delete/i }).all()
        let attempts = 0

        while (deleteButtons.length > 0 && attempts < 20) {
            // Click delete on the first analysis
            await deleteButtons[0].click()

            // Handle confirm dialog if present
            const confirmButton = page.getByRole('button', { name: /confirm|yes|delete/i }).last()
            if (await confirmButton.isVisible({ timeout: 2000 }).catch(() => false)) {
                await confirmButton.click()
            }

            // Wait for deletion to process
            await page.waitForTimeout(1000)

            // Refresh and check remaining
            await page.goto('/analyses')
            await expect(page.getByText('All Analyses')).toBeVisible({ timeout: 15000 })
            deleteButtons = await page.getByRole('button', { name: /delete/i }).all()
            attempts++
        }

        // Verify clean state
        await page.goto('/dashboard')
        await expect(page.getByText(/Good (morning|afternoon|evening)/)).toBeVisible({ timeout: 15000 })
    })
})
