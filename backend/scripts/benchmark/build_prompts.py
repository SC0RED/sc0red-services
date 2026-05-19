#!/usr/bin/env python3
"""Build ``benchmark_prompts.json`` from sc0red Services's actual prompt templates.

Renders each canonical prompt template with a fixed ``Acme Corp`` fixture
context so the benchmark sees realistic prompt sizes and shapes. The output
file is committed so the benchmark is reproducible without re-rendering;
re-run this script whenever a template changes to regenerate.

Usage:
    cd backend && uv run python scripts/benchmark/build_prompts.py

The fixture is intentionally hand-crafted to be representative:
- Vision/mission/VP read like a B2B SaaS company.
- The 4 perspectives have realistic objective titles and short definitions.
- Scrape excerpts are sized to match typical production prompts (~10-15K input tokens).

The benchmark cost is dominated by these input tokens. With ~10 prompts × 2
models, expect $3-7 per full run.
"""

from __future__ import annotations

import json
from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "src" / "pipeline" / "prompts"


# ── Fixture ─────────────────────────────────────────────────────────────────

_COMPANY_NAME = "Acme Robotics"
_URL = "https://acmerobotics.example.com"
_VISION = "Acme Robotics builds collaborative robots that work alongside warehouse associates to make order fulfilment faster, safer, and more accurate."
_VALUE_PROPOSITION = "operational_excellence — Acme delivers 30% throughput improvement for mid-market warehouse operators through a fleet of collaborative pick-and-pack robots."

# Each perspective has 3-4 short objectives. Definitions are tight — typical
# of what an assessed analysis would emit. Total context size targets ~10K
# input tokens to mirror production prompts.
_FINANCIAL_OBJECTIVES = """
- F1 "Grow recurring fleet-as-a-service revenue": Recurring SaaS + hardware-leasing revenue grows 40% YoY by capturing 3 additional Fortune-500 warehouse operators.
- F2 "Expand gross margin via parts standardisation": Standardise SKU base across the gen-3 robot to lift unit gross margin from 28% to 38% within 18 months.
- F3 "Sustain free cash flow positivity": Cross the FCF-positive threshold by Q4 2027 to fund capex without dilution.
""".strip()

_CUSTOMER_OBJECTIVES = """
- C1 "I want my fulfilment ops to scale without hiring 50 more pickers": Operators perceive the fleet as a labour-multiplier that eliminates seasonal hiring crunches.
- C2 "I want incident-free integration with my existing WMS": Operators experience zero-downtime install and seamless data flow with their WMS of choice within 30 days.
- C3 "I want measurable throughput and accuracy lift": Operators see weekly dashboards showing 30%+ throughput gain and <0.1% pick-error rate after rollout.
- C4 "I want long-term partnership, not a vendor": Operators see Acme as a strategic partner co-investing in their warehouse roadmap, not a transactional supplier.
""".strip()

_INTERNAL_PROCESSES = """
Theme 1: Build the gen-3 collaborative-robot platform
  - I1.1 "Ship a hardware platform that the next 5 years of features can stack on top of": Architectural foundation locks in modular tooling so customer-specific configs ship in weeks not months.
  - I1.2 "Make every install a 30-day delight": Standardised install playbook + remote commissioning toolchain hits a 30-day median from contract signing to first productive pick.
  - I1.3 "Continuously close the safety gap with humans-only operations": Behavioural safety telemetry from every robot feeds a quarterly safety-improvement loop that surfaces failure patterns before incidents.

Theme 2: Build the fleet-data flywheel
  - I2.1 "Capture pick patterns from every fleet to make the next install smarter": Cross-fleet aggregate telemetry creates a tuning corpus that compresses new-customer onboarding from 30 days to 14.
  - I2.2 "Turn fleet performance data into customer ROI proof": Per-customer ROI dashboards convert qualitative throughput claims into hard renewal-trigger numbers.
  - I2.3 "Use field data to drive the gen-3+ feature roadmap": Real-world picker-bot interaction data drives the prioritised feature list, not customer-anecdote roadmaps.
  - I2.4 "Detect customer-side bottlenecks our robots can absorb": Telemetry-driven upsell signals identify additional WMS integrations, conveyor handoffs, and depalletisation surfaces.

Theme 3: Build a customer-success engine that prevents churn
  - I3.1 "Catch at-risk customers before their renewal date": Quarterly health-scoring identifies trajectory-down customers in time for intervention.
  - I3.2 "Make every renewal a strategic conversation, not a price negotiation": Account-team playbooks tie every renewal to forward-looking expansion opportunities documented quarterly.
  - I3.3 "Build a peer-to-peer community of fulfilment leaders running Acme fleets": Customer-led knowledge-sharing sessions create durable peer ties that compound the switching cost.
  - I3.4 "Document and publish operator wins to drive market-pull": Field-proven case studies generate inbound demand at lower CAC than outbound prospecting.
""".strip()

