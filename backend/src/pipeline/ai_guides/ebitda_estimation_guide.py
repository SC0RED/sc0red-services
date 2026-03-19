"""EBITDA estimation guide — injected into EBITDA tree system prompts.

Provides industry benchmark tables, observable revenue proxies, business-model-specific
tree structures, and anti-pattern corrections for realistic financial decomposition.
"""

EBITDA_ESTIMATION_GUIDE = """\
## EBITDA Tree Estimation Framework

### Industry Benchmark Ranges

Use these as sanity checks — estimates outside these ranges require strong observable evidence:

| Business Model | Gross Margin | EBITDA Margin | Revenue per Employee |
|---------------|-------------|---------------|---------------------|
| SaaS | 70-85% | 15-35% | $150K-$400K |
| Professional Services | 30-50% | 10-25% | $100K-$250K |
| E-commerce / Marketplace | 25-45% | 5-15% | $200K-$800K |
| Manufacturing | 25-40% | 8-20% | $100K-$300K |
| Financial Services | 50-70% | 20-40% | $200K-$500K |
| Media / Content | 40-60% | 10-25% | $150K-$350K |
| Healthcare / Biotech | 50-70% | 15-30% | $150K-$400K |

If your estimates produce margins outside the range for the identified business model, \
re-examine your assumptions before proceeding.

### Observable Proxies for Revenue Estimation

| Observable Signal | What It Suggests | How to Use |
|-------------------|-----------------|------------|
| Employee count (LinkedIn/team page) × industry revenue per employee | Revenue range estimate | Primary sizing method for private companies |
| Number and type of office locations | Scale and geographic reach | Multiple offices suggest $10M+ revenue |
| Customer logos on website | Enterprise vs SMB mix, deal sizes | Fortune 500 logos suggest $50K+ ACV; SMB logos suggest lower ACV, higher volume |
| Pricing page (if visible) | Unit economics and deal structure | Multiply visible price × estimated customer count |
| "Customers" or "users" count claims | Scale validation | Cross-reference with employee count for consistency |
| Job posting volume and seniority | Growth trajectory and maturity | Heavy hiring = growth phase; senior-only = mature/stable |
| Technology integrations listed | Market segment and sophistication | Enterprise integrations (Salesforce, SAP) suggest larger deals |
| Funding history (if visible/known) | Scale expectations | Series B+ typically implies $5M-$50M ARR target |

Always cross-reference at least TWO proxies. A single signal can be misleading.

### Tree Structure Templates by Business Model

**SaaS** typical decomposition:
- Revenue: Subscriptions (70-90%), Professional Services (10-20%), Other/Usage (0-10%)
- COGS: Cloud Infrastructure (10-15%), Customer Support (5-10%), Implementation (0-5%)
- OpEx: Sales & Marketing (30-50%), R&D (15-25%), G&A (10-15%)

**Professional Services** typical decomposition:
- Revenue: Project-Based (40-60%), Retainers/Managed Services (30-50%), Training/Other (5-15%)
- COGS: Delivery Labour (50-65%)
- OpEx: Sales & Marketing (10-20%), R&D (5-10%), G&A (10-15%)

**E-commerce / Marketplace** typical decomposition:
- Revenue: Product Sales (60-80%), Marketplace Fees (10-30%), Advertising/Other (5-15%)
- COGS: Product/Fulfilment (55-75%)
- OpEx: Sales & Marketing (15-30%), Technology (5-10%), G&A (5-10%)

**Manufacturing** typical decomposition:
- Revenue: Product Sales (80-95%), Services/Aftermarket (5-20%)
- COGS: Materials (40-55%), Direct Labour (15-25%), Manufacturing Overhead (5-10%)
- OpEx: Sales & Marketing (5-15%), R&D (3-8%), G&A (5-10%)

Match the tree structure to the company's ACTUAL business model as identified from their website, \
not a generic template. Adjust revenue splits and cost categories to reflect what is observable.

### Anti-Patterns

| Wrong | Right | Why |
|-------|-------|-----|
| Stating exact revenue without evidence (e.g., "$23.4M") | Provide ranges reflecting uncertainty (e.g., "$15M-$30M") | Private companies do not disclose financials; false precision erodes trust |
| Applying SaaS margins to a services company | Match margin structure to the observable business model | A consulting firm with 30% gross margin is normal; applying 75% SaaS margins is wrong |
| Creating tree nodes with no basis in observable data | Only include line items supported by website evidence | Invented line items add noise; stick to what is supported |
| Ignoring employee count as a sizing proxy | Always use observable headcount as a primary revenue estimator | Employee count is the most reliable public proxy for private company revenue |
| Using same tree structure regardless of business model | Select template based on identified business model, then customise | A SaaS tree for a manufacturer produces nonsensical output |
| Percentage allocations that do not sum correctly within parent | Verify child percentages sum to ~100% of parent node | Inconsistent math undermines credibility of the entire tree |\
"""
