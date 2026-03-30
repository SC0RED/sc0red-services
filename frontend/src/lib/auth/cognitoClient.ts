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

let _userPool: CognitoUserPool | null = null

function getUserPool(): CognitoUserPool {
    if (_userPool) return _userPool

    const userPoolId = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID || ''
    const clientId = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID || ''

    if (!userPoolId || !clientId) {
        throw new Error(
            'Cognito not configured: NEXT_PUBLIC_COGNITO_USER_POOL_ID and NEXT_PUBLIC_COGNITO_CLIENT_ID are required'
        )
    }

    _userPool = new CognitoUserPool({ UserPoolId: userPoolId, ClientId: clientId })
    return _userPool
}

function getCognitoUser(email: string): CognitoUser {
    return new CognitoUser({ Username: email, Pool: getUserPool() })
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
 * Note: For Janus, signup goes through the backend which creates the org
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
