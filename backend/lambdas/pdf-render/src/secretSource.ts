/**
 * Lambda-side secret resolution for the PDF render flow.
 *
 * Resolves `PDF_TOKEN_SECRET` from Secrets Manager at runtime. The Lambda's
 * env carries `PDF_TOKEN_SECRET_ARN` (the ARN of the secret), NOT the
 * cleartext value — that way `lambda:GetFunctionConfiguration` doesn't
 * expose the signing key. The role granted by `pdf_render_construct.py`
 * has `secretsmanager:GetSecretValue` on the specific secret ARN.
 *
 * Module-level cache means we pay the Secrets Manager round-trip once per
 * cold-start container (~30ms). Rotation requires a new container.
 */

import { GetSecretValueCommand, SecretsManagerClient } from '@aws-sdk/client-secrets-manager'

const PDF_TOKEN_SECRET_ARN_ENV = 'PDF_TOKEN_SECRET_ARN'

let cachedSecret: string | null = null
let cachedClient: SecretsManagerClient | null = null

function getClient(): SecretsManagerClient {
    if (cachedClient === null) {
        cachedClient = new SecretsManagerClient({})
    }
    return cachedClient
}

/**
 * Resolve the HMAC signing secret. Cached at the module level for the
 * lifetime of the Lambda container.
 *
 * Throws when:
 *   - `PDF_TOKEN_SECRET_ARN` env var is missing (misconfiguration)
 *   - Secrets Manager returns an error (IAM, network, etc.)
 *   - The secret value is empty
 *
 * Caller (the handler) maps any throw to a 500 with a clear log line.
 */
export async function readSigningSecret(): Promise<string> {
    if (cachedSecret !== null) return cachedSecret

    const arn = process.env[PDF_TOKEN_SECRET_ARN_ENV]
    if (!arn) {
        throw new Error(`${PDF_TOKEN_SECRET_ARN_ENV} is not set on the PDF render Lambda runtime`)
    }

    const response = await getClient().send(new GetSecretValueCommand({ SecretId: arn }))
    const secret = response.SecretString
    if (!secret) {
        throw new Error(`Secrets Manager returned empty SecretString for ${arn}`)
    }

    cachedSecret = secret
    return secret
}

/**
 * Test-only hook to flush the module-level cache between cases.
 * NOT exported from the package boundary — only used by `tests/`.
 */
export function _resetSecretCacheForTests(): void {
    cachedSecret = null
    cachedClient = null
}
