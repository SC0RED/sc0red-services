import { test as setup, expect } from '@playwright/test'

import { createIdToken } from '../helpers/create-id-token'
import { createSessionToken } from '../helpers/create-session'

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8001'

setup('register and create authenticated session', async ({ page, context }) => {
    const timestamp = Date.now()
    const email = `e2e-${timestamp}@janus-test.com`

    // 1. Register via backend API (no Cognito in E2E mode)
    const registerResponse = await page.request.post(`${BACKEND_URL}/api/auth/register`, {
        data: {
            name: 'E2E Test User',
            email,
            password: 'TestPass123!',
            orgName: `E2E Org ${timestamp}`,
        },
    })

    expect(registerResponse.ok()).toBeTruthy()
    const { user } = await registerResponse.json()

    // 2. Create an RS256 ID token (same as backend E2E script)
    const idToken = await createIdToken({
        id: user.id,
        email,
        name: 'E2E Test User',
        orgId: user.orgId,
        role: 'admin',
    })

    // 3. Create a NextAuth-compatible encrypted session cookie
    const sessionToken = await createSessionToken({
        id: user.id,
        email,
        name: 'E2E Test User',
        orgId: user.orgId,
        role: 'admin',
        idToken,
    })

    // 4. Set the session cookie
    await context.addCookies([
        {
            name: 'next-auth.session-token',
            value: sessionToken,
            domain: 'localhost',
            path: '/',
            httpOnly: true,
            secure: false,
            sameSite: 'Lax',
        },
    ])

    // 5. Verify authenticated access works
    await page.goto('/dashboard')
    await expect(page.getByText(/Good (morning|afternoon|evening)/)).toBeVisible({ timeout: 15000 })

    // 6. Save storage state for all local tests
    await context.storageState({ path: './playwright/.auth/local.json' })
})