_ORGANIZATIONAL_CAPACITY = """
- O.P (People) "Hire and retain hardware-software hybrids who can ship gen-3": Cross-disciplinary engineers + experienced field operators are the unique talent we cannot outsource.
- O.T (Technology) "A modular hardware-software stack that compounds on every customer install": Common platform across robot generations + a fleet-management plane that scales horizontally.
- O.C (Culture) "Engineer-operator co-ownership of customer outcomes": Engineers visit customer warehouses quarterly; field operators have a structured path to escalate platform gaps.
""".strip()

# Scrape excerpt — sized to mimic a typical production scrape (~8K chars).
_SCRAPED_TEXT = """Acme Robotics is a Series C robotics company that builds collaborative warehouse robots for mid-market fulfilment operators. Founded in 2018 in Boston, the company has raised $147M across four rounds with notable investors including Sequoia Capital, Lux Capital, and Goldman Sachs. The gen-3 platform launched in 2025 and is currently deployed in 47 warehouses across 23 customers, with 8 of those customers operating at 5+ sites.

The company's website emphasises a partnership model rather than a transactional vendor relationship. Case studies highlight operators in retail apparel (3 customers), e-commerce fulfilment (12 customers), pharmaceutical distribution (5 customers), and automotive parts (3 customers). Reported throughput gains range from 22% to 41% with the median at 31%; pick-error rates drop from a customer baseline of 0.3-0.8% to a fleet steady-state of 0.06-0.09%.

Team page lists 142 full-time employees with engineering split roughly 50/50 between hardware (mechanical, electrical, systems) and software (perception, fleet orchestration, customer-facing tooling). Leadership team includes a CEO with a background at Amazon Robotics and a CTO who previously led the perception team at Locus Robotics.

Pricing is sold via 3-year recurring contracts: a per-robot subscription that bundles hardware lease, fleet-management software, software updates, and field-engineering support. Headline price is $48K/robot/year for the standard config; customised end-effectors (cold-chain handling, fragile-item gripping) bid up to $66K/robot/year.

Recent product launches: a depalletisation arm extension (2025-Q3) that captures inbound receiving handoffs; a returns-processing config (2025-Q4) that addresses the reverse-logistics surge from 2024 e-commerce growth. The depalletisation arm has 11 deployed units across 6 customers; returns-processing has 3 pilot installs.

Customer churn is reported informally on the careers page as "<5% annually". Industry benchmarks for robotics-as-a-service hover around 8-15% for similar mid-market deployments.

Recent press coverage focuses on the gen-3 launch, a partnership with Honeywell Intelligrated for warehouse-control-system integration, and a 2025-Q4 Series C extension that brings total funding to $210M.

The company has stated public ambitions to reach $200M ARR by 2028 (currently ~$48M ARR) and to expand into European markets via a London office opening in 2026-Q2.

Engineering job postings emphasise expertise in ROS 2, Python, Rust, and warehouse-management-system protocols (specifically Manhattan Active and SAP EWM). The hardware org is hiring for mechanical engineers with cobot experience and electrical engineers with motor-control depth.

Customer success roles emphasise "fluency in warehouse operations" — postings prefer candidates with 5+ years of direct warehouse-floor experience over generic SaaS CS backgrounds. The implicit hiring signal: customer outcomes depend on field empathy, not playbook execution.

The company's positioning explicitly distances itself from "fully autonomous warehouses" — the gen-3 platform is sold as augmenting human pickers, not replacing them. Marketing copy repeatedly contrasts Acme with competitors (Geek+, Locus, Symbotic) on the question of replacement vs augmentation.

Web presence shows a regular blog cadence (~2 posts/month) focused on technical deep-dives, customer success stories, and warehouse-operations thought leadership. The blog has built a small but loyal following among warehouse ops practitioners.

Acme participates in MODEX, ProMat, and Gartner Supply Chain Symposium as a regular exhibitor. 2025 booth feedback emphasised the live-demo strategy: visitors operate a robot themselves rather than watching a video.

Partnerships announced in 2024-2025: Manhattan Associates (WMS integration), Honeywell Intelligrated (WCS integration), DHL Supply Chain (3PL operator deploying at 4 facilities), and Locus Group (system integrator).

Open questions a buyer might investigate: actual revenue recognition (subscription accounting vs. lease accounting), the long-tail unit economics on the customisation premium, the path to hardware gross-margin standardisation at 38%, and the European market entry capital requirements.
""".strip()

