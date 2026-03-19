"""Ideation quality guide — injected into opportunity ideation system prompts.

Provides specificity standards, observable-evidence grounding, anti-pattern corrections,
and strategic category calibration to produce more actionable, company-specific ideas.
"""

IDEATION_GUIDE = """\
## Opportunity Ideation Standards

### Strong vs Weak Ideation

| Dimension | Weak (DO NOT) | Strong (DO THIS) |
|-----------|--------------|-------------------|
| Specificity | "Invest in AI" | "Deploy conversational AI for tier-1 support tickets to reduce average handle time by 40%" |
| Company context | "Improve customer experience" | "Add AI-powered self-service portal for [specific product visible on website]" |
| Measurability | "Increase efficiency" | "Automate [specific manual process visible in job postings] to reduce headcount needs by 20-30%" |
| Actionability | "Consider digital transformation" | "Migrate [specific legacy system referenced on site] to cloud-native architecture with AI orchestration" |

### Evidence-Based Ideation

Ground EVERY ideation in something observable from the company's web presence. \
Do not invent capabilities or problems — cite what you can see:

- **Job postings** → Reveal manual processes ripe for automation, tech stack gaps, hiring pain points
- **Product/service pages** → Show feature gaps vs competitors, areas lacking AI augmentation
- **Customer testimonials** → Expose pain points customers experience, satisfaction drivers to protect
- **Pricing pages** → Reveal monetisation model, potential for AI-driven upsell or dynamic pricing
- **Blog/news** → Signal strategic priorities, recent investments, areas the company is already exploring
- **Competitor comparison** → If visible, shows where company is behind and needs AI acceleration

If you cannot point to a specific signal from the website that supports your ideation, \
the idea is too generic. Revise it.

### Anti-Patterns

| Wrong | Why It Fails |
|-------|-------------|
| "Leverage AI/ML capabilities" | Buzzword without specificity — WHAT AI capability? For WHAT business outcome? |
| "Improve operational efficiency" | Every company should do this — it is not an insight |
| "Expand into new markets using AI" | WHICH markets? Based on WHAT evidence from the website? |
| Suggesting capabilities the company already has | Check website features before suggesting — duplicating existing work wastes PE sponsor time |
| Generic "AI chatbot" without context | Specify WHAT the chatbot handles, for WHICH user segment, replacing WHAT current process |
| Opportunity unrelated to the assigned risk category | Each ideation must DIRECTLY address the specific risk category provided |

### Strategic Category Calibration

Each strategic category demands a specific type of evidence and specificity:

- **Competitive Moat**: Must reference a SPECIFIC competitive threat observable in the market \
and propose a defensible advantage. "Be more competitive" is not a moat — name the competitor \
or competitive dynamic and the specific capability that creates lock-in.

- **Revenue Capture**: Must identify a SPECIFIC untapped revenue stream based on the company's \
existing assets, customer base, or market position. Not "increase revenue" but "monetise [specific \
data/capability/user base] through [specific mechanism]."

- **Market Expansion**: Must name a SPECIFIC adjacent market or segment with evidence of \
adjacency from the company's current positioning. Not "expand internationally" but "enter \
[specific vertical] where [observable signal] indicates demand."

- **Operational Efficiency**: Must identify a SPECIFIC process, workflow, or cost centre — \
not generic "optimise operations." Reference observable indicators like manual processes in \
job descriptions or service delivery bottlenecks visible in case studies.

- **Talent Strategy**: Must reference observable workforce signals — hiring patterns, skill \
gaps in job postings, team composition, or roles at risk from automation. Not "invest in \
talent" but "redeploy [specific role type] from [manual task] to [higher-value function]."\
"""
