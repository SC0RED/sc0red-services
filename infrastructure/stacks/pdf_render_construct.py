"""PDF render Lambda — Node.js + headless Chromium.

Defines the `pdf-render` Lambda function (Node.js 20.x), the
`@sparticuz/chromium` layer it depends on, the Secrets Manager-backed
`PDF_TOKEN_SECRET` that signs URL tokens for the headless render flow,
and the IAM role that lets the API Lambda invoke it.

The Lambda itself runs no business logic — it accepts a JSON payload
of `{analysisId, token, frontendBaseUrl, companyName}`, validates the
HMAC token, navigates to `/print/{analysisId}?t={token}` via Puppeteer,
and returns the PDF buffer base64-encoded. See `backend/lambdas/pdf-render/`.
"""

from __future__ import annotations

from typing import Any

import aws_cdk as cdk
from aws_cdk import CfnOutput, Duration
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

# Reserved concurrency cap. See design.md D7: a runaway loop (e.g., a
# user triple-clicking Export PDF) won't burn through the account-wide
# concurrency limit.
RESERVED_CONCURRENCY = 5

# Lambda timeout. Headroom over the in-Lambda render timeout (25s by
# default in render.ts) so the API Gateway integration doesn't cut us
# off mid-render.
TIMEOUT_SECONDS = 30

# Memory size — Chromium needs 1GB minimum to render reliably; 1024MB
# gives a 100ms-class CPU allocation on Lambda.
MEMORY_MB = 1024


