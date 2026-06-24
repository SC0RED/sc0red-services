## Why

A production customer reported that the report mis-stated **Century Support Services, LLC** (a debt-settlement firm) — first as a SaaS/subscription business, then (after the placeholder fix shipped in `enforce-fact-vs-forecast-data-integrity`) as a generic "Professional Services" business with project/retainer/training revenue and an R&D cost line. None of that reflects debt-settlement **success-fee** economics (15–25% of enrolled debt).

The root cause is structural: the EBITDA tree and value chain are built from **hardcoded industry templates selected by a keyword match** on the AI-extracted `business_model` string. A loose match ("professional service") applies a template whose revenue mix and margins are pure assumptions. **Yet the AI model already knows the correct answer** — the customer got the right revenue model simply by asking ChatGPT. We replaced "ask the model" with "keyword-match a template," and the template is what misrepresents the company.

This change recovers that accuracy: decompose the financial/operating-model questions into small, sharply-scoped AI calls, ground quantitative facts with the model's **native web search**, and label every fact with explicit provenance and deterministic confidence — honest about what is estimated, rigorous about how each number was reached.

## What Changes

- **BREAKING (report internals): retire the deterministic keyword templates** for both the EBITDA tree and the value chain. They are replaced by a decomposed AI-research pipeline.
- **Add a decomposed financial-research DAG** — small short-answer structured AI calls organized into rounds (parallel within a round via `FutureManager`, sequential across rounds), mirroring the existing strategy-map decomposed generator:
  - Round 1 (independent): company type · primary revenue model · disclosed-figures lookup · scale signals
  - Round 2 (depends on R1): revenue mix · margin band · revenue range · cost drivers · real operating-model steps (value chain)
  - Round 3: assemble the EBITDA tree + value chain, then adversarially verify
- **Ground quantitative facts with OpenAI's native `web_search`** via the existing `signalfield_core` SDK — **no new vendor**. Enabled *selectively* (only on quantitative/real-world questions, not on questions the model answers from training knowledge). Returned `web_sources` become citations.
- **Per-fact provenance tiers** — every fact carries `DISCLOSED (cited)` | `INDUSTRY-TYPICAL` | `DERIVED-ESTIMATE`. A web-search source auto-upgrades a figure to `DISCLOSED`.
- **Deterministic confidence** derived from the provenance tier (not AI-self-rated), consistent with the existing EBITDA confidence labelling — for auditability.
- **Honest-but-rigorous labelling** — quantitative figures render as labelled estimates that "show their work" (value + provenance + confidence + one-line basis); disclosed figures show their citation. *(This absorbs the deferred forecast-framing + raise-the-grounding-bar follow-ups.)*
- **Adversarial verification** — a cheap plausibility yes/no check per fact (strategy-map yes/no pattern) downgrades or rejects implausible answers.
- **Wrapper extension** — `run_structured_ai_call` gains optional `tools` and returns `web_sources` (today it passes neither and discards sources).
- **Floor unchanged** — when the model genuinely can't determine a fact, the `enforce-fact-vs-forecast-data-integrity` "insufficient public data" placeholder still applies.
- **Out of scope (documented next step): UX/latency optimization** — streaming financials in after the headline, perceived-latency tuning. Quality first.

## Capabilities

### New Capabilities
- `decomposed-financial-research`: the question-DAG that derives revenue model, mix, margins, revenue range, cost drivers, and operating-model steps via small parallel/sequential structured AI calls, replacing the deterministic templates.
- `web-search-grounding`: selective use of the provider's native `web_search` tool to ground quantitative facts, capture `web_sources` as citations, and govern when search runs; includes the `run_structured_ai_call` tools/`web_sources` extension.
- `fact-provenance-labeling`: the provenance-tier model (`DISCLOSED`/`INDUSTRY-TYPICAL`/`DERIVED-ESTIMATE`), deterministic confidence from tier, and the honest-but-rigorous "show your work" presentation contract.

### Modified Capabilities
- `ebitda-tree-confidence`: the tree is now AI-researched; confidence derives from per-fact provenance tier rather than template/size match.

> Note: `value-chain-grounding`, `report-data-integrity`, and `company-profile-grounding` were introduced by the still-unarchived `enforce-fact-vs-forecast-data-integrity` change, so they are not yet in the spec baseline. Their behaviour here is carried by the new `decomposed-financial-research` (researched operating model) and `fact-provenance-labeling` (provenance-or-placeholder contract) capabilities; the deltas against those three will be reconciled when the prior change is archived.

## Impact

- **Backend pipeline:** new research steps + orchestrator under `src/pipeline/pipeline_steps/` (RequestStep-wired through `CompanyAnalysisFactory`); retire `_ebitda_templates.py` / `value_chain_templates.py` keyword logic; rewrite `build_ebitda_tree.py` / `build_value_chain.py` as assemblers over researched facts.
- **AI plumbing:** extend `ai_call.py` `run_structured_ai_call` (tools + `web_sources`); reuse `FutureManager` + the strategy-map round pattern.
- **Prompts/schemas:** new per-question templates + short schemas under `src/pipeline/prompts/`.
- **Models:** `EbitdaNode` / `EbitdaTreeResult` / `ValueChainStep` / `ValueChainResult` gain provenance-tier + citation fields (additive).
- **Persistence:** thread provenance/citation through `persist_results.py`, `assessment_repository.py`, `_assessment_subrecord_ops.py`, `analysis_payload.py` (additive, no migration).
- **Frontend + PDF + MCP:** render the provenance/confidence/basis + citations on the EBITDA and value-chain surfaces.
- **Cost/telemetry:** web-search calls incur ~$0.01 each (SDK-tracked); selective enablement caps this to a few calls per analysis.
- **Latency/determinism:** trades deterministic templates for researched accuracy; wall-clock ≈ slowest dependency chain (far below the old single ~27s EBITDA call).
- **Supersedes** the deferred forecast-framing + grounding-bar follow-ups recorded in `enforce-fact-vs-forecast-data-integrity/design.md`.
