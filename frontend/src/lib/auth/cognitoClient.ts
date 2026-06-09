/**
 * Cognito authentication client using amazon-cognito-identity-js.
 *
 * Wraps the Cognito SDK for direct auth operations from the frontend:
 * signIn, signUp, confirmSignUp, forgotPassword, confirmForgotPassword,
 * and completeNewPasswordChallenge (for invited users).
 */

import {
    AuthenticationDetails,
    CognitoUser,
    CognitoUserAttribute,
    CognitoUserPool,
    CognitoUserSession,
} from 'amazon-cognito-identity-js'

const poolData = {
    UserPoolId: process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID || '',
    ClientId: process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID || '',
}

const userPool = new CognitoUserPool(poolData)

function getCognitoUser(email: string): CognitoUser {
    const user = new CognitoUser({ Username: email, Pool: userPool })
    // USER_PASSWORD_AUTH is required for the migration Lambda trigger.
    // SRP auth (default) never sends the plaintext password to Cognito,
    // so the migration Lambda can't validate bcrypt passwords.
    user.setAuthenticationFlowType('USER_PASSWORD_AUTH')
    return user
}

export interface CognitoSignInResult {
    idToken: string
    accessToken: string
    refreshToken: string
    /** Set when Cognito returns NEW_PASSWORD_REQUIRED challenge */
    challengeName?: string
    /** The CognitoUser object — needed to complete password challenge */
    cognitoUser?: CognitoUser
}

/**
 * Authenticate with email + password via Cognito USER_PASSWORD_AUTH flow.
 *
 * Returns tokens on success. If the user has a temp password (invitation flow),
 * returns challengeName='NEW_PASSWORD_REQUIRED' with the cognitoUser for
 * completing the challenge via completeNewPasswordChallenge().
 */
export function signInWithCognito(email: string, password: string): Promise<CognitoSignInResult> {
    const cognitoUser = getCognitoUser(email)
    const authDetails = new AuthenticationDetails({
        Username: email,
        Password: password,
    })

    return new Promise((resolve, reject) => {
        cognitoUser.authenticateUser(authDetails, {
            onSuccess(session: CognitoUserSession) {
                resolve({
                    idToken: session.getIdToken().getJwtToken(),
                    accessToken: session.getAccessToken().getJwtToken(),
                    refreshToken: session.getRefreshToken().getToken(),
                })
            },
            onFailure(error: Error) {
                reject(error)
            },
            newPasswordRequired() {
                resolve({
                    idToken: '',
                    accessToken: '',
                    refreshToken: '',
                    challengeName: 'NEW_PASSWORD_REQUIRED',
                    cognitoUser,
                })
            },
        })
    })
}

/**
 * Refresh the Cognito session using a refresh token (server-safe).
 *
 * Used by the NextAuth `jwt` callback to mint a fresh idToken before the
 * 1-hour idToken expiry, so server-side `backendFetch` calls never send an
 * expired token. Uses a direct Cognito `InitiateAuth` (`REFRESH_TOKEN_AUTH`)
 * call via `fetch` rather than `amazon-cognito-identity-js`, because this runs
 * in the Node `jwt` callback (no browser storage/runtime). The app client is a
 * public SPA client (no secret), so no `SECRET_HASH` is required. The refresh
 * token itself is unchanged by this flow and remains valid for its 30-day life.
 *
 * The region is derived from the pool id (`<region>_xxxxx`) so no separate
 * region env var is needed.
 */
export async function refreshCognitoSession(
    refreshToken: string
): Promise<{ idToken: string; accessToken: string }> {
    const region = poolData.UserPoolId.split('_')[0]
    const response = await fetch(`https://cognito-idp.${region}.amazonaws.com/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-amz-json-1.1',
            'X-Amz-Target': 'AWSCognitoIdentityProviderService.InitiateAuth',
        },
        body: JSON.stringify({
            AuthFlow: 'REFRESH_TOKEN_AUTH',
            ClientId: poolData.ClientId,
            AuthParameters: { REFRESH_TOKEN: refreshToken },
        }),
    })
    if (!response.ok) {
        const detail = await response.text()
        throw new Error(`Cognito refresh failed (${response.status}): ${detail}`)
    }
    const data = (await response.json()) as {
        AuthenticationResult?: { IdToken?: string; AccessToken?: string }
    }
    const result = data.AuthenticationResult
    if (!result?.IdToken || !result?.AccessToken) {
        throw new Error('Cognito refresh returned no tokens in AuthenticationResult')
    }
    return { idToken: result.IdToken, accessToken: result.AccessToken }
}

/**
 * Complete the NEW_PASSWORD_REQUIRED challenge for invited users.
 */
export function completeNewPasswordChallenge(
    cognitoUser: CognitoUser,
    newPassword: string
): Promise<CognitoSignInResult> {
    return new Promise((resolve, reject) => {
        cognitoUser.completeNewPasswordChallenge(
            newPassword,
            {},
            {
                onSuccess(session: CognitoUserSession) {
                    resolve({
                        idToken: session.getIdToken().getJwtToken(),
                        accessToken: session.getAccessToken().getJwtToken(),
                        refreshToken: session.getRefreshToken().getToken(),
                    })
                },
                onFailure(error: Error) {
                    reject(error)
                },
            }
        )
    })
}

/**
 * Initiate forgot-password flow — sends verification code to email.
 */
export function forgotPassword(email: string): Promise<void> {
    const cognitoUser = getCognitoUser(email)
    return new Promise((resolve, reject) => {
        cognitoUser.forgotPassword({
            onSuccess() {
                resolve()
            },
            onFailure(error: Error) {
                reject(error)
            },
        })
    })
}

/**
 * Confirm forgot-password with verification code and new password.
 */
export function confirmForgotPassword(email: string, code: string, newPassword: string): Promise<void> {
    const cognitoUser = getCognitoUser(email)
    return new Promise((resolve, reject) => {
        cognitoUser.confirmPassword(code, newPassword, {
            onSuccess() {
                resolve()
            },
            onFailure(error: Error) {
                reject(error)
            },
        })
    })
}

/**
 * Sign up a new user with Cognito (self-signup flow).
 * Note: For sc0red Services, signup goes through the backend which creates the org
 * and Cognito user together. This function is available for direct signup
 * if needed in the future.
 */
export function signUpWithCognito(
    email: string,
    password: string,
    name: string,
    orgId: string,
    role: string = 'admin'
): Promise<void> {
    const attributes = [
        new CognitoUserAttribute({ Name: 'email', Value: email }),
        new CognitoUserAttribute({ Name: 'name', Value: name }),
        new CognitoUserAttribute({ Name: 'custom:org_id', Value: orgId }),
        new CognitoUserAttribute({ Name: 'custom:role', Value: role }),
    ]

    return new Promise((resolve, reject) => {
        userPool.signUp(email, password, attributes, [], (error) => {
            if (error) {
                reject(error)
            } else {
                resolve()
            }
        })
    })
}

/**
 * Confirm signup with verification code.
 */
export function confirmSignUp(email: string, code: string): Promise<void> {
    const cognitoUser = getCognitoUser(email)
    return new Promise((resolve, reject) => {
        cognitoUser.confirmRegistration(code, true, (error) => {
            if (error) {
                reject(error)
            } else {
                resolve()
            }
        })
    })
}
