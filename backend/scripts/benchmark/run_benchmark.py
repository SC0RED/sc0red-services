#!/usr/bin/env python3
"""AI Model Benchmark Runner for sc0red Assessment Engine.

Sends curated prompts to a specified model via the OpenAI Responses API,
captures output quality, cost, latency, and schema compliance.

Usage:
    python run_benchmark.py --model gpt-5.1
    python run_benchmark.py --model gpt-5.4-mini --baseline
    python run_benchmark.py --model gpt-5.1 --prompts custom_prompts.json
"""

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

import openai

# Pricing per 1M tokens — update when models change
MODEL_PRICING = {
    "gpt-5.1": {"input": 1.25, "output": 10.00, "web_search": 0.01},
    "gpt-5.4-mini": {"input": 0.75, "output": 4.50, "web_search": 0.01},
    "gpt-5.5": {"input": 5.00, "output": 30.00, "web_search": 0.01},
    # Add new models here
}

# Defaults for unknown models
DEFAULT_PRICING = {"input": 1.00, "output": 5.00, "web_search": 0.01}


def load_prompts(prompts_path: str) -> dict:
    """Load benchmark prompts from JSON file."""
    with open(prompts_path) as f:
        return json.load(f)


def build_tools(tool_names: list[str] | None) -> list[dict] | None:
    """Build OpenAI tools config from tool name list."""
    if not tool_names:
        return None
    # ``web_search_preview`` is emitted at most once even if multiple tool aliases
    # for it are present. Other tool names are reserved for future use.
    tools: list[dict] = []
    if "web_search" in tool_names:
        tools.append({"type": "web_search_preview"})
    return tools or None


def run_single_prompt(client: openai.OpenAI, model: str, prompt: dict) -> dict:
    """Run a single benchmark prompt and capture results."""
    prompt_id = prompt["id"]
    task_type = prompt["task_type"]
    schema = prompt["json_schema"]
    tools = build_tools(prompt.get("tools"))

    # Build input — handle both string and list (chat messages) prompts
    input_text = prompt["prompt"]

    # Build request params. Mirror what Janus production sends so the
    # benchmark is a faithful proxy: system prompt via ``instructions``,
    # ``reasoning.effort`` and ``text.verbosity`` from the prompt envelope.
    text_block: dict[str, object] = {
        "format": {
            "type": "json_schema",
            "name": schema["name"],
            "schema": schema["schema"],
            "strict": True,
        }
    }
    verbosity = prompt.get("verbosity")
    if verbosity:
        text_block["verbosity"] = verbosity

    request_params: dict[str, object] = {
        "model": model,
        "input": input_text,
        "text": text_block,
    }

    system_prompt = prompt.get("system_prompt")
    if system_prompt:
        request_params["instructions"] = system_prompt

    reasoning_effort = prompt.get("reasoning_effort")
    if reasoning_effort:
        request_params["reasoning"] = {"effort": reasoning_effort}

    if tools:
        request_params["tools"] = tools

    # Execute and time
    start_time = time.monotonic()
    error = None
    response = None
    content = None

    try:
        response = client.responses.create(**request_params)
        content = json.loads(response.output_text)
    except json.JSONDecodeError as e:
        error = f"JSON parse error: {e}"
        content = {"_raw_text": response.output_text if response else None}
    except openai.APIError as e:
        error = f"API error: {e}"
    except Exception as e:
        error = f"Unexpected error: {e}"

    elapsed = time.monotonic() - start_time

    # Extract token usage
    input_tokens = 0
    output_tokens = 0
    if response and hasattr(response, "usage") and response.usage:
        input_tokens = response.usage.input_tokens or 0
        output_tokens = response.usage.output_tokens or 0

    # Calculate cost
    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
    cost = (
        (input_tokens * pricing["input"] / 1_000_000)
        + (output_tokens * pricing["output"] / 1_000_000)
    )

    # Check if web search was used and add cost
    web_search_used = False
    if response and tools:
        for item in response.output or []:
            if getattr(item, "type", None) in ("web_search_call",):
                web_search_used = True
                cost += pricing.get("web_search", 0)
                break

    # Schema compliance check — verify required fields are present
    schema_compliant = True
    missing_fields = []
    if content and not error:
        required = schema["schema"].get("required", [])
        for field in required:
            if field not in content:
                schema_compliant = False
                missing_fields.append(field)

        # Check nested required fields
        for field, props in schema["schema"].get("properties", {}).items():
            if isinstance(props, dict) and props.get("type") == "object" and field in content:
                nested_required = props.get("required", [])
                for nfield in nested_required:
                    if nfield not in content.get(field, {}):
                        schema_compliant = False
                        missing_fields.append(f"{field}.{nfield}")

    return {
        "prompt_id": prompt_id,
        "task_type": task_type,
        "description": prompt.get("description", ""),
        "model": model,
        "content": content,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cost_usd": round(cost, 6),
        "latency_seconds": round(elapsed, 3),
        "schema_compliant": schema_compliant,
        "missing_fields": missing_fields,
        "web_search_used": web_search_used,
        "error": error,
    }


