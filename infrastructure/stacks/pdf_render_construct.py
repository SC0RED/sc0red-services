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

# Pin to the same Chromium version as in `package.json`. Layer ARN
# pattern is the canonical `@sparticuz/chromium-aws-lambda` distribution
# for the matching version. Update both together when bumping.
CHROMIUM_LAYER_VERSION = "121.0.0"


class PdfRenderConstruct(Construct):
    """PDF render Lambda + supporting resources (secret, layer, IAM)."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        environment: str,
        config: dict[str, Any],
        frontend_base_url: str,
    ) -> None:
        super().__init__(scope, construct_id)
        self._environment = environment
        self._config = config

        self._token_secret = self._build_token_secret()
        self._chromium_layer = self._build_chromium_layer()
        self._function = self._build_function(frontend_base_url)

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

    def _build_chromium_layer(self) -> lambda_.LayerVersion:
        """Attach the `@sparticuz/chromium` Lambda layer.

        We bundle the layer's tarball alongside the Lambda code in the
        `backend/lambdas/pdf-render/layers/chromium/` directory at deploy
        time; the local-dev / CI flow downloads the matching tarball with
        the wrapper script. See `backend/lambdas/pdf-render/README.md`.

        For now the construct points at a placeholder path — apply-time
        wiring will replace it with an actual asset path or a published
        layer ARN once we decide on the distribution pattern.
        """
        return lambda_.LayerVersion(
            self,
            "ChromiumLayer",
            code=lambda_.Code.from_asset(
                "../backend/lambdas/pdf-render/layers/chromium",
            ),
            compatible_runtimes=[lambda_.Runtime.NODEJS_20_X],
            compatible_architectures=[lambda_.Architecture.X86_64],
            description=(
                f"@sparticuz/chromium {CHROMIUM_LAYER_VERSION} — headless Chromium for the PDF render Lambda."
            ),
        )

    def _build_function(self, frontend_base_url: str) -> lambda_.Function:
        log_retention = self._resolve_log_retention()

        log_group = logs.LogGroup(
            self,
            "PdfRenderLogs",
            log_group_name=f"/aws/lambda/janus-pdf-render-{self._environment}",
            retention=log_retention,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

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
                    command=[
                        "bash",
                        "-c",
                        " && ".join([
                            "npm ci --omit=dev --silent",
                            "npm run build --silent",
                            "cp -r dist node_modules /asset-output/",
                        ]),
                    ],
                ),
            ),
            layers=[self._chromium_layer],
            timeout=Duration.seconds(TIMEOUT_SECONDS),
            memory_size=MEMORY_MB,
            reserved_concurrent_executions=RESERVED_CONCURRENCY,
            log_group=log_group,
            environment={
                "PDF_TOKEN_SECRET": self._token_secret.secret_value.to_string(),
                "FRONTEND_BASE_URL": frontend_base_url,
                "STAGE": self._environment,
            },
            tracing=(
                lambda_.Tracing.ACTIVE
                if self._config.get("enable_monitoring")
                else lambda_.Tracing.DISABLED
            ),
        )

        # The Lambda reads its signing secret from the environment, so it
        # needs the GetSecretValue permission for the rotation case
        # (after a Secrets Manager rotation, env vars can be re-resolved).
        self._token_secret.grant_read(function)
        return function

    def _resolve_log_retention(self) -> logs.RetentionDays:
        days = self._config.get("log_retention_days", 7)
        return {
            7: logs.RetentionDays.ONE_WEEK,
            30: logs.RetentionDays.ONE_MONTH,
            90: logs.RetentionDays.THREE_MONTHS,
        }.get(days, logs.RetentionDays.ONE_WEEK)
