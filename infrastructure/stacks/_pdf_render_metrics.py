"""CloudWatch metric filters + dashboard for the PDF render Lambda.

Extracted from `pdf_render_construct.py` to keep that file under the
400-line spirit-of-the-rule limit (CLAUDE.md backend guideline). The
metric filters convert structured log lines emitted by the Lambda
handler — `{"event":"pdf_render","status":"ok","durationMs":1234,...}`
— into CloudWatch metrics for the `sc0red Services/<env>/PdfRender` namespace,
plus a dashboard in monitored environments.

Operations are exposed as a free function so the construct can call it
once from `__init__` without owning the metric-construct boilerplate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cdk import Duration
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_logs as logs

if TYPE_CHECKING:
    from constructs import Construct


def build_pdf_render_metrics(
    scope: Construct,
    *,
    log_group: logs.ILogGroup,
    environment: str,
    config: dict[str, Any],
) -> None:
    """Build the per-render metric filters + dashboard.

    The metric filters tap the Lambda's structured log lines:
    - ``status=ok`` → publishes ``RenderDurationMs``, ``RenderPageCount``,
      ``RenderPdfSizeBytes`` (capacity planning).
    - ``status=error`` → publishes ``RenderErrorCount`` (server-side
      failures; page on any).
    - ``status=reject`` → publishes ``RenderRejectCount`` (token / parse
      failures; alert on sustained rate).

    The dashboard is only created in monitored environments
    (``config["enable_monitoring"]``) — dev environments don't need
    paging surface area.
    """
    metric_namespace = f"sc0red Services/{environment.capitalize()}/PdfRender"

    # Successful-render filter: matches `event=pdf_render` AND `status=ok`.
    ok_pattern = logs.FilterPattern.all(
        logs.FilterPattern.string_value("$.event", "=", "pdf_render"),
        logs.FilterPattern.string_value("$.status", "=", "ok"),
    )

    for metric_name, json_path in (
        ("RenderDurationMs", "$.durationMs"),
        ("RenderPageCount", "$.pageCount"),
        ("RenderPdfSizeBytes", "$.pdfSizeBytes"),
    ):
        logs.MetricFilter(
            scope,
            f"{metric_name}Filter",
            log_group=log_group,
            metric_namespace=metric_namespace,
            metric_name=metric_name,
            filter_pattern=ok_pattern,
            metric_value=json_path,
        )

    # Failure counters. ``error`` is server-side; ``reject`` is token /
    # parse — separate metrics so alarm thresholds target the right
    # severity (errors: page on any; rejects: alert on rate).
    for failure_status, metric_name in (
        ("error", "RenderErrorCount"),
        ("reject", "RenderRejectCount"),
    ):
        logs.MetricFilter(
            scope,
            f"{metric_name}Filter",
            log_group=log_group,
            metric_namespace=metric_namespace,
            metric_name=metric_name,
            filter_pattern=logs.FilterPattern.all(
                logs.FilterPattern.string_value("$.event", "=", "pdf_render"),
                logs.FilterPattern.string_value("$.status", "=", failure_status),
            ),
            metric_value="1",
            default_value=0,
        )

    if not config.get("enable_monitoring"):
        return

    cloudwatch.Dashboard(
        scope,
        "PdfRenderDashboard",
        dashboard_name=f"sc0red-services-pdf-render-{environment}",
        widgets=[
            [
                cloudwatch.GraphWidget(
                    title="Render duration (ms)",
                    left=[
                        cloudwatch.Metric(
                            namespace=metric_namespace,
                            metric_name="RenderDurationMs",
                            statistic="p95",
                            period=Duration.minutes(5),
                        )
                    ],
                    width=12,
                ),
                cloudwatch.GraphWidget(
                    title="PDF size (bytes)",
                    left=[
                        cloudwatch.Metric(
                            namespace=metric_namespace,
                            metric_name="RenderPdfSizeBytes",
                            statistic="Average",
                            period=Duration.minutes(5),
                        )
                    ],
                    width=12,
                ),
            ],
            [
                cloudwatch.GraphWidget(
                    title="Pages per render",
                    left=[
                        cloudwatch.Metric(
                            namespace=metric_namespace,
                            metric_name="RenderPageCount",
                            statistic="Average",
                            period=Duration.minutes(5),
                        )
                    ],
                    width=12,
                ),
                cloudwatch.GraphWidget(
                    title="Failures (5-min)",
                    left=[
                        cloudwatch.Metric(
                            namespace=metric_namespace,
                            metric_name="RenderErrorCount",
                            label="Errors (server-side)",
                            statistic="Sum",
                            period=Duration.minutes(5),
                        ),
                        cloudwatch.Metric(
                            namespace=metric_namespace,
                            metric_name="RenderRejectCount",
                            label="Rejects (token / parse)",
                            statistic="Sum",
                            period=Duration.minutes(5),
                        ),
                    ],
                    width=12,
                ),
            ],
        ],
    )
