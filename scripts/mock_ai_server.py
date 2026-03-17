"""Minimal mock AI server for E2E / integration testing.

Handles OpenAI  POST /v1/chat/completions
      Anthropic POST /v1/messages

Routes by inspecting the json_schema properties to identify which pipeline
step is calling and returns a structurally valid mock response.

No external dependencies — pure stdlib. Run with: python mock_ai_server.py
"""

from __future__ import annotations

import json
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
                "rationale": "Moderate competitive pressure from AI-native entrants with several well-funded competitors in the space.",
            },
            {
                "category": "technology_obsolescence",
                "score": 5.0,
                "rationale": "Moderate technology risk given current stack with standard tech choices and some legacy components.",
            },
            {
                "category": "customer_behavior",
                "score": 4.0,
                "rationale": "Low customer churn risk with long-term contract structure observed.",
            },
            {
                "category": "margin_compression",
                "score": 5.0,
                "rationale": "Moderate margin pressure from infrastructure costs with cloud cost trends visible in pricing.",
            },
        ],
    },
    # AssessRisk — Batch B (internal/operational risks)
    "risk_scores_batch_b": {
        "risk_scores": [
            {
                "category": "talent_workforce",
                "score": 4.0,
                "rationale": "Low talent risk with stable engineering team and low attrition signals from job postings.",
            },
            {
                "category": "regulatory_compliance",
                "score": 3.0,
                "rationale": "Low regulatory exposure in current markets with no significant compliance flags visible.",
            },
            {
                "category": "supply_chain",
                "score": 3.0,
                "rationale": "Minimal supply chain risk for SaaS model with software-only product and no physical supply chain.",
            },
            {
                "category": "data_ip",
                "score": 4.0,
                "rationale": "Low data and IP risk with standard data handling practices.",
            },
        ],
    },
    # GenerateEbitdaTree (flat node format with parent_id references)
    "nodes": {
        "summary": "E2E Test Corp operates a subscription SaaS model with primary revenue from platform fees and analytics add-ons. AI opportunities have the most impact on operational efficiency and revenue expansion.",
        "revenue_estimate": "$5M-$15M",
        "ebitda_estimate": "$1M-$3M (15-25% margin)",
        "nodes": [
            {
                "id": "revenue",
                "parent_id": None,
                "label": "Total Revenue",
                "type": "revenue",
                "value_range": "$5M-$15M",
                "percentage_of_parent": None,
                "description": "Combined subscription and services revenue",
            },
            {
                "id": "platform_subscriptions",
                "parent_id": "revenue",
                "label": "Platform Subscriptions",
                "type": "revenue",
                "value_range": "$4M-$12M",
                "percentage_of_parent": 80,
                "description": "Annual SaaS subscription fees",
            },
            {
                "id": "services",
                "parent_id": "revenue",
                "label": "Professional Services",
                "type": "revenue",
                "value_range": "$1M-$3M",
                "percentage_of_parent": 20,
                "description": "Implementation and consulting services",
            },
            {
                "id": "cogs",
                "parent_id": None,
                "label": "Cost of Revenue",
                "type": "cost",
                "value_range": "$1.5M-$4.5M",
                "percentage_of_parent": 30,
                "description": "Cloud infrastructure and support costs",
            },
            {
                "id": "gross_profit",
                "parent_id": None,
                "label": "Gross Profit",
                "type": "subtotal",
                "value_range": "$3.5M-$10.5M",
                "percentage_of_parent": 70,
                "description": "Revenue minus cost of revenue",
            },
            {
                "id": "opex_rnd",
                "parent_id": None,
                "label": "R&D Expense",
                "type": "cost",
                "value_range": "$1M-$3M",
                "percentage_of_parent": 20,
                "description": "Engineering and product development",
            },
            {
                "id": "opex_sga",
                "parent_id": None,
                "label": "SG&A Expense",
                "type": "cost",
                "value_range": "$1M-$3M",
                "percentage_of_parent": 20,
                "description": "Sales, general and administrative expenses",
            },
            {
                "id": "ebitda",
                "parent_id": None,
                "label": "EBITDA",
                "type": "subtotal",
                "value_range": "$1M-$3M",
                "percentage_of_parent": None,
                "description": "Earnings before interest, taxes, depreciation and amortisation",
            },
        ],
    },
    # GenerateOpportunities
    "opportunities": {
        "opportunities": [
            {
                "title": "Adopt AI-powered workflow automation",
                "impact_rating": "High",
                "strategic_category": "Competitive Moat",
                "description": (
                    "Implement AI-driven automation to reduce manual overhead. "
                    "This creates a defensible efficiency advantage."
                ),
                "implementation_steps": [
                    "Audit current manual workflows",
                    "Pilot AI tooling on highest-volume tasks",
                    "Roll out across the organisation",
                ],
                "timeline": "Quick Win (1-3 months)",
                "investment_range": "$50K-$100K",
                "roi_estimate": "2x ROI within 12 months through headcount reallocation",
                "related_services": ["Mock AI Co - Workflow automation"],
                "value_lever": "Cost Side",
            }
        ],
        "top_three_immediate_actions": [
            "Audit current automation coverage",
            "Identify highest-ROI AI use cases",
            "Build internal AI literacy programme",
        ],
    },
}


def _detect_step(body: dict) -> str:
    """Return the key in _MOCK_RESPONSES that matches this request's schema.

    Handles both:
     - OpenAI Responses API: body["text"]["format"]["schema"]["properties"]
     - OpenAI Chat Completions API: body["response_format"]["json_schema"]["schema"]["properties"]
     - Anthropic Messages API: body["response_format"]["json_schema"]["schema"]["properties"]

    For risk assessment, dispatches to batch A or B by inspecting the prompt
    for batch-specific category keywords (competitive_displacement = batch A,
    talent_workforce = batch B).
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
        for key in ("actual_url", "company_name", "nodes", "opportunities"):
            if key in props:
                return key
        if "risk_scores" in props:
            # Dispatch risk batches by checking prompt for category keywords
            prompt_text = _extract_prompt_text(body)
            if "competitive_displacement" in prompt_text:
                return "risk_scores_batch_a"
            return "risk_scores_batch_b"

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
                # Message format: {"role": "user", "content": "..."}
                content = item.get("content", "")
                if isinstance(content, str) and content:
                    return content
    # OpenAI Chat Completions / Anthropic Messages
    for message in body.get("messages", []):
        if message.get("role") == "user":
            content = message.get("content", "")
            if isinstance(content, str) and content:
                return content
            # Anthropic format: content is a list of blocks
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        return block.get("text", "")
    # Last resort: stringify the entire body and search
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
        "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
    }


def _openai_chat_envelope(content: object) -> dict:
    """Response format for the OpenAI Chat Completions API (/v1/chat/completions)."""
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
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
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


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:  # noqa: N802
        print(f"[mock-ai] {self.path} — {fmt % args}")

    def do_GET(self) -> None:  # noqa: N802
        """Health probe + mock company website for E2E scraper."""
        if self.path.startswith("/company"):
            self._send_html(_MOCK_COMPANY_HTML, 200)
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
