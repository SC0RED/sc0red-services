/**
 * Frontend-side secret resolution for the PDF export flow.
 *
 * The Amplify SSR Lambda reads `PDF_TOKEN_SECRET` and `INTERNAL_API_KEY`
 * directly from `process.env`. The values are injected as Amplify branch
 * env vars by `infrastructure/stacks/amplify_construct.py:create_branch`,
 * sourced from the Secrets Manager secrets that the Python + Node.js
 * Lambdas use.
 *
 * NOTE: this is the deliberate trade-off documented in the review-fixes
 * PR — the API Lambda + render Lambda resolve secrets at runtime via
 * `secretsmanager:GetSecretValue` (so `lambda:GetFunctionConfiguration`
 * doesn't expose them), but the Amplify SSR Lambda's IAM role doesn't
 * have Secrets Manager permission by default. Threading that through
 * Amplify's compute-role infrastructure is its own scope; it's tracked
 * as a follow-up.
 *
 * Practical implication: anyone with Amplify console access can read the
 * secrets via the branch env-var UI. That's a smaller blast radius than
 * the wider `lambda:Get*` IAM role pattern, but real and worth fixing.
 */

const PDF_TOKEN_SECRET_ENVIRONMENT = 'PDF_TOKEN_SECRET'
const INTERNAL_API_KEY_ENVIRONMENT = 'INTERNAL_API_KEY'

/**
 * Resolve the HMAC signing secret used to mint URL tokens for the print
 * route. Throws when the env var isn't set so the caller surfaces a
 * clean 500 instead of a confusing downstream auth failure.
 */
export function readSigningSecret(): string {
    const secret = process.env[PDF_TOKEN_SECRET_ENVIRONMENT]
    if (!secret) {
        throw new Error(`${PDF_TOKEN_SECRET_ENVIRONMENT} is not set on the Amplify SSR runtime`)
    }
    return secret
}

/**
 * Resolve the shared secret for calling the Python backend's
 * `/api/internal/analysis/{id}` endpoint (used by the print page server
 * component to load analysis data on behalf of the headless render).
 */
export function readInternalApiKey(): string {
    const key = process.env[INTERNAL_API_KEY_ENVIRONMENT]
    if (!key) {
        throw new Error(`${INTERNAL_API_KEY_ENVIRONMENT} is not set on the Amplify SSR runtime`)
    }
    return key
}
