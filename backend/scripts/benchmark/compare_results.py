#!/usr/bin/env python3
"""Compare two benchmark runs and produce a report.

Usage:
    python compare_results.py --baseline results/gpt-5.1_baseline.json --candidate results/gpt-5.4-mini_2026-03-29.json
    python compare_results.py --baseline results/gpt-5.1_baseline.json --candidate results/gpt-5.4-mini_2026-03-29.json --output report.md
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path


def load_results(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def pct_change(baseline: float, candidate: float) -> str:
    """Format percentage change with direction."""
    if baseline == 0:
        return "N/A"
    change = ((candidate - baseline) / baseline) * 100
    sign = "+" if change > 0 else ""
    return f"{sign}{change:.1f}%"


def cost_delta_label(change_pct: float) -> str:
    """Human-readable label for cost change."""
    if change_pct < -20:
        return "🟢 significant savings"
    if change_pct < -5:
        return "🟢 moderate savings"
    if change_pct < 5:
        return "⚪ comparable"
    if change_pct < 20:
        return "🟡 moderate increase"
    return "🔴 significant increase"


def latency_delta_label(change_pct: float) -> str:
    if change_pct < -20:
        return "🟢 much faster"
    if change_pct < -5:
        return "🟢 faster"
    if change_pct < 5:
        return "⚪ comparable"
    if change_pct < 20:
        return "🟡 slower"
    return "🔴 much slower"


def compare_content(baseline_content: dict | None, candidate_content: dict | None) -> dict:
    """Compare two structured outputs and flag differences."""
    if not baseline_content or not candidate_content:
        return {"comparable": False, "reason": "missing content"}

    diffs = {}
    all_keys = set(list(baseline_content.keys()) + list(candidate_content.keys()))

    for key in all_keys:
        b_val = baseline_content.get(key)
        c_val = candidate_content.get(key)

        if b_val == c_val:
            continue

        # For enum/categorical fields, flag exact differences
        if isinstance(b_val, str) and isinstance(c_val, str):
            # Check if these are assessment-type enum values
            enum_values = {"yes", "no", "likely", "unlikely", "unclear", "1", "2", "3", "4", "5"}
            if b_val.lower() in enum_values or c_val.lower() in enum_values:
                diffs[key] = {
                    "type": "categorical_change",
                    "baseline": b_val,
                    "candidate": c_val,
                    "severity": "high",
                }
            else:
                # Narrative field — flag length difference
                b_len = len(b_val)
                c_len = len(c_val)
                len_ratio = c_len / b_len if b_len > 0 else 0
                diffs[key] = {
                    "type": "narrative_change",
                    "baseline_length": b_len,
                    "candidate_length": c_len,
                    "length_ratio": round(len_ratio, 2),
                    "severity": "low" if 0.5 < len_ratio < 2.0 else "medium",
                }
        elif isinstance(b_val, dict) and isinstance(c_val, dict):
            nested = compare_content(b_val, c_val)
            if nested.get("diffs"):
                diffs[key] = {"type": "nested", "nested_diffs": nested["diffs"]}
        else:
            diffs[key] = {
                "type": "value_change",
                "baseline": str(b_val)[:200],
                "candidate": str(c_val)[:200],
            }

    return {"comparable": True, "diffs": diffs, "identical": len(diffs) == 0}


def generate_report(baseline: dict, candidate: dict) -> str:
    """Generate a markdown comparison report."""
    b_meta = baseline["metadata"]
    c_meta = candidate["metadata"]
    b_summary = baseline["summary"]
    c_summary = candidate["summary"]

    # Build prompt lookup
    b_results = {r["prompt_id"]: r for r in baseline["results"]}
    c_results = {r["prompt_id"]: r for r in candidate["results"]}

    # Cost and latency deltas
    cost_change = (
        ((c_summary["total_cost_usd"] - b_summary["total_cost_usd"]) / b_summary["total_cost_usd"] * 100)
        if b_summary["total_cost_usd"] > 0
        else 0
    )
    latency_change = (
        ((c_summary["avg_latency_seconds"] - b_summary["avg_latency_seconds"]) / b_summary["avg_latency_seconds"] * 100)
        if b_summary["avg_latency_seconds"] > 0
        else 0
    )

    lines = []
    lines.append("# AI Model Benchmark Comparison")
    lines.append("")
    lines.append(f"**Baseline:** {b_meta['model']} ({b_meta['timestamp'][:10]})")
    lines.append(f"**Candidate:** {c_meta['model']} ({c_meta['timestamp'][:10]})")
    lines.append(f"**Prompts:** {b_meta['prompt_count']}")
    lines.append("")

    # Aggregate metrics
    lines.append("## Aggregate Metrics")
    lines.append("")
    lines.append(f"| Metric | {b_meta['model']} | {c_meta['model']} | Delta |")
    lines.append("|--------|---------|-----------|-------|")
    lines.append(
        f"| Total cost | ${b_summary['total_cost_usd']:.4f} | ${c_summary['total_cost_usd']:.4f} | "
        f"{pct_change(b_summary['total_cost_usd'], c_summary['total_cost_usd'])} {cost_delta_label(cost_change)} |"
    )
    lines.append(
        f"| Avg latency | {b_summary['avg_latency_seconds']:.1f}s | {c_summary['avg_latency_seconds']:.1f}s | "
        f"{pct_change(b_summary['avg_latency_seconds'], c_summary['avg_latency_seconds'])} {latency_delta_label(latency_change)} |"
    )
    lines.append(
        f"| Schema compliance | {b_summary['schema_compliance_rate']*100:.0f}% | {c_summary['schema_compliance_rate']*100:.0f}% | "
        f"{pct_change(b_summary['schema_compliance_rate'], c_summary['schema_compliance_rate'])} |"
    )
    lines.append(
        f"| Errors | {b_summary['error_count']} | {c_summary['error_count']} | |"
    )
    lines.append("")

    # Per-task-type breakdown
    lines.append("## Per-Task-Type Breakdown")
    lines.append("")

    task_types = defaultdict(lambda: {"b_cost": 0, "c_cost": 0, "b_latency": 0, "c_latency": 0, "count": 0, "diffs": 0})
    for pid in b_results:
        if pid not in c_results:
            continue
        b = b_results[pid]
        c = c_results[pid]
        tt = b["task_type"]
        task_types[tt]["count"] += 1
        task_types[tt]["b_cost"] += b["cost_usd"]
        task_types[tt]["c_cost"] += c["cost_usd"]
        task_types[tt]["b_latency"] += b["latency_seconds"]
        task_types[tt]["c_latency"] += c["latency_seconds"]

        comparison = compare_content(b.get("content"), c.get("content"))
        if comparison.get("diffs"):
            task_types[tt]["diffs"] += 1

    lines.append("| Task Type | Count | Cost Δ | Latency Δ | Content Diffs |")
    lines.append("|-----------|-------|--------|-----------|---------------|")
    for tt, data in sorted(task_types.items()):
        lines.append(
            f"| {tt} | {data['count']} | "
            f"{pct_change(data['b_cost'], data['c_cost'])} | "
            f"{pct_change(data['b_latency'], data['c_latency'])} | "
            f"{data['diffs']}/{data['count']} |"
        )
    lines.append("")

    # Per-prompt detail
    lines.append("## Per-Prompt Comparison")
    lines.append("")

    for pid in b_results:
        if pid not in c_results:
            continue

        b = b_results[pid]
        c = c_results[pid]
        comparison = compare_content(b.get("content"), c.get("content"))

        # Flag icon
        if b.get("error") or c.get("error"):
            flag = "🔴"
        elif comparison.get("diffs"):
            # Check severity
            high_severity = any(
                d.get("severity") == "high"
                for d in comparison["diffs"].values()
                if isinstance(d, dict)
            )
            flag = "🔴" if high_severity else "🟡"
        else:
            flag = "🟢"

        lines.append(f"### {flag} {pid}: {b.get('description', '')}")
        lines.append("")
        lines.append(f"| | {b_meta['model']} | {c_meta['model']} |")
        lines.append("|---|---|---|")
        lines.append(f"| Cost | ${b['cost_usd']:.4f} | ${c['cost_usd']:.4f} |")
        lines.append(f"| Latency | {b['latency_seconds']:.1f}s | {c['latency_seconds']:.1f}s |")
        lines.append(f"| Tokens | {b['total_tokens']} | {c['total_tokens']} |")
        lines.append(f"| Schema OK | {'✅' if b['schema_compliant'] else '❌'} | {'✅' if c['schema_compliant'] else '❌'} |")

        if comparison.get("diffs"):
            lines.append("")
            lines.append("**Content differences:**")
            for field, diff in comparison["diffs"].items():
                if diff.get("type") == "categorical_change":
                    lines.append(f"- ⚠️ **{field}**: `{diff['baseline']}` → `{diff['candidate']}`")
                elif diff.get("type") == "narrative_change":
                    lines.append(
                        f"- {field}: length {diff['baseline_length']} → {diff['candidate_length']} "
                        f"(ratio: {diff['length_ratio']}x)"
                    )
                elif diff.get("type") == "nested":
                    for nfield, ndiff in diff.get("nested_diffs", {}).items():
                        if ndiff.get("type") == "categorical_change":
                            lines.append(f"- ⚠️ **{field}.{nfield}**: `{ndiff['baseline']}` → `{ndiff['candidate']}`")
                        else:
                            lines.append(f"- {field}.{nfield}: changed")
        elif comparison.get("identical"):
            lines.append("")
            lines.append("Content: ✅ identical")

        if b.get("error"):
            lines.append(f"- Baseline error: {b['error']}")
        if c.get("error"):
            lines.append(f"- Candidate error: {c['error']}")

        lines.append("")

    # Recommendation
    lines.append("## Recommendation")
    lines.append("")

    # Count high-severity diffs
    high_diffs = 0
    total_compared = 0
    for pid in b_results:
        if pid not in c_results:
            continue
        total_compared += 1
        comparison = compare_content(b_results[pid].get("content"), c_results[pid].get("content"))
        if comparison.get("diffs"):
            for d in comparison["diffs"].values():
                if isinstance(d, dict) and d.get("severity") == "high":
                    high_diffs += 1
                    break

    if c_summary["error_count"] > b_summary["error_count"]:
        lines.append("⛔ **Do not switch.** Candidate has more errors than baseline.")
    elif high_diffs > total_compared * 0.3:
        lines.append(
            f"⚠️ **Proceed with caution.** {high_diffs}/{total_compared} prompts have high-severity "
            f"content differences (assessment/score changes). Review each manually before switching."
        )
    elif cost_change < -10 and high_diffs <= 2:
        lines.append(
            f"✅ **Good candidate.** {pct_change(b_summary['total_cost_usd'], c_summary['total_cost_usd'])} cost change "
            f"with {high_diffs} high-severity content differences. Manual review of flagged prompts recommended."
        )
    else:
        lines.append(
            f"ℹ️ **Mixed results.** Cost: {pct_change(b_summary['total_cost_usd'], c_summary['total_cost_usd'])}, "
            f"Latency: {pct_change(b_summary['avg_latency_seconds'], c_summary['avg_latency_seconds'])}, "
            f"Content diffs: {high_diffs}/{total_compared} high-severity. Review needed."
        )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Compare AI Model Benchmark Results")
    parser.add_argument("--baseline", required=True, help="Path to baseline results JSON")
    parser.add_argument("--candidate", required=True, help="Path to candidate results JSON")
    parser.add_argument("--output", default=None, help="Path to write markdown report (default: stdout + auto-save)")

    args = parser.parse_args()

    baseline = load_results(args.baseline)
    candidate = load_results(args.candidate)

    report = generate_report(baseline, candidate)

    # Print to terminal
    print(report)

    # Save report
    if args.output:
        output_path = args.output
    else:
        b_model = baseline["metadata"]["model"]
        c_model = candidate["metadata"]["model"]
        output_path = str(Path(args.baseline).parent / f"comparison_{b_model}_vs_{c_model}.md")

    with open(output_path, "w") as f:
        f.write(report)
    print(f"\nReport saved to: {output_path}")


if __name__ == "__main__":
    main()
