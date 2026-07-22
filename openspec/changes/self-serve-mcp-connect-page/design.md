## Context

The sc0red Services MCP server (`/mcp`, streamable-HTTP, OAuth bearer) is live in dev/testing/production behind per-env branded domains (`mcp.{dev,test,prod}.services.sc0red.ai/mcp`). OAuth is the only auth method and is proven — it was used to connect Claude Code to the dev and test servers during development.

Today the only in-app connect guidance is a static blurb at the bottom of `frontend/src/app/(authenticated)/settings/connected-apps/ConnectedAppsView.tsx`:
- It does NOT show the server URL ("ask your administrator if you don't have it") — the frontend has no knowledge of the MCP URL.
- No per-client steps, no copy-able config, no transport/auth guidance.

The sibling **sc0red** app has a dedicated Connect page (server address → choose auth → tabbed per-client setup). This change brings an equivalent, simpler (OAuth-only) experience to sc0red Services.

## Goals / Non-Goals

**Goals:**
- A customer can self-serve connect their assistant with zero help from an administrator: find the address, follow client-specific steps, sign in with sc0red, and see the connection appear.
- One page, one mental model: **address → set it up → manage** (no separate "connect" vs "manage" split).
- Correct, copy-able, per-environment server address surfaced programmatically (no hard-coded or "ask an admin" URL).
- Full, trustworthy walkthroughs for the two clients whose remote-MCP + OAuth support is stable (Claude Desktop, Cursor).
- Preserve the existing consent management (list connected assistants + disconnect), re-homed onto this page.

**Non-Goals:**
- API keys / long-lived tokens for MCP (a whole separate auth feature — issue/store/rotate/revoke + a second bearer path). OAuth only.
- A full ChatGPT walkthrough tab (deferred — see the ChatGPT decision below).
- Per-user or per-org MCP URLs — the endpoint is one shared address per environment; OAuth carries identity.
- Any change to the MCP protocol, OAuth flow, or consent model.

## Decisions

### Page structure — one page, three sections
```
Settings ▸ Connect
 ① Your server address     copy-able mcpServerUrl (from /api/config) + "sign in when prompted"
 ② Set it up in your assistant     tabs: Claude Desktop | Cursor & others | ChatGPT
 ③ Connected apps          existing OAuth-consent list + Disconnect, folded in
```
Rationale: merges the reference's "server address" + "set up your assistant" and folds today's Connected Apps management underneath, so the connect→appear→manage loop lives on one screen. The reference's separate "choose how to connect" step is dropped entirely because OAuth is the only method.

### Keystone: surface `mcpServerUrl` via `/api/config`
The page cannot exist without the frontend knowing the URL. Add a `mcpServerUrl` field to the existing `/api/config` response, sourced from a per-environment env var / CDK output (the same value already configured for the branded MCP domain). It is a public endpoint address (no secret). One shared value per environment — no templating. Every other part of the page is contained frontend + copy work with no protocol risk once this lands.

### Per-client content
- **Claude Desktop** (full): add via the Connectors UI → paste the address → sign in with sc0red → approve. Include an optional `claude_desktop_config.json` `mcp-remote` bridge snippet (Node 18+) for file-only setups.
- **Cursor & others** (full): a copy-able `~/.cursor/mcp.json` (or project `.cursor/mcp.json`) remote-MCP entry templated on `mcpServerUrl`, then OAuth on first use. This snippet also serves generic "any MCP-compatible client" cases.
- **ChatGPT** (hedged one-liner + link): see below.

### ChatGPT: hedged pointer, not a walkthrough (spike result)
A spike (July 2026) confirmed custom remote MCP in ChatGPT **does work** — via **Developer Mode**, with OAuth and full read+write tool calling. But:
1. It is **beta** (OpenAI and a Sep-2025 Auth0 walkthrough both label Developer Mode beta).
2. It is **gated to paid plans** (Pro / Business / Enterprise / Edu — not Free), and the exact tier list has shifted over time, so we don't pin a specific set in the UI.
3. The enable path is **UI-unstable**: OpenAI's docs say *Settings → Security and login*, the Auth0 walkthrough says *Settings → Connectors → Advanced*, and "connectors" was renamed "apps" in Dec 2025.

A hard-coded step-by-step would go stale within a release or two and only helps paid users who flip a beta toggle — a poor fit for a page whose value is a clean, trustworthy walkthrough. **Decision:** ChatGPT gets a single honest sentence ("beta; on Plus/Pro enable Developer Mode, add the address above, sign in with sc0red") plus a link to OpenAI's Developer Mode guide. A full ChatGPT tab is a fast-follow once it exits beta / the UI settles.

Sources: OpenAI developer docs (`developers.openai.com/api/docs/mcp`), OpenAI Help Center "Developer mode and MCP apps in ChatGPT", Auth0 "Integrate your OAuth-secured MCP server in ChatGPT" (2025-09-11).

### Component decomposition (360-line limit)
The page is assembled from focused sub-components rather than one file: a copy-able server-address block, a per-client tabs component (with the copy-able snippets), and reuse of the existing connected-apps list + disconnect. This keeps each component within the frontend size limit and lets the address block / tabs be tested in isolation.

## Risks / Trade-offs

- **Instruction staleness** — vendor client UIs change; per-client steps drift. Mitigated by linking out for the volatile one (ChatGPT) and keeping Claude/Cursor steps minimal (the address + "sign in" is the durable core; exact menu names are the fragile part).
- **ChatGPT users under-served in v1** — a Plus/Pro user who wants ChatGPT gets only a pointer. Accepted: better an honest pointer than brittle steps; revisit at GA.
- **Config surface** — exposing `mcpServerUrl` publicly is fine (it's the same address printed on the page), but the plumbing must be per-environment so dev/test/prod each show their own address; a mis-wired value would send customers to the wrong endpoint. Low risk, worth an explicit check in each env.
- **Duplication with the sibling sc0red app** — two apps now maintain similar Connect content; acceptable (different servers, different auth surface — API keys there, OAuth-only here).
