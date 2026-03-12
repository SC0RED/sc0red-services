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
    # AssessRisk
    "risk_scores": {
        "risk_scores": [
            {
                "category": "technology_obsolescence",
                "score": 5.0,
                "explanation": "Moderate technology risk given current stack.",
                "evidence": "Standard tech choices with some legacy components.",
            },
            {
                "category": "competitive_displacement",
                "score": 5.0,
                "explanation": "Moderate competitive pressure from AI-native entrants.",
                "evidence": "Several well-funded competitors in the space.",
            },
            {
                "category": "talent_workforce",
                "score": 4.0,
                "explanation": "Low talent risk; stable engineering team.",
                "evidence": "Low attrition signals from job postings.",
            },
            {
                "category": "customer_behavior",
                "score": 4.0,
                "explanation": "Low customer churn risk.",
                "evidence": "Long-term contract structure observed.",
            },
            {
                "category": "regulatory_compliance",
                "score": 3.0,
                "explanation": "Low regulatory exposure in current markets.",
                "evidence": "No significant compliance flags visible.",
            },
            {
                "category": "data_ip",
                "score": 4.0,
                "explanation": "Low data and IP risk.",
                "evidence": "Standard data handling practices.",
            },
            {
                "category": "margin_compression",
                "score": 5.0,
                "explanation": "Moderate margin pressure from infrastructure costs.",
                "evidence": "Cloud cost trends visible in pricing.",
            },
            {
                "category": "supply_chain",
                "score": 3.0,
                "explanation": "Minimal supply chain risk for SaaS model.",
                "evidence": "Software-only product with no physical supply chain.",
            },
        ],
        "overall_score": 4.1,
        "tier": "moderate",
        "top_risks": [
            "technology_obsolescence",
            "competitive_displacement",
            "margin_compression",
        ],
        "analysis_summary": (
            "Mock risk assessment for E2E testing. "
            "Overall moderate risk profile with manageable exposure across key categories."
        ),
    },
    # GenerateOpportunities
    "opportunities": {
        "opportunities": [
            {
                "title": "Adopt AI-powered workflow automation",
                "risk_mitigated": "technology_obsolescence",
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
                "related_services": [
                    {
                        "service_type": "AI Platform",
                        "vendors": [
                            {
                                "name": "Mock AI Co",
                                "url": "https://mock-ai.example.com",
                                "specialty": "Workflow automation",
                            }
                        ],
                    }
                ],
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
        for key in ("actual_url", "company_name", "risk_scores", "opportunities"):
            if key in props:
                return key

    return "unknown"


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
