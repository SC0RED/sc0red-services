import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'

// Set pool env BEFORE the (dynamic) import — cognitoClient constructs a
// CognitoUserPool at module load and validates the pool-id format. cognitoClient
// is imported dynamically inside each test so this runs first.
process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID = 'us-east-1_testpool'
process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID = 'testclientid'

describe('refreshCognitoSession', () => {
    beforeEach(() => vi.clearAllMocks())
    afterEach(() => vi.unstubAllGlobals())

    it('exchanges the refresh token for a fresh idToken via REFRESH_TOKEN_AUTH', async () => {
        const fetchMock = vi.fn().mockResolvedValue({
            ok: true,
            json: async () => ({
                AuthenticationResult: { IdToken: 'newid', AccessToken: 'newacc' },
            }),
        })
        vi.stubGlobal('fetch', fetchMock)

        const { refreshCognitoSession } = await import('@/lib/auth/cognitoClient')
        const result = await refreshCognitoSession('refresh-1')

        expect(result).toEqual({ idToken: 'newid', accessToken: 'newacc' })
        // region derived from the pool id, public client id, correct target
        expect(fetchMock).toHaveBeenCalledWith(
            'https://cognito-idp.us-east-1.amazonaws.com/',
            expect.objectContaining({
                method: 'POST',
                headers: expect.objectContaining({
                    'X-Amz-Target': 'AWSCognitoIdentityProviderService.InitiateAuth',
                }),
            })
        )
        const body = JSON.parse(fetchMock.mock.calls[0][1].body)
        expect(body).toMatchObject({
            AuthFlow: 'REFRESH_TOKEN_AUTH',
            ClientId: 'testclientid',
            AuthParameters: { REFRESH_TOKEN: 'refresh-1' },
        })
    })

    it('throws when Cognito returns a non-OK response', async () => {
        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue({ ok: false, status: 400, text: async () => 'NotAuthorizedException' })
        )
        const { refreshCognitoSession } = await import('@/lib/auth/cognitoClient')
        await expect(refreshCognitoSession('bad')).rejects.toThrow(/Cognito refresh failed \(400\)/)
    })

    it('throws when the response lacks tokens', async () => {
        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue({ ok: true, json: async () => ({ AuthenticationResult: {} }) })
        )
        const { refreshCognitoSession } = await import('@/lib/auth/cognitoClient')
        await expect(refreshCognitoSession('r')).rejects.toThrow(/no tokens/)
    })
})
