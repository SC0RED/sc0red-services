# Cognito User Management Migration Plan

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Multi-user orgs | Yes, with invitation flow | PE firms have multiple analysts |
| UI approach | Custom UI (not Cognito Hosted UI) | Full control over look-and-feel |
| MFA | Off now, designed for future TOTP | Cognito supports enabling without code changes |
| Social login | Off now, designed for future Google/Microsoft | Cognito supports adding identity providers later |
| Existing users | Bulk-import via migration Lambda | Transparent — users don't know migration happened |
| Deployment target | Real AWS account | Not LocalStack (Cognito has limited LocalStack support) |

---

## Architecture Change

```
CURRENT                                    AFTER COGNITO
─────────                                  ─────────────
Frontend                                   Frontend
  NextAuth CredentialsProvider               NextAuth CredentialsProvider
    → calls backend /api/auth/login            → calls Cognito SDK directly
    → backend returns user object               → Cognito returns RS256 JWT
  serverToken.ts signs HS256 JWT             serverToken.ts extracts Cognito idToken
    → backend validates with shared secret     → backend validates with JWKS public keys

Backend                                    Backend
  auth_middleware: HS256 + NEXTAUTH_SECRET    auth_middleware: RS256 + Cognito JWKS
  auth_handlers: bcrypt login/register       cognito_client: invite/org management
  user_repository: passwords in DynamoDB     user_repository: no passwords, has cognito_sub

Infrastructure                             Infrastructure
  No Cognito resources                       Cognito User Pool + App Client
  NEXTAUTH_SECRET shared FE↔BE               Migration Lambda trigger
                                             NEXTAUTH_SECRET only for NextAuth sessions
```

---

## Phase 1: CDK Infrastructure (additive, zero user impact)

Deploy Cognito User Pool alongside existing auth. Nothing consumes it yet.

### Files

| Action | File | What Changes |
|---|---|---|
| **Create** | `infrastructure/stacks/cognito_construct.py` | Cognito User Pool: email sign-in, custom attributes (`custom:org_id`, `custom:role`, `custom:legacy_user_id`), password policy (8+ chars, upper+lower+digits), email verification, `USER_PASSWORD_AUTH` + `USER_SRP_AUTH` flows, migration Lambda trigger slot |
| **Create** | `infrastructure/stacks/cognito_construct.py` | Cognito App Client: no secret (public SPA client), 1h ID/access token validity, 30d refresh token, prevent user enumeration errors |
| **Modify** | `infrastructure/stacks/janus_stack.py` | Instantiate `CognitoConstruct`, pass `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`, `COGNITO_REGION` as env vars to both Lambdas. Keep `NEXTAUTH_SECRET` (dual-stack). Add CfnOutputs for pool ID, client ID |

### Cognito User Pool Configuration

```python
# Custom attributes
custom:org_id          # string, mutable — org UUID
custom:role            # string, mutable — "admin" | "analyst" | "viewer"
custom:legacy_user_id  # string, immutable — maps to DynamoDB USER# pk

# Password policy
min_length = 8
require_lowercase = True
require_uppercase = True
require_digits = True
require_symbols = False
temp_password_validity = 7 days  # for invitations

# Token validity
id_token = 1 hour
access_token = 1 hour
refresh_token = 30 days

# Auth flows
USER_PASSWORD_AUTH  # needed for migration Lambda
USER_SRP_AUTH       # for future security upgrade

# Other
self_sign_up = True
auto_verify_email = True
account_recovery = EMAIL_ONLY
mfa = OFF (designed for future TOTP enablement)
prevent_user_existence_errors = True
```

### Rollback
Delete the construct instantiation from `janus_stack.py`, `cdk deploy` removes the pool. No consumers affected.

---

## Phase 2: Migration Lambda (transparent user import)

When an existing DynamoDB user logs in through Cognito for the first time, the migration Lambda validates their bcrypt password and creates the Cognito user. User experiences no difference.

### Files

| Action | File | What Changes |
|---|---|---|
| **Create** | `backend/src/handlers/cognito_migration_trigger.py` | Handles `UserMigration_Authentication`: look up user by email in DynamoDB → bcrypt verify → return user attributes with `finalUserStatus=CONFIRMED`, `messageAction=SUPPRESS` |
| **Create** | `backend/src/handlers/cognito_migration_trigger.py` | Handles `UserMigration_ForgotPassword`: look up user by email → return attributes so Cognito sends reset code |
| **Create** | `backend/src/handlers/cognito_migration_entry.py` | Thin Lambda entry point: instantiates DynamoDB provider, delegates to trigger handler |
| **Modify** | `infrastructure/stacks/cognito_construct.py` | Create migration Lambda (128MB, 10s timeout), grant DynamoDB read access, wire as `user_migration` trigger |