class PdfRenderConstruct(Construct):
    """PDF render Lambda + supporting resources (secret, layer, IAM)."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        environment: str,
        config: dict[str, Any],
    ) -> None:
        super().__init__(scope, construct_id)
        self._environment = environment
        self._config = config

        self._token_secret = self._build_token_secret()
        self._internal_api_key = self._build_internal_api_key()
        self._function = self._build_function()
        self._build_metrics(self._function.log_group)

        # Surface the Lambda ARN so the API Lambda's environment can pick
        # it up in `janus_stack.py` and `lambda:InvokeFunction` can be
        # granted at the right scope.
        CfnOutput(
            self,
            "PdfRenderLambdaArn",
            value=self._function.function_arn,
            description="ARN of the PDF render Lambda — read by the API Lambda",
        )

    # ── Public surface ────────────────────────────────────────────────

    @property
    def function(self) -> lambda_.Function:
        """The PDF render Lambda. Used by the API Lambda for invoke grants."""
        return self._function

    @property
    def token_secret(self) -> secretsmanager.Secret:
        """The HMAC signing secret. Granted-read to the API Lambda + this Lambda."""
        return self._token_secret

    @property
    def internal_api_key(self) -> secretsmanager.Secret:
        """The shared secret for the Next.js print page → backend internal endpoint.

        Consumed by `internal_handlers.handle_internal_get_analysis` (Python)
        and the `/print/[analysisId]/page.tsx` server component (TypeScript).
        Both MUST read it from `INTERNAL_API_KEY`.
        """
        return self._internal_api_key

    def grant_invoke(self, grantee: iam.IGrantable) -> iam.Grant:
        """Allow `grantee` (typically the API Lambda) to invoke the PDF Lambda."""
        return self._function.grant_invoke(grantee)

    # ── Internals ─────────────────────────────────────────────────────

    def _build_token_secret(self) -> secretsmanager.Secret:
        """Create the per-environment HMAC signing secret in Secrets Manager.

        CDK generates a random 32-byte value at deploy time. Rotation is a
        CDK redeploy with a new logical ID (or a manual override via the
        Secrets Manager console — see `docs/runbooks/pdf-token-rotation.md`).
        """
        return secretsmanager.Secret(
            self,
            "PdfTokenSecret",
            secret_name=f"janus/{self._environment}/pdf-token-secret",
            description=(
                "HMAC-SHA256 key for signing short-lived URL tokens that authorise "
                "the PDF render Lambda's headless browser navigation to /print/{id}."
            ),
            generate_secret_string=secretsmanager.SecretStringGenerator(
                # 32-byte alphanumeric secret. The token-signing module
                # treats the value as opaque bytes.
                password_length=64,
                exclude_punctuation=True,
            ),
        )

    def _build_internal_api_key(self) -> secretsmanager.Secret:
        """Per-environment shared secret for the Next.js → backend internal path.

        Used by the `/print/{id}` server component when fetching analysis
        data (the headless browser has no NextAuth session, so we can't
        forward a Cognito JWT). Stored in Secrets Manager + injected as
        `INTERNAL_API_KEY` on both Lambdas. Constant-time-compared in
        `internal_handlers.handle_internal_get_analysis`.
        """
        return secretsmanager.Secret(
            self,
            "InternalApiKey",
            secret_name=f"janus/{self._environment}/internal-api-key",
            description=(
                "Shared secret authorising the Next.js print route's "
                "headless-browser-data-fetch path to call /api/internal/analysis."
            ),
            generate_secret_string=secretsmanager.SecretStringGenerator(
                password_length=64,
                exclude_punctuation=True,
            ),
        )

    def _build_function(self) -> lambda_.Function:
        log_retention = self._resolve_log_retention()

        log_group = logs.LogGroup(
            self,
            "PdfRenderLogs",
            log_group_name=f"/aws/lambda/janus-pdf-render-{self._environment}",
            retention=log_retention,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        # `@sparticuz/chromium` ships as an npm package containing the
        # Chromium binary (~50MB). We bundle it directly into the Lambda
        # code asset instead of using a separate layer — at this size the
        # function package is well inside the 250MB unzipped limit, and
        # avoiding a layer simplifies the deploy story (no layer-version-
        # vs-handler-version drift, no separate asset path to provision).
        function = lambda_.Function(
            self,
            "PdfRenderFunction",
            function_name=f"janus-pdf-render-{self._environment}",
            runtime=lambda_.Runtime.NODEJS_20_X,
            architecture=lambda_.Architecture.X86_64,
            handler="dist/handler.handler",
            code=lambda_.Code.from_asset(
                "../backend/lambdas/pdf-render",
                bundling=cdk.BundlingOptions(
                    image=lambda_.Runtime.NODEJS_20_X.bundling_image,
                    # Run as root inside the bundling container — without
                    # this, CDK passes `-u 1001:1001` (the GitHub Actions
                    # runner UID) and `npm ci` fails to write node_modules
                    # into the mounted source dir (owned by root from the
                    # runner's perspective). Container exits in ~14ms with
                    # status 243. Matches the pattern in `lambda_factory.
                    # build_bundling_options` for the Python Lambda.
                    user="root",
                    command=[
                        "bash",
                        "-c",
                        " && ".join([
                            "npm ci --silent",
                            "npm run build --silent",
                            "npm prune --omit=dev --silent",
                            "cp -r dist node_modules /asset-output/",
                        ]),
                    ],
                ),
            ),
            timeout=Duration.seconds(TIMEOUT_SECONDS),
            memory_size=MEMORY_MB,
            reserved_concurrent_executions=RESERVED_CONCURRENCY,
            log_group=log_group,
            environment={
                # Pass the ARN, NOT the cleartext value. The Lambda fetches
                # the secret at runtime via `secretsmanager:GetSecretValue`
                # (cached at module level). Avoids exposing the signing
                # key via `lambda:GetFunctionConfiguration`.
                "PDF_TOKEN_SECRET_ARN": self._token_secret.secret_arn,
                "STAGE": self._environment,
            },
            tracing=(
                lambda_.Tracing.ACTIVE
                if self._config.get("enable_monitoring")
                else lambda_.Tracing.DISABLED
            ),
        )

        # The Lambda fetches the signing secret via Secrets Manager at
        # runtime (env carries the ARN, not the cleartext). Grant read
        # access on the specific secret only.
        self._token_secret.grant_read(function)
        return function

    def _build_metrics(self, log_group: logs.ILogGroup) -> None:
        """Extract `durationMs`, `pageCount`, `pdfSizeBytes` from the Lambda's
        structured JSON log lines and publish them as CloudWatch metrics.

        The handler emits one log line per render of the form
        `{"event":"pdf_render","status":"ok","durationMs":1234,"pageCount":5,
         "pdfSizeBytes":67890,...}`. The metric filter pattern matches only
        successful renders so failures don't pollute capacity numbers.
        """
        metric_namespace = f"Janus/{self._environment.capitalize()}/PdfRender"

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
                self,
                f"{metric_name}Filter",
                log_group=log_group,
                metric_namespace=metric_namespace,
                metric_name=metric_name,
                filter_pattern=ok_pattern,
                metric_value=json_path,
            )

        # Failure counters. The handler emits `status: 'error'` for
        # render crashes / misconfiguration AND `status: 'reject'` for
        # parse failures + invalid tokens. Both are real operational
        # signals worth alerting on independently — an `error` is a
        # server-side failure that needs ops attention; sustained
        # `reject` events suggest a token-expiry bug or abuse traffic.
        # Two separate metrics so alarm thresholds can target the right
        # severity (errors: page on any; rejects: alert on rate).
        for failure_status, metric_name in (
            ("error", "RenderErrorCount"),
            ("reject", "RenderRejectCount"),
        ):
            logs.MetricFilter(
                self,
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

        # Dashboard widget — only created in monitored environments.
        if not self._config.get("enable_monitoring"):
            return

        cloudwatch.Dashboard(
            self,
            "PdfRenderDashboard",
            dashboard_name=f"janus-pdf-render-{self._environment}",
            widgets=[[
                cloudwatch.GraphWidget(
                    title="Render duration (ms)",
                    left=[cloudwatch.Metric(
                        namespace=metric_namespace,
                        metric_name="RenderDurationMs",
                        statistic="p95",
                        period=Duration.minutes(5),
                    )],
                    width=12,
                ),
                cloudwatch.GraphWidget(
                    title="PDF size (bytes)",
                    left=[cloudwatch.Metric(
                        namespace=metric_namespace,
                        metric_name="RenderPdfSizeBytes",
                        statistic="Average",
                        period=Duration.minutes(5),
                    )],
                    width=12,
                ),
            ], [
                cloudwatch.GraphWidget(
                    title="Pages per render",
                    left=[cloudwatch.Metric(
                        namespace=metric_namespace,
                        metric_name="RenderPageCount",
                        statistic="Average",
                        period=Duration.minutes(5),
                    )],
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
            ]],
        )

    def _resolve_log_retention(self) -> logs.RetentionDays:
        # Match `lambda_factory`'s strict contract: every environment
        # config MUST declare `log_retention_days`. A missing key is a
        # config-shape bug, not something we should silently paper over.
        days = self._config["log_retention_days"]
        retention_map = {
            7: logs.RetentionDays.ONE_WEEK,
            30: logs.RetentionDays.ONE_MONTH,
            90: logs.RetentionDays.THREE_MONTHS,
        }
        if days not in retention_map:
            message = (
                f"Unsupported log_retention_days={days}; "
                "supported values are 7, 30, 90."
            )
            raise ValueError(message)
        return retention_map[days]
