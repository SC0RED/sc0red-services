import { vi, describe, it, expect, beforeEach } from 'vitest'

// Mock the Cognito client so importing authOptions doesn't construct a real
// CognitoUserPool (which validates env-derived pool ids), and so we can drive
// the refresh path deterministically.
vi.mock('@/lib/auth/cognitoClient', () => ({
    signInWithCognito: vi.fn(),
    refreshCognitoSession: vi.fn(),
}))

import { refreshCognitoSession } from '@/lib/auth/cognitoClient'
import { authOptions } from '@/lib/auth/authOptions'

const mockRefresh = vi.mocked(refreshCognitoSession)

// Build a fake idToken whose payload carries the given `exp` (the callback
// decodes the refreshed idToken to read its new expiry).
function makeIdToken(exp: number): string {
    const payload = Buffer.from(JSON.stringify({ exp })).toString('base64url')
    return `header.${payload}.sig`
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const jwt = authOptions.callbacks!.jwt as any
const nowSec = () => Math.floor(Date.now() / 1000)

describe('authOptions jwt callback — Cognito idToken refresh', () => {
    beforeEach(() => vi.clearAllMocks())

    it('stores idToken + refreshToken + expiry on initial sign-in', async () => {
        const user = {
            id: 'u1',
            orgId: 'o1',
            role: 'admin',
            idToken: 'id1',
            refreshToken: 'r1',
            idTokenExpiresAt: nowSec() + 3600,
        }
        const token = await jwt({ token: {}, user })
        expect(token.idToken).toBe('id1')
        expect(token.refreshToken).toBe('r1')
        expect(token.idTokenExpiresAt).toBe(user.idTokenExpiresAt)
        expect(token.error).toBeUndefined()
        expect(mockRefresh).not.toHaveBeenCalled()
    })

    it('passes a still-fresh token through without refreshing', async () => {
        const token = await jwt({
            token: { idToken: 'id1', refreshToken: 'r1', idTokenExpiresAt: nowSec() + 3600 },
        })
        expect(token.idToken).toBe('id1')
        expect(mockRefresh).not.toHaveBeenCalled()
    })

    it('passes through (no refresh, no error) when expiry is unknown', async () => {
        // Sessions minted before this change shipped, and e2e mock sessions,
        // carry idToken but no idTokenExpiresAt/refreshToken. They must pass
        // through untouched — NOT get flagged as a refresh error (which would
        // bounce every authenticated request to /login).
        const token = await jwt({ token: { idToken: 'legacy' } })
        expect(token.idToken).toBe('legacy')
        expect(token.error).toBeUndefined()
        expect(mockRefresh).not.toHaveBeenCalled()
    })

    it('refreshes an expired token and updates idToken + expiry', async () => {
        const newExp = nowSec() + 3600
        mockRefresh.mockResolvedValue({ idToken: makeIdToken(newExp), accessToken: 'a2' })
        const token = await jwt({
            token: { idToken: 'old', refreshToken: 'r1', idTokenExpiresAt: nowSec() - 10 },
        })
        expect(mockRefresh).toHaveBeenCalledWith('r1')
        expect(token.idToken).toBe(makeIdToken(newExp))
        expect(token.idTokenExpiresAt).toBe(newExp)
        expect(token.error).toBeUndefined()
    })

    it('refreshes when within the skew window (about to expire)', async () => {
        const newExp = nowSec() + 3600
        mockRefresh.mockResolvedValue({ idToken: makeIdToken(newExp), accessToken: 'a2' })
        // 30s out — inside the 60s skew window → should refresh
        await jwt({ token: { idToken: 'old', refreshToken: 'r1', idTokenExpiresAt: nowSec() + 30 } })
        expect(mockRefresh).toHaveBeenCalled()
    })

    it('sets error when refresh fails (refresh token expired/revoked)', async () => {
        mockRefresh.mockRejectedValue(new Error('NotAuthorizedException'))
        const token = await jwt({
            token: { idToken: 'old', refreshToken: 'r1', idTokenExpiresAt: nowSec() - 10 },
        })
        expect(token.error).toBe('RefreshAccessTokenError')
    })

    it('sets error when expired with no refresh token', async () => {
        const token = await jwt({ token: { idToken: 'old', idTokenExpiresAt: nowSec() - 10 } })
        expect(token.error).toBe('RefreshAccessTokenError')
        expect(mockRefresh).not.toHaveBeenCalled()
    })

    it('short-circuits (no Cognito call) when already in the refresh-error state', async () => {
        const token = await jwt({
            token: {
                idToken: 'old',
                refreshToken: 'r1',
                idTokenExpiresAt: nowSec() - 10,
                error: 'RefreshAccessTokenError',
            },
        })
        expect(token.error).toBe('RefreshAccessTokenError')
        expect(mockRefresh).not.toHaveBeenCalled()
    })

    it('treats a refreshed token with no exp as a refresh failure', async () => {
        // idToken payload without `exp` → Number(undefined) = NaN → must error, not loop
        const noExpToken = `header.${Buffer.from(JSON.stringify({ sub: 'x' })).toString('base64url')}.sig`
        mockRefresh.mockResolvedValue({ idToken: noExpToken, accessToken: 'a2' })
        const token = await jwt({
            token: { idToken: 'old', refreshToken: 'r1', idTokenExpiresAt: nowSec() - 10 },
        })
        expect(token.error).toBe('RefreshAccessTokenError')
    })
})