### Migration Lambda Logic

```
UserMigration_Authentication trigger:
  1. event["userName"] = email, event["request"]["password"] = plaintext
  2. DynamoDB lookup: GSI4 query EMAIL#{email}
  3. If not found → raise exception (Cognito returns "user not found")
  4. bcrypt.checkpw(password, stored_hash)
  5. If invalid → raise exception (Cognito returns "incorrect password")
  6. Set event["response"]["userAttributes"]:
     - email (verified)
     - name
     - custom:org_id
     - custom:role
     - custom:legacy_user_id (DynamoDB user ID)
  7. Set finalUserStatus = "CONFIRMED" (skip email verification)
  8. Set messageAction = "SUPPRESS" (no welcome email)
  9. Return event

UserMigration_ForgotPassword trigger:
  1. Look up user by email in DynamoDB
  2. If found → populate userAttributes with email_verified=true
  3. Return event (Cognito sends reset code)
  4. If not found → raise exception
```

### Rollback
Remove trigger from User Pool via CDK. Migration stops but no harm — existing DynamoDB auth still works since frontend hasn't switched.

---

## Phase 3: Backend Auth — Dual RS256/HS256 Validation

Backend accepts BOTH Cognito RS256 tokens and legacy HS256 tokens. Enables gradual frontend rollout.

### Files

| Action | File | What Changes |
|---|---|---|
| **Rewrite** | `backend/src/handlers/auth_middleware.py` | Add `CognitoJWKSValidator`: fetches JWKS from Cognito endpoint, caches at module level. `validate_token()` tries RS256 first, falls back to HS256 |
| **Create** | `backend/src/handlers/cognito_client.py` | Wrapper around `boto3 cognito-idp`: `create_user()`, `invite_user()`, `admin_set_password()`, `list_users_in_group()` |
| **Create** | `backend/src/handlers/invitation_handlers.py` | `handle_invite_member`, `handle_accept_invite`, `handle_list_members`, `handle_remove_member` |
| **Modify** | `backend/src/handlers/auth_handlers.py` | `handle_register` now ALSO creates user in Cognito (dual-write during transition) |
| **Modify** | `backend/src/handlers/api_gateway_handler.py` | Add routes: `POST /api/org/invite`, `POST /api/auth/accept-invite`, `GET /api/org/members`, `DELETE /api/org/members/{user_id}` |
| **Modify** | `backend/src/repositories/dynamodb/user_repository.py` | Add `cognito_sub` field, invitation CRUD methods, `find_by_cognito_sub()` |
| **Modify** | `backend/src/repositories/dynamodb/provider.py` | Add `create_invitation_repository()` |
| **Add dep** | `backend/pyproject.toml` | `cryptography>=42.0` (for PyJWT RS256 key parsing) |

### Auth Middleware Dual Validation

```python
def validate_token(authorization: str) -> AuthContext:
    token = authorization[7:]  # strip "Bearer "

    # Try Cognito RS256 first
    try:
        payload = cognito_validator.validate(token)
        return AuthContext(
            user_id=payload.get("custom:legacy_user_id") or payload["sub"],
            org_id=payload["custom:org_id"],
            email=payload.get("email", ""),
            role=payload.get("custom:role", "analyst"),
            name=payload.get("name", ""),
        )
    except InvalidTokenError:
        pass  # Not a Cognito token — try legacy

    # Fallback to legacy HS256
    payload = jwt.decode(token, NEXTAUTH_SECRET, algorithms=["HS256"])
    return AuthContext(
        user_id=payload["id"],
        org_id=payload["orgId"],
        email=payload.get("email", ""),
        role=payload.get("role", "analyst"),
        name=payload.get("name", ""),
    )
```

**Key design**: `AuthContext` is identical regardless of token type. Every handler downstream is unaffected — they receive the same `AuthContext`.

### JWKS Caching

```python
_JWKS_CACHE: dict[str, Any] | None = None  # module-level, survives Lambda container reuse

class CognitoJWKSValidator:
    def __init__(self, region, pool_id, client_id):
        self._issuer = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"
        self._jwks_url = f"{self._issuer}/.well-known/jwks.json"
        self._client_id = client_id

    def _get_keys(self):
        global _JWKS_CACHE
        if _JWKS_CACHE is None:
            _JWKS_CACHE = httpx.get(self._jwks_url).json()
        return _JWKS_CACHE

    def validate(self, token):
        keys = self._get_keys()
        # Match kid from token header to JWKS key
        # Decode with RS256, verify audience=client_id, issuer=pool_url
```

