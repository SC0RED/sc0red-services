## 1. Surface the MCP server address (keystone)

- [x] 1.1 **Single source of truth**: derive `mcpServerUrl` from the CDK output that already defines the branded MCP domain per environment (do NOT introduce a second, hand-maintained env var that could drift). Wire that one value into the config source `/api/config` reads.
- [x] 1.2 Add `mcpServerUrl` to the `/api/config` response payload + its frontend config type.
- [x] 1.3 Validate the value at the config boundary: assert it is an `https://…/mcp` URL and matches the expected `mcp.{dev,test,prod}.services.sc0red.ai/mcp` shape for the running environment; an unexpected/missing value surfaces as the unavailable state (task 2.2), never a wrong endpoint.
- [x] 1.4 Tests: `/api/config` includes `mcpServerUrl`; per-environment mapping resolves the correct host; a missing/empty/non-`/mcp` value is treated as unavailable (drives the disabled-controls state), not rendered blank or as "ask an administrator".

## 2. Connect page shell + server-address section

- [ ] 2.1 Add the Connect page/route under `settings/` (grow the existing `connected-apps` page into it; update the Settings nav label/link to "Connect").
- [ ] 2.2 Server-address sub-component: shows `mcpServerUrl` with a Copy button and the "sign in with sc0red when prompted" note. Keep under the 360-line component limit.
- [ ] 2.3 Tests: renders the configured address; Copy places the exact URL on the clipboard; unavailable-address state.

## 3. Per-client setup instructions (tabs)

- [ ] 3.1 Client-tabs sub-component with Claude Desktop / Cursor & others / ChatGPT.
- [ ] 3.2 Claude Desktop tab: Connectors-UI + OAuth walkthrough; optional `mcp-remote` bridge `claude_desktop_config.json` snippet (Node 18+) with a Copy button.
- [ ] 3.3 Cursor tab: copy-able `~/.cursor/mcp.json` remote-MCP snippet templated on `mcpServerUrl` + OAuth-on-first-use note.
- [ ] 3.4 ChatGPT tab: hedged one-liner (beta, Plus/Pro, Developer Mode, add the address, sign in) + link to OpenAI's Developer Mode guide. No reproduced click-steps.
- [ ] 3.5 Tests: each tab renders; snippets interpolate the current `mcpServerUrl`; Copy works; ChatGPT entry links out and shows the beta caveat.

## 4. Fold in connected-apps management

- [ ] 4.1 Reuse the existing connected-apps list + Disconnect as the page's "Connected apps" section (preserve current consent/disconnect behavior).
- [ ] 4.2 Empty state directs the customer to the setup instructions above.
- [ ] 4.3 Remove the old bare "How to connect" blurb (superseded by the tabs) and update any links pointing at the old page.
- [ ] 4.4 Tests: list + disconnect still work in the new placement; empty state renders.

## 5. Verify + ship

- [ ] 5.1 `cd frontend && npm run lint && npx tsc --noEmit && npm test` — all green; components within size limits.
- [ ] 5.2 Backend (if config plumbing touches Python): `ruff check` + `ruff format` + naming validator + `pytest` ≥ 95%.
- [ ] 5.3 Manually verify on dev: the page shows the dev address, Claude Desktop + Cursor walkthroughs connect via OAuth, the assistant appears in the connected list, and Disconnect revokes it.
- [ ] 5.4 Branch → PR → E2E → merge approval (never commit to `development` directly).

## 6. Future work (out of scope for this change)

- [ ] 6.1 Add a full ChatGPT walkthrough tab once ChatGPT custom-MCP exits beta and its UI path stabilizes (replace the one-liner pointer).
