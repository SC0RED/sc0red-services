## ADDED Requirements

### Requirement: `/settings` route exists for user profile and org info

The webapp SHALL provide an authenticated route at `/settings` that displays the current user's profile information and the organization context. The page SHALL be reachable from the sidebar navigation.

#### Scenario: User navigates to settings

- **WHEN** the user clicks "Settings" in the sidebar
- **THEN** they navigate to `/settings` and see sections for Profile, Org info, and a placeholder for Appearance

#### Scenario: Unauthenticated user is redirected

- **WHEN** an unauthenticated user attempts to load `/settings`
- **THEN** they are redirected to `/login` (existing authenticated-layout middleware behavior)

### Requirement: Settings page displays profile information read-only

The Profile section SHALL display the user's display name and email address, sourced from the NextAuth session (which sources from Cognito). Both fields SHALL be displayed as read-only text. A clarifying note SHALL indicate that email/password changes are managed through Cognito-hosted UI (linked from the page).

#### Scenario: Profile shows display name and email

- **WHEN** the user views `/settings`
- **THEN** the Profile section shows their name (from session) and email (from session); both are non-editable

#### Scenario: Profile links to Cognito-hosted password change

- **WHEN** the user clicks "Change password" in the Profile section
- **THEN** the user navigates to the existing Cognito-hosted password reset flow (or the in-app password reset route, whichever is current)

### Requirement: Settings page displays org info with copy-to-clipboard

The Org Info section SHALL display the user's organization ID with a click-to-copy button, and the user's role (admin / member). The copy button SHALL provide visual + toast feedback on successful copy.

#### Scenario: User copies org_id

- **WHEN** the user clicks the "Copy" button next to the org_id
- **THEN** the org_id is copied to the clipboard, the button briefly shows a confirmation icon, and a toast appears with "Copied org ID"

#### Scenario: Role displays with badge styling

- **WHEN** the user views `/settings` and their role is `admin`
- **THEN** an "Admin" badge renders next to the role label using the existing badge component

### Requirement: Logout is accessible from the settings page

The Settings page SHALL provide a clearly-labelled "Sign out" button that triggers the existing logout flow. (Whether logout ALSO appears elsewhere — e.g., sidebar bottom — is preserved per the existing implementation.)

#### Scenario: User signs out from settings

- **WHEN** the user clicks "Sign out" on `/settings`
- **THEN** the existing NextAuth signout flow runs and the user is redirected to `/login`