### Invitation Flow

```
Admin (role=admin) calls POST /api/org/invite {email, role}
  → Validate caller.role == "admin"
  → Create DynamoDB record: pk=ORG#{org_id}, sk=INVITE#{id}
    Fields: email, role, invited_by, status=pending, expires_at
  → Call cognito_client.invite_user(email, org_id, role)
    → Cognito admin_create_user with temp password, sends email
  → Return invitation ID

Invited user receives email with temp password
  → Visits /accept-invite?email=...
  → Enters temp password + new password
  → Frontend calls Cognito signIn(email, tempPassword)
    → Cognito returns NEW_PASSWORD_REQUIRED challenge
  → Frontend calls completeNewPasswordChallenge(newPassword)
  → Backend POST /api/auth/accept-invite
    → Creates USER#{id} record with same org_id
    → Updates invitation status=accepted
  → User redirected to /login
```

### Rollback
Remove RS256 path from `validate_token()`. HS256 keeps working. Invitation endpoints can be left deployed (unused).

---

## Phase 4: Frontend Auth — Cognito SDK with Custom UI

The user-facing switch. Login/signup call Cognito directly. HS256 bridge eliminated.

### Files

| Action | File | What Changes |
|---|---|---|
| **Add dep** | `frontend/package.json` | `amazon-cognito-identity-js` |
| **Create** | `frontend/src/lib/auth/cognitoClient.ts` | Initialize `CognitoUserPool`, export: `signIn()`, `signUp()`, `confirmSignUp()`, `forgotPassword()`, `confirmForgotPassword()`, `completeNewPasswordChallenge()`, `getIdToken()`, `refreshSession()` |
| **Rewrite** | `frontend/src/lib/auth/authOptions.ts` | CredentialsProvider `authorize()` calls `cognitoClient.signIn()` → decodes ID token → returns user with `idToken`. JWT callback stores `idToken`. |
| **Simplify** | `frontend/src/lib/api/serverToken.ts` | `getBackendToken()` extracts Cognito `idToken` from NextAuth JWT. Remove `jsonwebtoken` import. |
| **Modify** | `frontend/src/app/login/page.tsx` | Keep UI. Add "Forgot password?" link. `handleSubmit` still calls `signIn('credentials', ...)` — NextAuth delegates to Cognito internally |
| **Modify** | `frontend/src/app/signup/page.tsx` | Rewrite: POST backend `/api/auth/signup` (creates org + Cognito user) → show email verification code input → `confirmSignUp()` → auto-login |
| **Create** | `frontend/src/app/forgot-password/page.tsx` | Step 1: email → `forgotPassword()`. Step 2: code + new password → `confirmForgotPassword()`. Step 3: success |
| **Create** | `frontend/src/app/accept-invite/page.tsx` | Enter temp password + new password → `signIn()` triggers challenge → `completeNewPasswordChallenge()` |
| **Modify** | `frontend/src/types/next-auth.d.ts` | Add `idToken?: string` to JWT interface |

### Environment Variables (new)

```
NEXT_PUBLIC_COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
NEXT_PUBLIC_COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
NEXT_PUBLIC_COGNITO_REGION=us-east-1
NEXTAUTH_SECRET=...  # still needed for NextAuth session encryption
```

### Token Flow After Migration

```
User logs in → Cognito SDK authenticates
  → Cognito returns: idToken (RS256), accessToken, refreshToken
  → NextAuth stores idToken in its JWT
  → serverToken.ts extracts idToken from session
  → backendFetch sends: Authorization: Bearer {cognitoIdToken}
  → Backend validates RS256 against JWKS
  → Extracts custom:org_id → builds AuthContext
  → Handler validates org_id match on resources (unchanged)
```

### Rollback
Revert `authOptions.ts` and `serverToken.ts` to HS256 versions. Backend dual-validation ensures old tokens work. Feature flag: if `NEXT_PUBLIC_COGNITO_USER_POOL_ID` is empty, fall back to legacy provider.

---

## Phase 5: Cleanup (point of no return)

Remove legacy auth after confirming all users migrated.

### Pre-conditions
- All DynamoDB users have corresponding Cognito users (verify count)
- Zero "HS256 fallback" log entries for 2+ weeks
- Keep DynamoDB `password_hash` data for 30 days as safety net

### Files

