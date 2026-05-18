"""PDF render Lambda — Node.js + headless Chromium.

Defines the `pdf-render` Lambda function (Node.js 20.x), the
`@sparticuz/chromium` layer it depends on, the Secrets Manager-backed
`PDF_TOKEN_SECRET` that signs URL tokens for the headless render flow,
the S3 exports bucket the Lambda writes to in async mode, and the DLQ
that catches async-invoke retry exhaustion.

The Lambda runs in two modes (see `handler.ts`):
- Sync (legacy, retired in Phase 4 of `async-pdf-export-with-cache`):
  invoked via API Gateway proxy, returns base64 PDF in the response.
- Async (new, primary): invoked via `InvocationType="Event"`, writes
  the bytes to S3 + conditionally transitions the assessment's
  `PDF_EXPORT` sub-row to `ready` / `failed`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import aws_cdk as cdk
from aws_cdk import CfnOutput, Duration
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_destinations as lambda_destinations
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import aws_sqs as sqs
from constructs import Construct

from stacks._pdf_render_metrics import build_pdf_render_metrics

if TYPE_CHECKING:
    from aws_cdk import aws_dynamodb as dynamodb

# Reserved concurrency cap. See design.md D7: a runaway loop (e.g., a
# user triple-clicking Export PDF) won't burn through the account-wide
# concurrency limit.
RESERVED_CONCURRENCY = 5

# Lambda timeout. Headroom over the in-Lambda render timeout (25s by
# default in render.ts) so the API Gateway integration doesn't cut us
# off mid-render.
TIMEOUT_SECONDS = 30

# Memory size — Chromium needs 1GB minimum to render reliably. Bumped
# from 1024MB to 2048MB on 2026-05-18 because 1024MB was producing
# 26-28s renders, putting the synchronous request chain (browser →
# Amplify SSR → backend API Gateway → Python proxy → PDF Lambda → S3
# → response stream) right against API Gateway's 29s hard ceiling.
# Result: intermittent 504s for the user even when the PDF rendered
# successfully (CloudWatch confirmed the bytes were generated, the
# delivery just couldn't complete in time).
#
# Lambda allocates vCPU proportional to memory: 1024MB ≈ 0.5 vCPU,
# 2048MB ≈ 1.0 vCPU. Chromium PDF rendering is CPU-bound, so doubling
# memory roughly halves render time (expected ~13s in production).
# Cost delta is small (renders are infrequent and only ~2x as
# expensive each) — well worth the headroom.
#
# This is a band-aid; the structural fix is to move PDF rendering off
# the synchronous request path entirely. See the
# ``async-pdf-export-with-cache`` OpenSpec change.
MEMORY_MB = 2048


class PdfRenderConstruct(Construct):
    """PDF render Lambda + supporting resources (secret, layer, IAM)."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        environment: str,
        config: dict[str, Any],
        assessment_table: dynamodb.ITable,
    ) -> None:
        super().__init__(scope, construct_id)
        self._environment = environment
        self._config = config

        self._token_secret = self._build_token_secret()
        self._internal_api_key = self._build_internal_api_key()
        self._exports_bucket = self._build_exports_bucket()
        self._async_dlq = self._build_async_dlq()
        self._function = self._build_function()

        # Async-mode permissions: S3 write (the bytes), DynamoDB
        # UpdateItem (the conditional ready/failed transition), and the
        # exports bucket name + table name in env so the Lambda can find
        # them. The conditional update is scoped by ConditionExpression
        # in handler code (guards on `started_at`); IAM here is at the
        # table grant — DynamoDB doesn't support attribute-level grants.
        self._exports_bucket.grant_put(self._function)
        assessment_table.grant(self._function, "dynamodb:UpdateItem")
        self._function.add_environment(
            "PDF_EXPORTS_BUCKET", self._exports_bucket.bucket_name
        )
        self._function.add_environment("ASSESSMENT_TABLE", assessment_table.table_name)

        # Async-invoke retry: the default budget is 2 retries over up to
        # 6 hours. For a user-driven PDF export, that's way too long —
        # the user will click again way before then. Bound to 5 minutes
        # so DLQ messages reflect actual exhaustion rather than ancient
        # retries. on_failure routes exhausted retries to the DLQ.
        lambda_.EventInvokeConfig(
            self,
            "PdfRenderAsyncConfig",
            function=self._function,
            max_event_age=Duration.minutes(5),
            on_failure=lambda_destinations.SqsDestination(self._async_dlq),
            retry_attempts=2,
        )
        self._build_dlq_alarm()

        build_pdf_render_metrics(
            self,
            log_group=self._function.log_group,
            environment=self._environment,
            config=self._config,
        )

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
    def exports_bucket(self) -> s3.Bucket:
        """The S3 bucket holding cached rendered PDFs (per-analysis key).

        The PDF Lambda has ``s3:PutObject`` on the bucket (granted in
        ``__init__``). The API Lambda needs ``s3:GetObject`` to mint
        the 60-second presigned download URLs — that grant is wired
        in ``janus_stack.py``, where both Lambdas live.
        """
        return self._exports_bucket

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

    def _build_exports_bucket(self) -> s3.Bucket:
        """Create the per-environment S3 bucket that caches rendered PDFs.

        One object per analysis (``pdf-exports/<analysisId>.pdf``);
        re-renders overwrite the same key. No lifecycle policy — storage
        cost is rounding error at expected volume. Block-all-public-access
        + bucket-owner-enforced ownership keeps the access model
        unambiguous: the PDF Lambda writes, the API Lambda reads via
        presigned URLs minted server-side. Browser clients never get a
        direct bucket grant.
        """
        return s3.Bucket(
            self,
            "PdfExportsBucket",
            bucket_name=f"janus-{self._environment}-pdf-exports",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_ENFORCED,
            removal_policy=self._config["removal_policy"],
            auto_delete_objects=self._environment == "development",
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

    def _build_async_dlq(self) -> sqs.Queue:
        """SQS DLQ that catches async-invoke failures after retry exhaustion.

        Lambda async-invoke (``InvocationType="Event"``) has its own
        built-in retry budget; this DLQ collects events that exceed it
        (e.g., persistent Chromium crashes, throttled DynamoDB writes).
        Operators consume the queue to backfill failures into the
        ``pdf_export.status = "failed"`` state for affected analyses.
        """
        return sqs.Queue(
            self,
            "PdfRenderAsyncDlq",
            queue_name=f"janus-pdf-render-async-dlq-{self._environment}",
            retention_period=Duration.days(14),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
        )

    def _build_dlq_alarm(self) -> None:
        """Alarm fires whenever the DLQ has any visible messages.

        Async-invoke exhaustion is rare and operationally important —
        ``threshold = 1`` over a 5-minute window means any DLQ activity
        pages someone. Gated on ``enable_monitoring`` to match the
        ``ObservabilityConstruct`` pattern (dev environments don't need
        paging surface; the alarm noise would dull the signal when it
        eventually wires to SNS in staging/production).
        """
        if not self._config.get("enable_monitoring"):
            return
        cloudwatch.Alarm(
            self,
            "PdfRenderAsyncDlqAlarm",
            alarm_name=f"janus-pdf-render-async-dlq-{self._environment}",
            alarm_description=(
                "PDF render Lambda async-invoke has DLQ messages — "
                "renders are failing after retry exhaustion."
            ),
            metric=self._async_dlq.metric_approximate_number_of_messages_visible(
                period=Duration.minutes(5),
                statistic="Maximum",
            ),
            threshold=1,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
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