_DOCUMENT_SECTION = ""  # No supplementary docs in this fixture.

# Risk categories block for risk_batch.md
_RISK_CATEGORIES_BLOCK = """
1. competitive_displacement — A new AI-native warehouse robot vendor could displace Acme's mid-market positioning with a lower per-unit cost or a categorically better autonomy curve.
2. technology_obsolescence — Foundation-model-driven perception could render Acme's task-specific perception stack obsolete; the gen-3 platform may not absorb the shift gracefully.
3. customer_behavior — Warehouse operators may shift preferences from cobot+human models to fully autonomous models, undermining the augment-not-replace positioning.
4. margin_compression — Falling component costs + competitive pricing pressure may erode the per-robot subscription gross margin before the standardisation roadmap delivers.
""".strip()

_RISK_INDUSTRY_WEIGHTING = "Robotics-as-a-service is hardware-heavy and capital-intensive. Risk scoring should over-weight margin and technology-obsolescence categories relative to a software-only SaaS company."

_RISK_ASSESSMENT_QUESTIONS = """For each category, answer:
- What is the 3-year severity if this risk plays out?
- What is the probability the risk crystallises within 3 years?
- What concrete signals from THIS company's profile contributed to the score?

Score each from 1 (negligible) to 10 (existential). Use the full scale.""".strip()

# Additional fixture values for strategy-map templates.
_INDUSTRY = "Industrial Robotics — Collaborative Warehouse Automation"
_MISSION = "Acme Robotics enables mid-market warehouse operators to scale fulfilment capacity without proportional labour growth."
_REVENUE_ESTIMATE = "$48M ARR (FY2025), trending toward $200M by 2028"
_EBITDA_ESTIMATE = "Approaching FCF-positive in Q4 2027; current EBITDA margin -8% as gen-3 platform absorbs R&D"

_EBITDA_TREE = """
- Revenue: ~$48M ARR
  - Hardware-lease subscription (~70% of ARR)
  - Software/fleet-management (~20% of ARR)
  - Customisation premiums (~10% of ARR)
- COGS: ~70% of revenue
  - Hardware unit cost: gen-3 BOM ~$32K/robot, target ~$22K via standardisation
  - Field-engineering install + ongoing support: ~12% of revenue
- Gross Margin: ~30%, target 38% post-standardisation
- OpEx: ~38% of revenue
  - R&D (hardware-software hybrid teams): ~22% of revenue
  - S&M (mid-market field sales): ~10% of revenue
  - G&A: ~6% of revenue
- EBITDA: -8% currently, target +8% at $200M ARR
""".strip()

_TOP_OPPORTUNITIES = """
1. Compress gen-3 hardware BOM via ML-driven component substitution (margin lever)
2. Convert pilot installs to multi-site rollouts via measurable ROI dashboards (revenue lever)
3. Capture inbound receiving handoffs with the depalletisation arm extension (revenue lever)
4. Build a peer-to-peer customer community to depress churn (retention lever)
""".strip()

_OPPORTUNITIES = _TOP_OPPORTUNITIES  # alias used by some templates

_VALUE_CHAIN = """
Primary activities:
  - Inbound logistics (hardware component supply chain)
  - Operations (robot assembly + commissioning)
  - Outbound logistics (field installation at customer warehouses)
  - Marketing & sales (mid-market warehouse operator outreach)
  - Service (ongoing fleet management + field engineering)
Support activities:
  - R&D (hardware + software hybrid engineering)
  - HR (cross-disciplinary engineering + field-operator recruiting)
  - Procurement (component standardisation programme)
""".strip()

_VALUE_CHAIN_SUMMARY = "Hardware-heavy primary activities (assembly, install, service) with R&D as the dominant support activity; differentiation comes from the engineer-operator co-ownership culture."

