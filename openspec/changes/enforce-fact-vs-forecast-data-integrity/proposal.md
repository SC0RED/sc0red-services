## Why

A production customer (CEO of a portfolio firm) reported that the generated report for a debt-settlement company described it as an 80%-subscription **SaaS** business doing **$30M–$400M** revenue at a **15–35% EBITDA margin**, and produced a "Grow subscription revenue" opportunity — none of it true. The cause is a silent `business_model == "saas"` default: when a company matches no industry-template keyword, both the EBITDA tree and the value chain fabricate a complete SaaS P&L and operating model and present it **as fact**. Wrong forward-looking advice is forgivable in this product; wrong *existing facts* destroy customer confidence and get the whole tool dismissed. We need to guarantee the report never asserts an existing fact it cannot ground.

## What Changes

- **Establish a "fact vs. forecast" data-integrity contract.** Every report surface is classified FACT (existing reality — business model, financials, operating model) or FORECAST (risk scores, opportunities, strategy map). FACT surfaces must be grounded in evidence or shown as an explicit placeholder; they must never be defaulted, templated-as-fact, or asserted without basis. FORECAST surfaces may be approximate.
- **BREAKING (report output): remove the silent SaaS fallback** in both the EBITDA tree (`_DEFAULT_TEMPLATE_KEY`) and the value chain (`DEFAULT_TEMPLATE_KEY`). When `business_model` matches no template, the section renders a clearly-labeled **"insufficient public data to model this"** placeholder instead of a fabricated SaaS section.
- **Fix the EBITDA range-width defect** so a *matched* template no longer multiplies the bottom of one uncertainty band against the top of another (today's ~13× `$30M–$400M` spread presented as fact).
- **Give the value chain the same grounding/confidence signal the EBITDA tree already has** — today it silently defaults to SaaS with no confidence signal at all.
- **Ground profile facts.** AI-extracted existing facts (especially `business_model`, `revenue_model`, `company_size`) must be traceable to scraped content; ungroundable fields are marked low-confidence or omitted rather than confidently asserted. Fix the `company_size` enum mismatch between the profile schema (`"Enterprise 1000+"`) and the size map (`"Large 1000-5000"` / `"Enterprise 5000+"`) that silently defaults size today.
- **Make it durable.** Extend `make audit` to fail on any fact-bearing report section that carries a silent default, so a future section cannot reintroduce this pattern.
- **Documented follow-up (not in this change): "forecast framing"** — re-wording forward-looking surfaces (opportunities, value levers, strategy map) as explicit suggestions rather than statements. Captured in design.md as the next step.

## Capabilities

### New Capabilities
- `report-data-integrity`: The fact-vs-forecast classification contract, the "insufficient public data" placeholder standard for ungroundable FACT surfaces, and the audit rule that forbids silent defaults on fact-bearing sections.
- `value-chain-grounding`: The value chain must render the placeholder (not a defaulted SaaS chain) when `business_model` matches no template, and carry a derivation-provenance signal equivalent to the EBITDA tree's.
- `company-profile-grounding`: AI-extracted existing facts must be grounded in scraped content; ungroundable facts are omitted/low-confidence rather than asserted; `company_size` values align with the downstream size map.

### Modified Capabilities
- `ebitda-tree-confidence`: A no-template-match no longer produces a "low confidence" defaulted SaaS tree — it produces the "insufficient public data" placeholder. Adds the requirement that the revenue range must not compound independent uncertainty bands into a misleadingly wide figure.

## Impact

- **Backend pipeline steps**: `build_ebitda_tree.py`, `_ebitda_templates.py`, `_ebitda_confidence.py`, `build_value_chain.py`, `value_chain_templates.py`, `extract_profile.py`.
- **Prompts/schemas**: `prompts/schemas/profile.json`, `prompts/system/profile_extraction.md`.
- **Models**: `model_company.py` (`EbitdaTreeResult` / `ValueChainResult` gain a placeholder/insufficient-data state; `ValueChainStep` or `ValueChainResult` gains a confidence/provenance field).
- **Frontend**: report sections that render the EBITDA tree and value chain must handle the new placeholder state.
- **Tooling**: `make audit` / audit script gains the silent-default check.
- **Downstream**: opportunity/value-lever cards that read revenue streams or the value chain stop inheriting fabricated SaaS language as a side effect.
- **No DynamoDB schema migration**: new fields are additive and optional.
