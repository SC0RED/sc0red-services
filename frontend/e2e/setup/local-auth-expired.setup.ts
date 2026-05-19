import { test as setup } from '@playwright/test'

import { createIdToken } from '../helpers/create-id-token'
import { createSessionToken } from '../helpers/create-session'

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8001'

/**
 * Creates an authenticated session where the NextAuth cookie is valid
 * but the Cognito ID token inside it has already expired.
 *
 * This is the exact scenario that caused the infinite redirect loop:
 * - Middleware sees a valid NextAuth session
 * - Middleware decodes the idToken and finds exp < now
 * - Middleware redirects to /login
 * - (Old bug: login page checked useSession(), saw "authenticated", showed blank page)
 * - (Fix: login page always renders the form)
 */
setup('create session with expired Cognito token', async ({ page, context }) => {
    const timestamp = Date.now()
    const email = `e2e-expired-${timestamp}@sc0red-services-test.com`

    // 1. Register a real user (needed so the user exists in DynamoDB)
    const registerResponse = await page.request.post(`${BACKEND_URL}/api/auth/register`, {
        data: {
            name: 'E2E Expired User',
            email,
            password: 'TestPass123!',
            orgName: `E2E Expired Org ${timestamp}`,
        },
    })

    if (!registerResponse.ok()) {
        const body = await registerResponse.text()
        throw new Error(`Register failed (${registerResponse.status()}): ${body}`)
    }
    const { user } = await registerResponse.json()

    // 2. Create an ID token that expired 1 hour ago
    const expiredIdToken = await createIdToken(
        {
            id: user.id,
            email,
            name: 'E2E Expired User',
            orgId: user.orgId,
            role: 'admin',
        },
        { expiresIn: '-1h' }
    )

    // 3. Create a valid NextAuth session cookie containing the expired ID token
    //    The NextAuth cookie itself is still valid (8h), but the Cognito token
    //    inside it has expired — this is what middleware checks.
    const sessionToken = await createSessionToken({
        id: user.id,
        email,
        name: 'E2E Expired User',
        orgId: user.orgId,
        role: 'admin',
        idToken: expiredIdToken,
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

    // 5. Save storage state (do NOT verify dashboard — it should redirect to login)
    await context.storageState({ path: './playwright/.auth/local-expired.json' })
})