_OPPORTUNITY_CATEGORIES = "Competitive Moat, Revenue Capture, Market Expansion, Operational Efficiency, Talent Strategy"

_DOCUMENT_TEXT = ""  # No supplementary documents in this fixture.


def _system_prompt(relpath: str) -> str:
    """Load a system prompt by repo-relative path under ``prompts/``."""
    return (_PROMPTS_DIR / relpath).read_text(encoding="utf-8").strip()


# Cached system-prompt strings — loaded once at import. Mirrors what
# production passes to ``client.responses.create(instructions=...)`` so the
# benchmark exercises the same model behaviour the pipeline relies on.
_SP_STRATEGY_MAP = _system_prompt("strategy_map/system/strategy_map_generator.md")
_SP_PROFILE = _system_prompt("system/profile_extraction.md")
_SP_RISK = _system_prompt("system/risk_assessment.md")
_SP_IDEATION = _system_prompt("system/opportunity_ideation.md")
_SP_DETAIL = _system_prompt("system/opportunity_detail.md")


def _render(template_relpath: str, **kwargs: str) -> str:
    """Load a template and substitute named placeholders with the fixture values."""
    text = (_PROMPTS_DIR / template_relpath).read_text(encoding="utf-8")
    for key, value in kwargs.items():
        text = text.replace("{" + key + "}", value)
    return text


def _load_schema(schema_relpath: str) -> dict:
    """Load a JSON schema. Wrap into OpenAI ``json_schema`` envelope."""
    raw = json.loads((_PROMPTS_DIR / schema_relpath).read_text(encoding="utf-8"))
    name = raw.get("title", "structured_response").replace(" ", "_")
    return {"name": name, "schema": raw}


# ── Prompt builders ─────────────────────────────────────────────────────────


def build_arrow_yesno() -> dict:
    """A representative arrow yes/no call (one of 30-60 per analysis)."""
    prompt = _render(
        "strategy_map/templates/decomposed/arrow_yesno.md",
        company_name=_COMPANY_NAME,
        vision_statement=_VISION,
        value_proposition=_VALUE_PROPOSITION,
        from_id="O.P",
        from_title="Hire and retain hardware-software hybrids who can ship gen-3",
        to_id="I1.1",
        to_title="Ship a hardware platform that the next 5 years of features can stack on top of",
        financial_objectives=_FINANCIAL_OBJECTIVES,
        customer_objectives=_CUSTOMER_OBJECTIVES,
        internal_processes=_INTERNAL_PROCESSES,
        organizational_capacity=_ORGANIZATIONAL_CAPACITY,
    )
    return {
        "id": "strategy_map_arrow_yesno_01",
        "task_type": "arrow_yesno",
        "description": "Strategy-map arrow yes/no — one candidate cause-effect link among 60+ parallel calls",
        "prompt": prompt,
        "json_schema": _load_schema("strategy_map/schemas/per_call/arrow_yesno.json"),
        "system_prompt": _SP_STRATEGY_MAP,
        "reasoning_effort": "low",
        "verbosity": "medium",
    }


def build_arrows_priorities() -> dict:
    """The single holistic priorities call — the one that hit the 184s tail."""
    prompt = _render(
        "strategy_map/templates/decomposed/arrows_priorities.md",
        vision_statement=_VISION,
        value_proposition=_VALUE_PROPOSITION,
        financial_objectives=_FINANCIAL_OBJECTIVES,
        customer_objectives=_CUSTOMER_OBJECTIVES,
        internal_processes=_INTERNAL_PROCESSES,
        organizational_capacity=_ORGANIZATIONAL_CAPACITY,
    )
    return {
        "id": "strategy_map_arrows_priorities_01",
        "task_type": "arrows_priorities",
        "description": "Strategy-map holistic priorities synthesis — the historic tail-latency outlier",
        "prompt": prompt,
        "json_schema": _load_schema("strategy_map/schemas/per_call/arrows_priorities.json"),
        "system_prompt": _SP_STRATEGY_MAP,
        "reasoning_effort": "low",
        "verbosity": "medium",
    }


