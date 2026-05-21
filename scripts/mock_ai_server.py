"""Minimal mock AI server for E2E / integration testing.

Handles OpenAI  POST /v1/chat/completions
      Anthropic POST /v1/messages

Routes by inspecting the json_schema properties to identify which pipeline
step is calling and returns a structurally valid mock response.

No external dependencies — pure stdlib. Run with: python mock_ai_server.py
"""

from __future__ import annotations

import json
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

_PORT = 8080

_MOCK_COMPANY_HTML = """\
<!DOCTYPE html>
<html>
<head><title>E2E Test Corp - AI Risk Intelligence Platform</title></head>
<body>
<h1>E2E Test Corp</h1>
<p>We are a B2B SaaS company providing AI-powered risk intelligence to private equity firms.</p>
<p>Our platform analyses portfolio companies for AI disruption risk across eight categories.</p>
<p>Founded in 2023, E2E Test Corp serves enterprise clients in the financial services sector.</p>
<p>Products: Risk Intelligence Platform, Portfolio Analytics Dashboard, Opportunity Engine.</p>
<p>Technology: Python, React, AWS Lambda, DynamoDB.</p>
<p>Revenue model: annual subscription, starting at $50K per year.</p>
<a href="https://linkedin.com/company/e2e-test-corp">LinkedIn</a>
<a href="/about">About Us</a>
<a href="/pricing">Pricing</a>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Mock payloads — one per pipeline step, keyed by a unique top-level property
# ---------------------------------------------------------------------------
_MOCK_RESPONSES: dict[str, object] = {
    # URLResolutionStrategy
    "actual_url": {
        "actual_url": "https://example.com",
    },
    # ExtractProfile
    "company_name": {
        "company_name": "E2E Test Corp",
        "industry": "B2B SaaS - Testing",
        "industry_sector": "Technology",
        "business_model": "SaaS",
        "description": "A mock company used for E2E integration testing.",
        "products_services": ["Test Platform", "Mock Analytics"],
        "target_market": "Enterprise software teams",
        "company_size": "Mid-market 200-1000",
        "revenue_model": "Subscription",
        "tech_signals": ["Python", "React", "Kubernetes"],
        "competitive_positioning": "Cost-effective, developer-friendly tooling",
        "ai_maturity": "Early exploration",
        "key_risks_visible": ["Limited market presence"],
    },
    # AssessRisk — Batch A (external market threats)
    "risk_scores_batch_a": {
        "risk_scores": [
            {
                "category": "competitive_displacement",
                "score": 5.0,
                "rationale": (
                    "Moderate competitive pressure from AI-native entrants"
                    " with several well-funded competitors in the space."
                ),
            },
            {
                "category": "technology_obsolescence",
                "score": 5.0,
                "rationale": (
                    "Moderate technology risk given current stack"
                    " with standard tech choices and some legacy components."
                ),
            },
            {
                "category": "customer_behavior",
                "score": 4.0,
                "rationale": (
                    "Low customer churn risk"
                    " with long-term contract structure observed."
                ),
            },
            {
                "category": "margin_compression",
                "score": 5.0,
                "rationale": (
                    "Moderate margin pressure from infrastructure costs"
                    " with cloud cost trends visible in pricing."
                ),
            },
        ],
    },
    # AssessRisk — Batch B (internal/operational risks)
    "risk_scores_batch_b": {
        "risk_scores": [
            {
                "category": "talent_workforce",
                "score": 4.0,
                "rationale": (
                    "Low talent risk with stable engineering team"
                    " and low attrition signals from job postings."
                ),
            },
            {
                "category": "regulatory_compliance",
                "score": 3.0,
                "rationale": (
                    "Low regulatory exposure in current markets"
                    " with no significant compliance flags visible."
                ),
            },
            {
                "category": "supply_chain",
                "score": 3.0,
                "rationale": (
                    "Minimal supply chain risk for SaaS model"
                    " with software-only product and no physical supply chain."
                ),
            },
            {
                "category": "data_ip",
                "score": 4.0,
                "rationale": (
                    "Low data and IP risk"
                    " with standard data handling practices."
                ),
            },
        ],
    },
    # Ideation (8 calls — one per risk category, dispatched by prompt keyword)
    "ideation_competitive_displacement": {
        "title": "AI-powered competitive intelligence platform",
        "description": (
            "Deploy real-time AI monitoring of competitor moves to stay"
            " ahead of AI-native entrants in the risk intelligence space."
        ),
        "value_lever": "Revenue Side",
        "strategic_category": "Competitive Moat",
        "impact_rating": "High",
    },
    "ideation_technology_obsolescence": {
        "title": "Modernise analytics engine with LLM integration",
        "description": (
            "Replace legacy analytics with LLM-powered insights"
            " to prevent technology obsolescence."
        ),
        "value_lever": "Both",
        "strategic_category": "Competitive Moat",
        "impact_rating": "High",
    },
    "ideation_customer_behavior": {
        "title": "AI-driven customer success automation",
        "description": (
            "Implement predictive churn models and automated engagement"
            " to counter shifting customer expectations."
        ),
        "value_lever": "Revenue Side",
        "strategic_category": "Revenue Capture",
        "impact_rating": "Medium",
    },
    "ideation_margin_compression": {
        "title": "Automate infrastructure cost optimisation",
        "description": (
            "Use AI to dynamically right-size cloud resources"
            " and reduce infrastructure spend."
        ),
        "value_lever": "Cost Side",
        "strategic_category": "Operational Efficiency",
        "impact_rating": "Medium",
    },
    "ideation_talent_workforce": {
        "title": "AI-augmented analyst workflow",
        "description": (
            "Equip analysts with AI copilots to handle"
            " higher volume without additional headcount."
        ),
        "value_lever": "Cost Side",
        "strategic_category": "Talent Strategy",
        "impact_rating": "Medium",
    },
    "ideation_regulatory_compliance": {
        "title": "Automated compliance monitoring dashboard",
        "description": (
            "Build AI-powered regulatory tracking for"
            " emerging AI governance frameworks."
        ),
        "value_lever": "Cost Side",
        "strategic_category": "Operational Efficiency",
        "impact_rating": "Low",
    },
    "ideation_supply_chain": {
        "title": "Vendor risk assessment automation",
        "description": (
            "Automate monitoring of key SaaS vendors"
            " for disruption signals."
        ),
        "value_lever": "Cost Side",
        "strategic_category": "Operational Efficiency",
        "impact_rating": "Low",
    },
    "ideation_data_ip": {
        "title": "Proprietary data moat strategy",
        "description": (
            "Build unique datasets from analysis outputs"
            " to create defensible IP."
        ),
        "value_lever": "Revenue Side",
        "strategic_category": "Competitive Moat",
        "impact_rating": "Medium",
    },
    # Detail (enrichment for selected opportunities)
    "detail": {
        "implementation_steps": [
            "Audit current manual workflows",
            "Pilot AI tooling on highest-volume tasks",
            "Roll out across the organisation",
        ],
        "timeline": "Quick Win (1-3 months)",
        "investment_range": "$50K-$100K",
        "roi_estimate": "2x ROI within 12 months through efficiency gains",
    },
    # GenerateStrategyMap — Step 1: Vision and Mission
    "strategy_map_step_1": {
        "vision": {
            "statement": (
                "To be the most trusted AI risk intelligence partner for"
                " private equity globally."
            ),
            "synthesised": True,
            "rationale": (
                "Synthesised from public materials describing the platform's"
                " PE focus and risk intelligence positioning."
            ),
        },
        "mission": {
            "statement": (
                "We help PE firms see AI-driven risk and opportunity in their"
                " portfolio before competitors do."
            ),
            "synthesised": True,
            "rationale": (
                "Synthesised from product copy emphasising risk-and-opportunity"
                " intelligence for PE firms."
            ),
        },
    },
    # Step 2: Customer Value Proposition classification
    "strategy_map_step_2": {
        "primary": "customer_intimacy",
        "secondary": None,
        "rationale": (
            "Public materials emphasise tailored deep-dives and a partnership"
            " relationship with PE clients rather than pure scale or product"
            " novelty."
        ),
        "exemplar_company": "Bain & Company",
    },
    # Step 3: Financial perspective — exactly 3 objectives
    "strategy_map_step_3": {
        "objectives": [
            {
                "id": "F1",
                "title": "Grow ARR through PE expansion",
                "definition": (
                    "Drive subscription revenue growth by expanding the"
                    " customer base of mid-market PE firms across geographies"
                    " through outbound and partner-led channels."
                ),
                "category": "revenue_growth",
                "confidence": "MEDIUM",
                "rationale_source": "Inferred from subscription model.",
            },
            {
                "id": "F2",
                "title": "Improve gross margin via automation",
                "definition": (
                    "Increase gross margin by automating analyst-heavy steps"
                    " in the assessment pipeline so each new customer added"
                    " requires less marginal labour."
                ),
                "category": "productivity",
                "confidence": "MEDIUM",
                "rationale_source": "Inferred from EBITDA tree margin signals.",
            },
            {
                "id": "F3",
                "title": "Maximise return on data assets",
                "definition": (
                    "Generate compounding returns on accumulated proprietary"
                    " analysis data by feeding it back into the assessment"
                    " engine and benchmarking products."
                ),
                "category": "productivity",
                "confidence": "LOW",
                "rationale_source": "Hypothesised from data-product strategy.",
            },
        ],
    },
    # Step 4: Customer perspective — first-person voice quotes, 3 objectives
    "strategy_map_step_4": {
        "objectives": [
            {
                "id": "C1",
                "title": "Show me AI risk in my portfolio I cannot see myself",
                "definition": (
                    "Customers want differentiated, non-obvious AI disruption"
                    " signals across portfolio companies that they cannot"
                    " easily generate using internal tooling."
                ),
                "panel": "consumer",
                "confidence": "MEDIUM",
                "rationale_source": "Inferred from differentiated-insight positioning.",
            },
            {
                "id": "C2",
                "title": "Help me act on that risk fast",
                "definition": (
                    "PE customers want concrete, prioritised actions tied to"
                    " each risk signal so they can convert insight into a"
                    " portfolio-company workplan within weeks."
                ),
                "panel": "consumer",
                "confidence": "MEDIUM",
                "rationale_source": "Inferred from opportunity-list product surface.",
            },
            {
                "id": "C3",
                "title": "Treat me like a partner, not a transaction",
                "definition": (
                    "Customers expect a hands-on advisory relationship around"
                    " each diligence and monitoring engagement rather than a"
                    " pure self-serve dashboard experience."
                ),
                "panel": "consumer",
                "confidence": "MEDIUM",
                "rationale_source": "Inferred from customer-intimacy classification.",
            },
        ],
    },
    # Step 5: Internal Processes — 2 themes, ids I1.x / I2.x
    "strategy_map_step_5": {
        "themes": [
            {
                "name": "Operate the Risk Intelligence Engine",
                "supports_financial_objectives": ["F1", "F2"],
                "objectives": [
                    {
                        "id": "I1.1",
                        "title": "Run the assessment pipeline at scale",
                        "definition": (
                            "Operate the multi-step AI assessment pipeline"
                            " reliably across every active engagement so"
                            " analysts receive consistent, high-quality output."
                        ),
                        "category": "operational_excellence",
                        "confidence": "MEDIUM",
                        "rationale_source": "Inferred from pipeline architecture.",
                    },
                    {
                        "id": "I1.2",
                        "title": "Continuously improve assessment quality",
                        "definition": (
                            "Iterate on prompts, scoring rubrics and reviewer"
                            " feedback loops so each generation of the engine"
                            " produces sharper, better-evidenced outputs."
                        ),
                        "category": "innovation",
                        "confidence": "MEDIUM",
                        "rationale_source": "Inferred from product-quality focus.",
                    },
                ],
            },
            {
                "name": "Deepen Customer Engagement",
                "supports_financial_objectives": ["F1"],
                "objectives": [
                    {
                        "id": "I2.1",
                        "title": "Design tailored deep-dive engagements",
                        "definition": (
                            "Convert insight signals into bespoke deep-dive"
                            " engagements that PE customers value enough to"
                            " expand spend across their portfolio."
                        ),
                        "category": "customer_management",
                        "confidence": "MEDIUM",
                        "rationale_source": "Inferred from advisory positioning.",
                    },
                ],
            },
        ],
    },
    # Step 6: Organizational Capacity — People / Technology / Culture + coreValues
    "strategy_map_step_6": {
        "people": {
            "id": "O.P",
            "title": "Build a team of analyst-engineers",
            "definition": (
                "Recruit and retain a team that combines PE-domain analytical"
                " skill with applied-AI engineering capability so the engine"
                " and the advisory layer reinforce each other."
            ),
            "confidence": "MEDIUM",
            "rationale_source": "Inferred from hybrid analyst+engineer needs.",
        },
        "technology": {
            "id": "O.T",
            "title": "Run a reliable AI delivery platform",
            "definition": (
                "Provide the AI orchestration, evaluation and infrastructure"
                " backbone needed to deliver the assessment engine at scale"
                " with predictable cost and latency."
            ),
            "confidence": "MEDIUM",
            "rationale_source": "Inferred from cloud-AI architecture signals.",
        },
        "culture": {
            "id": "O.C",
            "title": "Live a culture of disciplined curiosity",
            "definition": (
                "Cultivate a working culture that pairs analytic rigour with"
                " active curiosity about emerging AI patterns so the team"
                " stays ahead of the disruption it advises on."
            ),
            "confidence": "LOW",
            "rationale_source": "Synthesised from positioning language.",
        },
        "coreValues": {
            "values": [
                "Rigour",
                "Curiosity",
                "Partnership",
                "Speed",
            ],
            "synthesised": True,
            "rationale": (
                "Inferred from public language emphasising analytical rigour"
                " and partnership delivery."
            ),
        },
    },
    # Step 7: Strategic Priorities + Arrows + What's Missing gaps
    "strategy_map_step_7": {
        "strategicPriorities": [
            {
                "name": "Operate the Risk Intelligence Engine",
                "result": (
                    "A reliable, continuously improving assessment pipeline"
                    " that scales to every active customer engagement."
                ),
            },
            {
                "name": "Deepen Customer Engagement",
                "result": (
                    "Trusted advisory relationships with each PE customer"
                    " that expand from pilot into portfolio-wide rollout."
                ),
            },
        ],
        "arrows": [
            {
                "from": "O.P",
                "to": "I1.1",
                "hypothesis": (
                    "A team of analyst-engineers is required to operate the"
                    " assessment pipeline reliably at scale."
                ),
            },
            {
                "from": "O.T",
                "to": "I1.1",
                "hypothesis": (
                    "Reliable AI infrastructure is required for the"
                    " assessment pipeline to run consistently every day."
                ),
            },
            {
                "from": "O.C",
                "to": "I1.2",
                "hypothesis": (
                    "A culture of disciplined curiosity drives the iterative"
                    " improvement of the assessment engine over time."
                ),
            },
            {
                "from": "I1.1",
                "to": "C1",
                "hypothesis": (
                    "Reliable engine operation produces the differentiated"
                    " AI risk signals that customers cannot generate alone."
                ),
            },
            {
                "from": "I2.1",
                "to": "C3",
                "hypothesis": (
                    "Tailored deep-dive engagements create the partnership"
                    " feel that customer-intimacy customers expect."
                ),
            },
            {
                "from": "C1",
                "to": "F1",
                "hypothesis": (
                    "Differentiated risk signals drive expansion within"
                    " each PE customer and unlock new logo acquisition."
                ),
            },
            {
                "from": "I1.2",
                "to": "F2",
                "hypothesis": (
                    "Engine quality improvements reduce per-engagement"
                    " analyst hours and lift gross margin over time."
                ),
            },
        ],
        "whatsMissing": [
            {
                "id": "G1",
                "title": "Channel and partner motion is unclear",
                "description": (
                    "Public materials do not yet describe a partner-led"
                    " distribution motion that would scale customer reach"
                    " beyond direct outbound effort."
                ),
                "deepDiveFraming": (
                    "A sc0red Advisory deep-dive would map the partner"
                    " landscape and prioritise the channel motion most"
                    " likely to accelerate F1."
                ),
                "relatedObjectiveIds": ["F1", "I2.1"],
            },
            {
                "id": "G2",
                "title": "Data moat strategy is implicit",
                "description": (
                    "Public materials hint at proprietary analysis data but"
                    " do not yet articulate how that data compounds into a"
                    " defensible product moat."
                ),
                "deepDiveFraming": (
                    "A sc0red Advisory deep-dive would shape the data-asset"
                    " strategy that converts F3 from hypothesis into"
                    " operating plan."
                ),
                "relatedObjectiveIds": ["F3"],
            },
        ],
    },
}

# Category keywords used to dispatch ideation responses
_IDEATION_CATEGORIES = [
    "competitive_displacement",
    "technology_obsolescence",
    "customer_behavior",
    "margin_compression",
    "talent_workforce",
    "regulatory_compliance",
    "supply_chain",
    "data_ip",
]


def _detect_step(body: dict) -> str:
    """Return the key in _MOCK_RESPONSES that matches this request.

    Handles:
     - OpenAI Responses API: body["text"]["format"]["schema"]["properties"]
     - OpenAI Chat Completions / Anthropic: body["response_format"]["json_schema"]["schema"]["properties"]

    Routing logic:
     - "actual_url" in props → URL resolution
     - "company_name" in props → profile extraction
     - "risk_scores" in props → risk batch A or B (by prompt keyword)
     - "impact_rating" in props but NOT "implementation_steps" → ideation
     - "implementation_steps" in props but NOT "title" → detail
    """
    candidates: list[dict] = []
    try:
        candidates.append(body["text"]["format"]["schema"])
    except (KeyError, TypeError):
        pass
    try:
        candidates.append(body["response_format"]["json_schema"]["schema"])
    except (KeyError, TypeError):
        pass

    for schema in candidates:
        props = set(schema.get("properties", {}).keys())

        # Strategy map (GenerateStrategyMap pipeline step) — every one of
        # the 7 calls passes the same schema, so we discriminate on the
        # `## Step N` header at the top of each rendered template.
        # `internalProcesses` is a property unique to the strategy-map
        # output schema, which is why we use it as the disambiguator.
        if "internalProcesses" in props:
            prompt_text = _extract_prompt_text(body)
            for step_number in range(1, 8):
                if f"## Step {step_number} " in prompt_text:
                    return f"strategy_map_step_{step_number}"
            # Fall through to step 1 if the header is missing — keeps
            # the mock from returning the generic `{"result": "mock"}`
            # fallback that fails downstream Pydantic validation.
            return "strategy_map_step_1"

        # Exact matches on unique top-level properties
        for key in ("actual_url", "company_name"):
            if key in props:
                return key

        # Risk batches
        if "risk_scores" in props:
            prompt_text = _extract_prompt_text(body)
            if "competitive_displacement" in prompt_text:
                return "risk_scores_batch_a"
            return "risk_scores_batch_b"

        # Ideation: has impact_rating but NOT implementation_steps
        if "impact_rating" in props and "implementation_steps" not in props:
            prompt_text = _extract_prompt_text(body)
            for category in _IDEATION_CATEGORIES:
                if category in prompt_text:
                    return f"ideation_{category}"
            return "ideation_competitive_displacement"

        # Detail: has implementation_steps but NOT title
        if "implementation_steps" in props and "title" not in props:
            return "detail"

    return "unknown"


def _extract_prompt_text(body: dict) -> str:
    """Extract the user prompt text from various API formats."""
    # OpenAI Responses API — input can be a string or list of message objects
    input_field = body.get("input")
    if isinstance(input_field, str) and input_field:
        return input_field
    if isinstance(input_field, list):
        for item in input_field:
            if isinstance(item, dict):
                content = item.get("content", "")
                if isinstance(content, str) and content:
                    return content
    # OpenAI Chat Completions / Anthropic Messages
    for message in body.get("messages", []):
        if message.get("role") == "user":
            content = message.get("content", "")
            if isinstance(content, str) and content:
                return content
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        return block.get("text", "")
    return str(body)


def _openai_responses_envelope(content: object) -> dict:
    """Response format for the OpenAI Responses API (/v1/responses)."""
    return {
        "id": "resp_mock",
        "object": "response",
        "model": "gpt-5.1",
        "status": "completed",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(content),
                        "annotations": [],
                    }
                ],
            }
        ],
        "usage": {
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
        },
    }


def _openai_chat_envelope(content: object) -> dict:
    """Response format for OpenAI Chat Completions API."""
    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "gpt-5.1",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(content),
                    "refusal": None,
                },
                "finish_reason": "stop",
                "logprobs": None,
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        },
    }


def _anthropic_envelope(content: object) -> dict:
    return {
        "id": "msg_mock",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": json.dumps(content)}],
        "model": "claude-opus-4-6-20251101",
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }


def _load_jwks() -> dict:
    """Load the E2E test JWKS from the e2e-keys directory."""
    jwks_path = os.path.join(os.path.dirname(__file__), "e2e-keys", "jwks.json")
    with open(jwks_path) as f:
        return json.load(f)


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:  # noqa: N802
        print(f"[mock-ai] {self.path} — {fmt % args}")

    def do_GET(self) -> None:  # noqa: N802
        """Health probe + mock company website + JWKS for E2E auth."""
        if self.path.startswith("/company"):
            self._send_html(_MOCK_COMPANY_HTML, 200)
        elif self.path.endswith("/.well-known/jwks.json"):
            self._send_json(_load_jwks(), 200)
        else:
            self._send_json({"status": "ok"}, 200)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body: dict = json.loads(self.rfile.read(length)) if length else {}

        step = _detect_step(body)
        content = _MOCK_RESPONSES.get(step, {"result": "mock"})

        if self.path.endswith("/messages"):
            response = _anthropic_envelope(content)
        elif self.path.endswith("/responses"):
            response = _openai_responses_envelope(content)
        else:
            response = _openai_chat_envelope(content)

        self._send_json(response, 200)

    def _send_json(self, data: object, status: int) -> None:
        payload = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_html(self, html: str, status: int) -> None:
        payload = html.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", _PORT), _Handler)
    print(f"[mock-ai] Listening on :{_PORT}")
    server.serve_forever()