# Per-call request budget. Bounds the worst case when the model hits a
# slow path (the same tail-latency pathology this benchmark was built to
# investigate). Production uses 180s but typical Janus AI calls finish
# in 2-30s; 90s catches the tail without truncating legitimate work, and
# the single retry doubles the effective ceiling to ~180s before the
# benchmark records the call as a timeout error.
_REQUEST_TIMEOUT_SECONDS = 90.0
_MAX_RETRIES = 1


def run_benchmark(model: str, prompts_path: str, output_dir: str, baseline: bool = False) -> str:
    """Run full benchmark suite against a model."""
    data = load_prompts(prompts_path)
    prompts = data["prompts"]

    # Tight timeout + single retry. Without this the SDK defaults to a
    # 600 s per-request timeout and 2 retries — a single stuck call can
    # block the benchmark for 30 min. With 90 s x 2 attempts, worst case
    # per prompt is ~3 min, and the runner records ``error="API error: ..."``
    # in the result rather than hanging.
    client = openai.OpenAI(
        timeout=_REQUEST_TIMEOUT_SECONDS,
        max_retries=_MAX_RETRIES,
    )

    print(f"\n{'='*60}")
    print(f"  AI Model Benchmark — {model}")
    print(f"  {len(prompts)} prompts across {len({p['task_type'] for p in prompts})} task types")
    print(f"{'='*60}\n")

    results = []
    total_cost = 0.0
    total_latency = 0.0
    errors = 0
    schema_failures = 0

    for i, prompt in enumerate(prompts, 1):
        task = prompt["task_type"]
        desc = prompt.get("description", prompt["id"])
        print(f"  [{i}/{len(prompts)}] {task}: {desc}...", end=" ", flush=True)

        result = run_single_prompt(client, model, prompt)
        results.append(result)

        total_cost += result["cost_usd"]
        total_latency += result["latency_seconds"]

        if result["error"]:
            errors += 1
            print(f"ERROR ({result['latency_seconds']:.1f}s)")
        elif not result["schema_compliant"]:
            schema_failures += 1
            print(f"SCHEMA FAIL ({result['latency_seconds']:.1f}s) — missing: {result['missing_fields']}")
        else:
            print(f"OK ({result['latency_seconds']:.1f}s, ${result['cost_usd']:.4f})")

    # Summary
    print(f"\n{'='*60}")
    print("  RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"  Model:            {model}")
    print(f"  Prompts:          {len(prompts)}")
    print(f"  Passed:           {len(prompts) - errors - schema_failures}")
    print(f"  Schema failures:  {schema_failures}")
    print(f"  Errors:           {errors}")
    print(f"  Total cost:       ${total_cost:.4f}")
    print(f"  Total latency:    {total_latency:.1f}s")
    print(f"  Avg latency:      {total_latency / len(prompts):.1f}s")
    print(f"{'='*60}\n")

    # Build output
    output = {
        "metadata": {
            "model": model,
            "timestamp": datetime.now(UTC).isoformat(),
            "prompts_file": prompts_path,
            "prompt_count": len(prompts),
            "is_baseline": baseline,
        },
        "summary": {
            "total_cost_usd": round(total_cost, 6),
            "total_latency_seconds": round(total_latency, 3),
            "avg_latency_seconds": round(total_latency / len(prompts), 3),
            "schema_compliance_rate": round(
                (len(prompts) - schema_failures - errors) / len(prompts), 4
            ),
            "error_count": errors,
        },
        "results": results,
    }

    # Write output
    os.makedirs(output_dir, exist_ok=True)
    if baseline:
        filename = f"{model}_baseline.json"
    else:
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        filename = f"{model}_{date_str}.json"

    output_path = os.path.join(output_dir, filename)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"  Results saved to: {output_path}\n")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="AI Model Benchmark Runner")
    parser.add_argument("--model", required=True, help="Model name (e.g., gpt-5.1, gpt-5.4-mini)")
    parser.add_argument(
        "--prompts",
        default=str(Path(__file__).parent / "benchmark_prompts.json"),
        help="Path to prompts JSON file",
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).parent / "results"),
        help="Output directory for results",
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Save as baseline reference for future comparisons",
    )

    args = parser.parse_args()
    run_benchmark(args.model, args.prompts, args.output, args.baseline)


if __name__ == "__main__":
    main()