def build_internal_objective_detail() -> dict:
    """A representative Round-2 objective elaboration for the internal-processes perspective."""
    prompt = _render(
        "strategy_map/templates/decomposed/round3_detail_internal.md",
        company_name=_COMPANY_NAME,
        value_proposition=_VALUE_PROPOSITION,
        theme_name="Build the gen-3 collaborative-robot platform",
        objective_title="Ship a hardware platform that the next 5 years of features can stack on top of",
        sibling_titles="""- "Make every install a 30-day delight"
- "Continuously close the safety gap with humans-only operations" """.strip(),
        supports_financial_objectives="F1, F2",
        opportunities=_OPPORTUNITIES,
        value_chain=_VALUE_CHAIN,
    )
    return {
        "id": "strategy_map_internal_detail_01",
        "task_type": "internal_objective_detail",
        "description": "Strategy-map Round-3 internal-objective elaboration (definition, category, confidence)",
        "prompt": prompt,
        "json_schema": _load_schema("strategy_map/schemas/per_call/internal_objective_detail.json"),
        "system_prompt": _SP_STRATEGY_MAP,
        "reasoning_effort": "low",
        "verbosity": "medium",
    }


def build_financial_titles() -> dict:
    """Round-1 titles for the financial perspective (3 short titles)."""
    prompt = _render(
        "strategy_map/templates/decomposed/round1_titles_financial.md",
        company_name=_COMPANY_NAME,
        vision_statement=_VISION,
        value_proposition=_VALUE_PROPOSITION,
        ebitda_tree=_EBITDA_TREE,
        ebitda_estimate=_EBITDA_ESTIMATE,
        revenue_estimate=_REVENUE_ESTIMATE,
        top_opportunities=_TOP_OPPORTUNITIES,
    )
    return {
        "id": "strategy_map_financial_titles_01",
        "task_type": "financial_titles",
        "description": "Strategy-map Round-1 financial-perspective title list (3 short objective titles)",
        "prompt": prompt,
        "json_schema": _load_schema("strategy_map/schemas/per_call/financial_titles.json"),
        "system_prompt": _SP_STRATEGY_MAP,
        "reasoning_effort": "low",
        "verbosity": "medium",
    }


def build_mission_text() -> dict:
    """Step-1 mission-statement generation."""
    prompt = _render(
        "strategy_map/templates/decomposed/mission_text.md",
        company_name=_COMPANY_NAME,
        company_url=_URL,
        industry=_INDUSTRY,
        scraped_content=_SCRAPED_TEXT,
        document_text=_DOCUMENT_TEXT,
    )
    return {
        "id": "strategy_map_mission_text_01",
        "task_type": "mission_text",
        "description": "Strategy-map mission-statement generation from scrape",
        "prompt": prompt,
        "json_schema": _load_schema("strategy_map/schemas/per_call/mission_text.json"),
        "system_prompt": _SP_STRATEGY_MAP,
        "reasoning_effort": "low",
        "verbosity": "medium",
    }


def build_vp_primary() -> dict:
    """Step-2 value-proposition primary classifier."""
    prompt = _render(
        "strategy_map/templates/decomposed/vp_primary.md",
        company_name=_COMPANY_NAME,
        industry=_INDUSTRY,
        scraped_content=_SCRAPED_TEXT,
        vision_statement=_VISION,
        mission_statement=_MISSION,
        opportunity_categories=_OPPORTUNITY_CATEGORIES,
        value_chain_summary=_VALUE_CHAIN_SUMMARY,
    )
    return {
        "id": "strategy_map_vp_primary_01",
        "task_type": "vp_primary",
        "description": "Strategy-map value-proposition primary classifier (operational_excellence / customer_intimacy / product_leadership / hybrid)",
        "prompt": prompt,
        "json_schema": _load_schema("strategy_map/schemas/per_call/vp_primary.json"),
        "system_prompt": _SP_STRATEGY_MAP,
        "reasoning_effort": "low",
        "verbosity": "medium",
    }


def build_profile() -> dict:
    """Company-profile extraction (used by ParallelProfileRiskAndIdeation)."""
    prompt = _render(
        "templates/profile.md",
        url=_URL,
        content=_SCRAPED_TEXT,
        document_section=_DOCUMENT_SECTION,
    )
    return {
        "id": "profile_extract_01",
        "task_type": "profile_extraction",
        "description": "ParallelProfileRisk — extract structured company profile from scrape",
        "prompt": prompt,
        "json_schema": _load_schema("schemas/profile.json"),
        "system_prompt": _SP_PROFILE,
        "reasoning_effort": "low",
        "verbosity": "medium",
    }


