"""Risk scoring calibration guide — injected into risk assessment system prompts.

Provides score range definitions, category-specific anchors, anti-pattern corrections,
and observable proxy patterns to eliminate score variance across runs.
"""

RISK_SCORING_GUIDE = """\
## Risk Score Calibration Framework

### Score Range Definitions (apply consistently across ALL categories)

| Score Range | Evidence Threshold | Meaning |
|-------------|-------------------|---------|
| 9-10 (Critical) | Multiple strong, independently observable indicators of imminent disruption | Business model is fundamentally threatened within 1-2 years; existential risk |
| 7-8 (High) | Clear, specific observable indicators of significant exposure | Meaningful vulnerability requiring strategic response within 2-3 years |
| 5-6 (Moderate) | Some indicators present but with mixed or ambiguous signals | Standard industry-level exposure; monitor but no urgency |
| 3-4 (Low) | Few or weak indicators; company shows active mitigation | Low exposure or company is well-positioned against this risk |
| 1-2 (Minimal) | No observable indicators; category largely irrelevant | Risk does not materially apply to this business model |

### Category-Specific Anchors

#### competitive_displacement
- Score 8+: AI-native competitors with demonstrably superior products visible in market \
(e.g., G2/Capterra rankings showing displacement, competitor funding rounds, customer migration signals)
- Score 5-6: Competitors exist but company retains differentiation visible in positioning and customer base
- Score 2-4: Company operates in niche with limited direct AI-native competition

#### technology_obsolescence
- Score 8+: Core technology stack or product approach is being superseded by AI alternatives \
(e.g., manual workflow tools vs AI-automated equivalents already in market)
- Score 5-6: Some components at risk but company shows modernisation signals (tech blog, job postings for AI roles)
- Score 2-4: Tech stack is current or company is already AI-native

#### customer_behavior
- Score 8+: Customer base is actively adopting AI alternatives (visible in competitor growth, \
declining review sentiment, customer churn signals)
- Score 5-6: Some customer segments exploring alternatives but core base appears stable
- Score 2-4: Strong customer lock-in visible (long-term contracts, high switching costs, testimonials)

#### margin_compression
- Score 8+: AI enabling competitors to deliver equivalent value at dramatically lower cost \
(visible in competitor pricing, open-source alternatives, commoditisation trends)
- Score 5-6: Some pricing pressure but company maintains premium positioning
- Score 2-4: Strong pricing power visible (premium positioning, value-based pricing, low-cost competition absent)

#### talent_workforce
- Score 8+: Core workforce functions directly automatable by current AI \
(e.g., data entry, basic analysis, tier-1 support — visible in job postings and service descriptions)
- Score 5-6: Some roles at risk but company workforce requires significant human judgement
- Score 2-4: Workforce roles are highly specialised or relationship-driven

#### regulatory_compliance
- Score 8+: Operating in sector with active AI regulation (healthcare AI, financial AI, hiring AI) \
with visible compliance gaps
- Score 5-6: Sector has emerging AI regulation but company shows awareness
- Score 2-4: Minimal regulatory exposure to AI-specific rules

#### supply_chain
- Score 8+: Key suppliers or vendor dependencies face disruption from AI \
(e.g., reliance on services being automated, single-vendor lock-in to vulnerable provider)
- Score 5-6: Some vendor dependencies with moderate AI exposure
- Score 2-4: Minimal supply chain complexity or software-only model with diversified vendors

#### data_ip
- Score 8+: Core IP or data advantage is being commoditised by AI \
(e.g., AI can generate equivalent data, open-source models matching proprietary capabilities)
- Score 5-6: Some data assets at risk but company has unique data sources
- Score 2-4: Strong data moat from proprietary sources not replicable by AI

### Anti-Patterns (DO NOT do these)

| Wrong Approach | Correct Approach | Why |
|---------------|-----------------|-----|
| Default most scores to 5-6 as a safe middle ground | Use the full 1-10 range based on observable evidence | Middle-clustering destroys signal; every company looks the same |
| Score based on industry reputation alone ("tech companies face AI risk") | Score based on THIS company's specific observable indicators | Generic industry takes are not analysis |
| Give higher scores to categories the company acknowledges on its website | Distinguish between acknowledging a risk and being vulnerable to it | Awareness does not equal vulnerability |
| Score all categories similarly within ±1 point | Allow 4+ point spreads between categories when evidence supports it | Companies have uneven risk profiles; flat scoring hides the real picture |
| Treat absence of information as moderate risk (score 5) | Treat absence of information as low risk (score 2-3) unless context demands otherwise | Missing data is not evidence of risk |

### Observable Proxy Patterns

For each category, look for these signals on the company's website and public presence:
- **Job postings**: Reveal tech stack, manual processes, growth areas, AI adoption level
- **Product/service pages**: Show feature set, competitive positioning, automation level
- **Customer testimonials/case studies**: Indicate satisfaction drivers, retention signals, pain points
- **Pricing pages**: Reveal monetisation model, competitive pressure, value positioning
- **Blog/news section**: Show strategic direction, recent investments, AI awareness
- **Team/about pages**: Indicate expertise depth, leadership focus, workforce composition
- **Technology/integration pages**: Reveal tech maturity, API ecosystem, modernisation level\
"""
