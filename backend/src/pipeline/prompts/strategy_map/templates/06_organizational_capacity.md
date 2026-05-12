## Step 6 — Organizational Capacity Perspective

You are generating Step 6 of a 7-step strategy map. This step produces
exactly 3 Organizational Capacity objectives, one each for the People,
Technology, and Culture buckets, per the Vector Advisory house style.

## Inputs

**Company name**: {company_name}
**Customer Value Proposition** (from Step 2): {value_proposition}
**Internal Processes themes** (from Step 5):
{internal_process_themes}

**Talent / workforce signals**:
- talent_workforce risk score: {talent_risk_score}
- talent_workforce risk rationale: {talent_risk_rationale}

**Technology signals** (inferred from public materials):
- Tech-stack mentions in scraped content: {tech_signals}
- Technology-related opportunities: {tech_opportunities}

**Culture signals** (inferred from public materials):
- Published values (if any): {published_values}
- About-us / leadership / careers content: {culture_signals}

## Your task

Produce exactly 3 Organizational Capacity objectives:

- ONE People objective (talent, skills, leadership, succession,
  associate experience)
- ONE Technology objective (systems, data, tools, technical
  capability)
- ONE Culture objective (values, ways of working, organisational
  alignment)

Produce JSON:

```json
{
  "organizationalCapacity": {
    "people": {
      "id": "O.P",
      "title": "<imperative title>",
      "definition": "<50-150 word 'We will…' definition>",
      "confidence": "<HIGH | MEDIUM | LOW>",
      "rationale_source": "<short note>"
    },
    "technology": {
      "id": "O.T",
      "title": "<imperative title>",
      "definition": "<50-150 word 'We will…' definition>",
      "confidence": "<HIGH | MEDIUM | LOW>",
      "rationale_source": "<short note>"
    },
    "culture": {
      "id": "O.C",
      "title": "<imperative title>",
      "definition": "<50-150 word 'We will…' definition>",
      "confidence": "<HIGH | MEDIUM | LOW>",
      "rationale_source": "<short note>"
    }
  },
  "coreValues": {
    "values": ["<value 1>", "<value 2>", "<value 3>", ...],
    "synthesised": <true|false>,
    "rationale": "<short note>"
  }
}
```

## Rules

- Exactly 3 objectives — one per bucket. Not more, not fewer.
- IDs are O.P, O.T, O.C.
- Each objective MUST connect to at least one Internal Process theme
  from Step 5. The objective enables the theme.
- Confidence guidance:
  - **HIGH** typically only for People when the company has a clear
    public talent / leadership story (executive bios, named
    leadership-development programmes, etc.) or for Technology when
    the company has a clear technical positioning (engineering blog,
    public open-source, technology-leadership awards).
  - **MEDIUM** when industry pattern fits but no direct public signal.
  - **LOW** when the bucket is inferred from absence — no published
    values means LOW confidence on Culture; sparse careers / about
    pages means LOW on People; no public tech presence means LOW on
    Technology. LOW objectives become "What's Missing?" gap
    candidates in Step 7.
- Core values: 3-6 values listed as a foundation strip. If the
  company publishes values explicitly, use those (`synthesised:
  false`). If not, infer from public materials and set
  `synthesised: true`.

## Example (Vector v1 substitution — Culture instead of Wawa's
Financial Management)

```json
{
  "organizationalCapacity": {
    "people": {
      "id": "O.P",
      "title": "Invest in and develop our associates to create high engagement and a culture of ownership",
      "definition": "We will deliver strong talent development processes to ensure that associates are engaged and have the skills, experiences, and competencies to deliver an outstanding customer experience. We will develop a comprehensive plan for recruitment, learning and development, retention, leadership development, and succession to ensure a deep, diverse, and robust talent pipeline.",
      "confidence": "MEDIUM",
      "rationale_source": "Careers page emphasises associate ownership; no specific learning-and-development programmes named publicly."
    },
    "technology": {
      "id": "O.T",
      "title": "Deliver reliable technologies and support services with valuable insight and innovative solutions",
      "definition": "We will provide consistently reliable technical products and support services, valuable insights to make forward-looking business decisions, and cost-effective and innovative solutions. To deliver this, we will drive a process-centric approach that ensures the highest return on technology investments.",
      "confidence": "MEDIUM",
      "rationale_source": "Technology-related opportunity (#5: digital ordering platform) implies but does not detail tech capability."
    },
    "culture": {
      "id": "O.C",
      "title": "Live our values to create the foundation for our strategy",
      "definition": "Our values — value people, delight customers, embrace change, do the right thing, do things right, and a passion for winning — are the foundation of how we work, how we serve customers, and how we grow. We will live these values consistently across the organization, embedding them in hiring, performance management, recognition, and decision-making.",
      "confidence": "HIGH",
      "rationale_source": "Values published explicitly on the about-us page."
    }
  },
  "coreValues": {
    "values": ["value people", "delight customers", "embrace change", "do the right thing", "do things right", "passion for winning"],
    "synthesised": false,
    "rationale": "Verbatim from the company's published values page."
  }
}
```

Output JSON only. No prose around it.