def build_risk_batch() -> dict:
    """Risk-batch assessment (one of two batches per analysis)."""
    prompt = _render(
        "templates/risk_batch.md",
        url=_URL,
        scraped_text=_SCRAPED_TEXT,
        document_section=_DOCUMENT_SECTION,
        categories_block=_RISK_CATEGORIES_BLOCK,
        risk_industry_weighting=_RISK_INDUSTRY_WEIGHTING,
        risk_assessment_questions=_RISK_ASSESSMENT_QUESTIONS,
        num_categories="4",
    )
    return {
        "id": "risk_batch_01",
        "task_type": "risk_batch",
        "description": "ParallelProfileRisk — assess 4 risk categories with rationale (audit-trail quality matters)",
        "prompt": prompt,
        "json_schema": _load_schema("schemas/risk_batch.json"),
        "system_prompt": _SP_RISK,
        "reasoning_effort": "low",
        "verbosity": "medium",
    }


def build_ideation() -> dict:
    """Single opportunity ideation (one of 8 per analysis)."""
    strategic_categories = "Available strategic categories: Competitive Moat, Revenue Capture, Market Expansion, Operational Efficiency, Talent Strategy"
    prompt = _render(
        "templates/ideation.md",
        url=_URL,
        scraped_text=_SCRAPED_TEXT,
        document_section=_DOCUMENT_SECTION,
        category_id="margin_compression",
        category_name="Margin compression",
        category_description="Falling component costs + competitive pricing pressure may erode the per-robot subscription gross margin before the standardisation roadmap delivers.",
        strategic_categories=strategic_categories,
    )
    return {
        "id": "ideation_01",
        "task_type": "ideation",
        "description": "ParallelProfileRisk — generate one specific AI opportunity addressing margin compression (creativity matters)",
        "prompt": prompt,
        "json_schema": _load_schema("schemas/ideation.json"),
        "system_prompt": _SP_IDEATION,
        "reasoning_effort": "low",
        "verbosity": "medium",
    }


def build_detail() -> dict:
    """DetailOpportunities — implementation steps + ROI."""
    company_context = "Acme Robotics — Series C collaborative warehouse-robot company. ~142 employees. ~$48M ARR. 23 customers."
    prompt = _render(
        "templates/detail.md",
        company_context=company_context,
        opportunity_title="Deploy AI-driven component-substitution analysis to compress hardware BOM cost by 12-18%",
        opportunity_description="Use ML-based component-substitution recommendations against the gen-3 hardware BOM to surface near-equivalent components at lower unit cost, accelerating the gross-margin standardisation roadmap.",
    )
    return {
        "id": "detail_01",
        "task_type": "detail_opportunity",
        "description": "DetailOpportunities — implementation steps + timeline + investment range + ROI (specificity matters)",
        "prompt": prompt,
        "json_schema": _load_schema("schemas/detail.json"),
        "system_prompt": _SP_DETAIL,
        "reasoning_effort": "low",
        "verbosity": "medium",
    }


# ── Main ────────────────────────────────────────────────────────────────────


def main() -> None:
    """Build benchmark_prompts.json from the 10 canonical sc0red Services prompts."""
    builders = [
        build_arrow_yesno,
        build_arrows_priorities,
        build_internal_objective_detail,
        build_financial_titles,
        build_mission_text,
        build_vp_primary,
        build_profile,
        build_risk_batch,
        build_ideation,
        build_detail,
    ]

    prompts = [builder() for builder in builders]

    output = {
        "metadata": {
            "version": "1.0",
            "created": "2026-05-15",
            "description": (
                "sc0red Services benchmark prompts — one per distinct AI call site. "
                "Generated by build_prompts.py from real sc0red Services prompt templates "
                "rendered with the Acme Robotics fixture. Re-run build_prompts.py "
                "when templates change."
            ),
            "fixture": "Acme Robotics (Series C collaborative warehouse-robot)",
            "schema_coverage": [p["task_type"] for p in prompts],
        },
        "prompts": prompts,
    }

    output_path = Path(__file__).parent / "benchmark_prompts.json"
    output_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")

    total_chars = sum(len(p["prompt"]) for p in prompts)
    print(f"Wrote {len(prompts)} prompts to {output_path}")
    print(f"Total prompt size: {total_chars:,} chars (~{total_chars // 4:,} tokens)")
    print(f"Schema coverage: {', '.join(p['task_type'] for p in prompts)}")


if __name__ == "__main__":
    main()
