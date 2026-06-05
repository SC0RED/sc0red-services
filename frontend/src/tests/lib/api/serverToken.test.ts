import { vi, describe, it, expect, beforeEach } from 'vitest'

vi.mock('next-auth/jwt', () => ({ getToken: vi.fn() }))
vi.mock('next/headers', () => ({
    cookies: vi.fn(async () => ({ getAll: () => [] })),
    headers: vi.fn(async () => new Map<string, string>()),
}))

import { getToken } from 'next-auth/jwt'

import { getBackendToken } from '@/lib/api/serverToken'

const mockGetToken = vi.mocked(getToken)

describe('getBackendToken', () => {
    beforeEach(() => vi.clearAllMocks())

    it('returns the idToken when present and there is no refresh error', async () => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        mockGetToken.mockResolvedValue({ idToken: 'id1' } as any)
        expect(await getBackendToken()).toBe('id1')
    })

    it('returns null when the jwt is flagged with a refresh error', async () => {
        mockGetToken.mockResolvedValue({
            idToken: 'stale',
            error: 'RefreshAccessTokenError',
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
        } as any)
        expect(await getBackendToken()).toBeNull()
    })

    it('returns null when there is no token at all', async () => {
        mockGetToken.mockResolvedValue(null)
        expect(await getBackendToken()).toBeNull()
    })
})