| Action | File | What Changes |
|---|---|---|
| **Modify** | `backend/src/handlers/auth_middleware.py` | Remove HS256 fallback, remove `NEXTAUTH_SECRET` usage |
| **Modify** | `backend/src/handlers/auth_handlers.py` | Remove `handle_login`. Refactor or delete `handle_register` |
| **Modify** | `backend/src/handlers/api_gateway_handler.py` | Remove `POST /api/auth/login` route |
| **Modify** | `backend/src/repositories/dynamodb/user_repository.py` | Remove `verify_password()`, remove `password_hash` from schema |
| **Modify** | `infrastructure/stacks/janus_stack.py` | Remove `NEXTAUTH_SECRET` from Lambda env vars |
| **Remove dep** | `frontend/package.json` | Remove `jsonwebtoken` |
| **Remove dep** | `backend/pyproject.toml` | Remove `bcrypt` (migration Lambda keeps its own copy) |

---

## Data Model Changes

### New: Invitation Records (same DynamoDB single table)

```
pk = ORG#{org_id}
sk = INVITE#{invite_id}
GSI4PK = EMAIL#{email}
GSI4SK = INVITE#{invite_id}

Fields:
  id          — UUID
  org_id      — org UUID
  email       — invited email
  role        — "analyst" | "viewer"
  invited_by  — admin user_id
  status      — "pending" | "accepted" | "expired"
  cognito_sub — Cognito user UUID (set after Cognito creates user)
  created_at  — ISO timestamp
  expires_at  — ISO timestamp (7 days from creation)
```

### Modified: User Record

```
Existing fields:  id, email, name, org_id, role, password_hash
New field:        cognito_sub (Cognito user UUID)
Deprecated:       password_hash (removed in Phase 5)
```

### Unchanged (zero changes needed)

- Company records — `org_id` validation continues unchanged
- Scan records — `org_id` validation continues unchanged
- Assessment records — no org awareness (accessed via company)
- Worker SQS messages — carry `org_id` directly, no token validation
- All 30+ handler `org_id` checks — receive same `AuthContext` from middleware
- All DynamoDB GSIs — no new GSIs needed

---

## Multi-User Org Model

### Org Roles

| Role | Can analyze | Can view | Can invite | Can remove members | Can delete org |
|---|---|---|---|---|---|
| admin | Yes | Yes | Yes | Yes | Yes |
| analyst | Yes | Yes | No | No | No |
| viewer | No | Yes | No | No | No |

### Role Enforcement

- **Frontend**: sidebar shows/hides "Invite Members" based on `session.user.role`
- **Backend**: `handle_invite_member` checks `authentication.role == "admin"`
- **Cognito**: role stored as `custom:role` custom attribute, included in ID token

---

## What Does NOT Change

| Component | Why Unchanged |
|---|---|
| Worker Lambda auth | SQS messages carry `org_id` directly from API Lambda. No JWT validation. |
| Pipeline steps | Receive `org_id` via `JanusEvent` from `FactoryManager`. No auth awareness. |
| DynamoDB single-table design | Same pk/sk patterns. No new GSIs. |
| Frontend route protection middleware | `withAuth` from NextAuth still works (checks session presence). |
| All 30+ `org_id` handler checks | `AuthContext` shape is identical from both RS256 and HS256 paths. |
| CORS configuration | Same headers, same allowed origins. |
| API Gateway | No native Cognito authorizer. JWT validated in Lambda code. |

---

## Implementation Sequence

```
Phase 1 (CDK)           Zero user impact — purely additive
    ↓
Phase 2 (Migration Λ)   Zero user impact — trigger ready, not invoked
    ↓
Phase 3 (Backend)        Zero user impact — dual validation, new endpoints unused
    ↓
Phase 4 (Frontend)       USER-FACING SWITCH — login now goes through Cognito
    ↓
Phase 5 (Cleanup)        Point of no return — legacy auth removed
```

Each phase: one PR, deployed and tested before moving to next.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| JWKS cold start latency (~150ms) | First request per Lambda container slower | Cache at module level; consider provisioned concurrency for prod |
| Cognito email sandbox (50/day) | Can't send invitations | Request SES production access before Phase 3 deploy |
| Existing sessions invalidated on Phase 4 | Users must re-login | Dual validation keeps old tokens valid for 30 days |
| Migration Lambda race condition | Duplicate user creation attempt | Cognito handles gracefully (returns existing user) |
| `custom:org_id` missing from token | 401 on every request | Migration Lambda sets it; new signups set it; tested in Phase 2 |
| Cognito custom attribute limit | 50 max, 2048 chars each | We use 3 attributes, all short strings — well within limits |
| Password reset for migrated users | User might not have Cognito password yet | Migration Lambda handles `ForgotPassword` trigger — creates Cognito user on reset flow too |
