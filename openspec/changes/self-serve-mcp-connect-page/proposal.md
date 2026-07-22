## Why

The sc0red Services MCP server is live in all environments and OAuth ("Sign in with sc0red") works end-to-end, but there is **no self-serve way for a customer to connect their AI assistant to it**. The only in-app guidance is a bare three-line "How to connect" blurb at the bottom of Settings ▸ Connected Apps that doesn't even give the server URL — it literally says *"ask your administrator if you don't have it."* Customers can't discover the address, don't know which transport/auth to use, and get no per-client setup steps. The sibling **sc0red** app already solves this with a dedicated, polished Connect page; sc0red Services should offer an equivalent, self-serve experience.

## What Changes

- Add a **single, well-designed Connect page** at Settings ▸ Connect (growing today's Connected Apps page) with one flow: **address → set it up → manage**.
  - **① Server address** — the customer's environment MCP URL (e.g. `https://mcp.prod.services.sc0red.ai/mcp`), shown with a Copy button, plus a note that they'll sign in with sc0red when their client prompts.
  - **② Set it up in your assistant** — tabbed per-client instructions:
    - **Claude Desktop** — full walkthrough (Connectors UI + OAuth; optional `mcp-remote` bridge for file-only setups).
    - **Cursor & others** — full walkthrough with a copy-able `~/.cursor/mcp.json` remote-MCP snippet (URL + OAuth).
    - **ChatGPT** — a hedged one-liner + link-out to OpenAI's Developer Mode guide (NOT a full walkthrough — see design.md for why).
  - **③ Connected apps** — the existing OAuth-consent list + Disconnect, folded into the same page so "connect → see it appear → manage it" is one loop.
- Surface a per-environment **`mcpServerUrl`** in the existing `/api/config` response (from an env var / CDK output) so the page can show the real address. This is the keystone dependency — one shared endpoint per environment; OAuth carries user identity, so no per-user/per-org templating.

**Out of scope (explicit):** API-key / long-lived-token auth for MCP. OAuth is the only supported and documented method. A full ChatGPT walkthrough tab is deferred until ChatGPT's custom-MCP support exits beta and its UI settles.

## Capabilities

### New Capabilities
- `mcp-connect-onboarding`: the self-serve Connect page — presenting the copy-able per-environment MCP server address, per-client OAuth setup instructions (Claude Desktop + Cursor full, ChatGPT a hedged pointer), and in-page management of connected assistants (consent list + disconnect).

### Modified Capabilities
<!-- None. No existing capability's REQUIREMENTS change. The /api/config addition is
     additive plumbing (no config-capability spec exists to modify), and the existing
     connected-apps consent/disconnect behavior is preserved as-is (re-homed onto the
     new page), not changed. -->

## Impact

- **Frontend**: new Connect page under `settings/` (grows the existing `connected-apps` page). Likely sub-components to respect the 360-line limit: a copy-able server-address block, a per-client tabs component, reusing the existing connected-apps list + disconnect. Customer-visible brand string is "sc0red Services".
- **Config**: `/api/config` gains a `mcpServerUrl` field, sourced per-environment (env var / CDK output). No secrets — it's a public endpoint address.
- **Backend / MCP protocol**: none. OAuth, the `/mcp` streamable-HTTP endpoint, per-env branded URLs, and consent management already exist and are unchanged.
- **Docs currency risk**: per-client UI instructions (especially ChatGPT, which is beta) drift as vendor UIs change; the ChatGPT pointer links out rather than hard-coding brittle steps.
- **Workflow**: spec-only change; implementation lands via branch → PR → merge approval (never committed to `development` directly).
