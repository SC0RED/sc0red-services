import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const sendMock = vi.fn()

vi.mock('@aws-sdk/client-secrets-manager', () => ({
    SecretsManagerClient: vi.fn().mockImplementation(() => ({
        send: sendMock,
    })),
    GetSecretValueCommand: vi.fn().mockImplementation((input: unknown) => ({ input })),
}))

import { _resetSecretCacheForTests, readSigningSecret } from '../src/secretSource'

const ARN = 'arn:aws:secretsmanager:us-east-1:1:secret:sc0red-services/dev/pdf-token-AbCdEf'

beforeEach(() => {
    sendMock.mockReset()
    _resetSecretCacheForTests()
    process.env.PDF_TOKEN_SECRET_ARN = ARN
})

afterEach(() => {
    delete process.env.PDF_TOKEN_SECRET_ARN
})

describe('readSigningSecret', () => {
    it('resolves the secret from Secrets Manager on first call', async () => {
        sendMock.mockResolvedValueOnce({ SecretString: 'fetched-secret' })
        const secret = await readSigningSecret()
        expect(secret).toBe('fetched-secret')
        expect(sendMock).toHaveBeenCalledTimes(1)
    })

    it('caches the resolved secret across requests (one fetch per cold start)', async () => {
        sendMock.mockResolvedValueOnce({ SecretString: 'cached-secret' })
        await readSigningSecret()
        await readSigningSecret()
        await readSigningSecret()
        expect(sendMock).toHaveBeenCalledTimes(1)
    })

    it('throws when the ARN env var is missing', async () => {
        delete process.env.PDF_TOKEN_SECRET_ARN
        await expect(readSigningSecret()).rejects.toThrow(/PDF_TOKEN_SECRET_ARN is not set/)
    })

    it('throws when Secrets Manager returns an empty value', async () => {
        sendMock.mockResolvedValueOnce({ SecretString: '' })
        await expect(readSigningSecret()).rejects.toThrow(/empty SecretString/)
    })

    it('propagates the AWS SDK error when the API call fails', async () => {
        sendMock.mockRejectedValueOnce(new Error('AccessDenied'))
        await expect(readSigningSecret()).rejects.toThrow(/AccessDenied/)
    })

    it('treats undefined SecretString the same as empty (no half-filled cache)', async () => {
        sendMock.mockResolvedValueOnce({})
        await expect(readSigningSecret()).rejects.toThrow(/empty SecretString/)
        // After failure, second call should also fail (cache not poisoned).
        sendMock.mockResolvedValueOnce({ SecretString: 'recovered' })
        const secret = await readSigningSecret()
        expect(secret).toBe('recovered')
    })
})
