## ADDED Requirements

### Requirement: A Connect page presents the customer's MCP server address

The web app SHALL provide an authenticated Connect page (under Settings) that displays the current environment's MCP server address and a one-click Copy control. The address SHALL be read from application config (`mcpServerUrl` on the `/api/config` response), NOT hard-coded and NOT deferred to "ask an administrator", so each environment (dev / testing / production) shows its own correct endpoint. The page SHALL state that the customer signs in with sc0red when their client prompts (OAuth), with nothing to copy or store beyond the address.

#### Scenario: Customer copies the environment's server address
- **WHEN** a signed-in customer opens the Connect page in a given environment
- **THEN** the page shows that environment's MCP server URL (ending in `/mcp`) with a Copy button, and copying places the exact URL on the clipboard

#### Scenario: Address is never a placeholder
- **WHEN** the Connect page renders
- **THEN** it shows the real configured `mcpServerUrl` and never instructs the customer to obtain the URL from an administrator

### Requirement: The Connect page provides per-client OAuth setup instructions

The Connect page SHALL provide setup instructions grouped by AI-assistant client. Claude Desktop and Cursor SHALL each have a full walkthrough that uses the OAuth ("Sign in with sc0red") flow, and Cursor SHALL include a copy-able remote-MCP configuration snippet templated on the current `mcpServerUrl`. All instructions SHALL describe OAuth as the connection method; the page MUST NOT present an API-key or other long-lived-token method (unsupported).

#### Scenario: Claude Desktop walkthrough
- **WHEN** the customer selects the Claude Desktop instructions
- **THEN** they see steps to add the server address as a connector and sign in with sc0red, plus an optional `mcp-remote` bridge configuration for file-only setups

#### Scenario: Cursor walkthrough with copy-able config
- **WHEN** the customer selects the Cursor instructions
- **THEN** they see a copy-able remote-MCP JSON entry containing the current environment's `mcpServerUrl`, and guidance to complete the OAuth sign-in on first use

### Requirement: ChatGPT is surfaced as a hedged pointer, not a brittle walkthrough

Because custom remote-MCP support in ChatGPT is a beta feature, gated to paid plans, and reached through an unstable, changing UI path, the Connect page SHALL present ChatGPT as a brief, honest pointer rather than a hard-coded step-by-step. The pointer SHALL note that it requires enabling ChatGPT's Developer Mode on a paid plan and SHALL link to OpenAI's official Developer Mode guide rather than reproducing menu steps that go stale.

#### Scenario: ChatGPT pointer links out instead of hard-coding steps
- **WHEN** the customer views the ChatGPT entry on the Connect page
- **THEN** it states that ChatGPT support is beta (paid plan, Developer Mode), tells them to add the server address above, and links to OpenAI's Developer Mode guide — without a reproduced click-by-click walkthrough

### Requirement: Connected assistants are managed on the same page

The Connect page SHALL include the customer's connected assistants (their OAuth consents) with the ability to disconnect any of them, so connecting and managing live in one place. An empty state SHALL point the customer at the setup instructions above. Disconnecting SHALL revoke that assistant's access.

#### Scenario: A newly connected assistant appears and can be disconnected
- **WHEN** a customer completes the OAuth flow from their assistant and returns to the Connect page
- **THEN** the assistant appears in the connected list with a Disconnect control, and choosing Disconnect revokes its access

#### Scenario: Empty state guides first connection
- **WHEN** the customer has no connected assistants
- **THEN** the connected list shows an empty state that directs them to the setup instructions on the same page
