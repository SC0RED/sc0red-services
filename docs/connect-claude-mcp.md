# Connecting Claude to the sc0red Services MCP Server

sc0red Services runs a remote [MCP](https://modelcontextprotocol.io) server so AI assistants
can read your portfolio analyses and start scans on your behalf — with the same OAuth login and
org scoping as the web app. This guide covers connecting **Claude** (claude.ai and Claude Code).

---

## Endpoints

| Environment | MCP URL |
|---|---|
| Production | `https://mcp.services.sc0red.ai/mcp` |
| Testing | `https://mcp.test.services.sc0red.ai/mcp` |
| Development | `https://mcp.dev.services.sc0red.ai/mcp` |

Use **production** unless you're testing. The server authenticates with OAuth (you log in with
your sc0red Services account and approve access) — there's no API key to manage.

---

## Option A — Claude.ai (web or desktop)

This is the standard path and how most users connect.

1. **Plan check** — custom connectors require a paid plan (Pro / Max / Team / Enterprise). On
   Team/Enterprise an org admin may need to enable custom connectors first.
2. Open **Settings → Connectors**.
3. Click **Add custom connector** (at the bottom of the connectors list).
4. Enter:
   - **Name:** `sc0red Services`
   - **Remote MCP server URL:** `https://mcp.services.sc0red.ai/mcp`
5. Click **Add**. Claude registers itself automatically (Dynamic Client Registration) and starts
   the OAuth flow:
   - You're taken to the sc0red Services consent page.
   - If you're not signed in, **log in or sign up** — you're returned to the consent page
     afterward.
   - Click **Allow access** (grants read + write).
6. The connector shows **Connected** with its tools.
7. In a chat, make sure the connector is enabled (tools/attachments menu), then ask away.

---

## Option B — Claude Code (CLI)

```bash
claude mcp add --transport http sc0red https://mcp.services.sc0red.ai/mcp
```

Then, inside a `claude` session, run `/mcp` to start the OAuth flow (opens your browser to log in
and approve). `/mcp` also lists the connected server and its tools once authenticated.

---

## What you can ask

The server exposes **17 tools** — read tools (dashboard, analyses, risk breakdowns, opportunities,
EBITDA, value chain, strategy map, scans, team) and write tools (start/confirm scans). Examples:

- *"Show my sc0red portfolio dashboard."*
- *"List my analyses and which ones are highest risk."*
- *"Start a scan of https://example.com and tell me the scan ID."*
- *"Check the progress of that scan."* (progress climbs live as the pipeline runs)
- *"Discover the portfolio at <PE firm URL>, then show me the discovered companies."*
- *"Confirm those companies for analysis."*

Tools are scoped to your organization — Claude only ever sees your org's data. Scans are rate
limited per organization (5/hour, 30/day) since each one triggers a full AI analysis.

---

## Troubleshooting

- **"Allow access" loops back to login** — make sure you complete login fully; you should land
  back on the consent page. (Fixed in the current release.)
- **Connector won't connect right after setup** — the OAuth issuer is the branded host; if you
  recently reconnected, remove and re-add the connector so it re-runs consent.
- **A scan tool says write access is required** — disconnect and reconnect, approving **write**
  access at the consent step.
- **"Scan rate limit reached"** — you've hit the per-org hourly/daily cap; the message says when
  to retry. The web app is unaffected.
- **Read tools return nothing** — your org has no analyses yet; start a scan first.
