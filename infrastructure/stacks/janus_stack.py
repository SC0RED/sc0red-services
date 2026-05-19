"""Janus CDK stack — DynamoDB, SQS, Lambda (API + Worker), API Gateway, Cognito."""

import os
from typing import Any

from aws_cdk import Annotations, CfnOutput, Stack
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as lambda_event_sources
from constructs import Construct

from stacks.amplify_construct import AmplifyConstruct
from stacks.cognito_construct import CognitoConstruct
from stacks.lambda_factory import (
    build_bundling_options,
    build_common_environment,
    create_lambda,
)
from stacks.mcp_construct import MCPConstruct
from stacks.observability_construct import ObservabilityConstruct
from stacks.pdf_render_construct import PdfRenderConstruct
from stacks.stack_resources import (
    create_analytics_log_group,
    create_api,
    create_documents_bucket,
    create_queues,
    create_table,
)
from stacks.step_functions_construct import StepFunctionsConstruct


class JanusStack(Stack):
    """Main stack: DynamoDB table, SQS queue, API + Worker Lambdas, API Gateway."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment: str,
        config: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Initialize the Janus stack."""
        super().__init__(scope, construct_id, **kwargs)

        self._environment = environment
        self._config = config

        arch_value = config.get("lambda_architecture", "x86_64")
        lambda_architecture = (
            lambda_.Architecture.ARM_64 if arch_value == "arm64" else lambda_.Architecture.X86_64
        )

        # Phase 1: Create Amplify app to get domain for CORS
        amplify = self._create_amplify()
        amplify_default_url = amplify.branch_url if amplify else ""

        # Phase 2 host cutover (rename-janus-to-sc0red-advisory):
        # ``canonical_frontend_domain`` is the URL the app SHOULD canonicalize
        # on — the sc0red Advisory custom domain in non-development environments
        # once attached in the Amplify Console. It drives NEXTAUTH_URL,
        # FRONTEND_BASE_URL (the print Lambda's navigation target),
        # CONSENT_BASE_URL (MCP), and the invitation-email FRONTEND_DOMAIN.
        # When no custom domain is configured (development, or non-Amplify
        # CDK synth), we fall back to the Amplify branch URL, and lastly to
        # the FRONTEND_DOMAIN env var for purely local synth.
        configured_custom_domain = config.get("frontend_custom_domain") or None
        configured_legacy_domain = config.get("frontend_legacy_domain") or None
        canonical_frontend_domain = (
            configured_custom_domain
            or amplify_default_url
            or os.environ.get("FRONTEND_DOMAIN", "")
        )
        # ``allowed_origins`` is the full list of hostnames CORS must accept.
        # During the 90-day cutover (proposal §10), CORS allows BOTH the new
        # sc0red Advisory host and the legacy ``*.janus.sc0red.com`` host so
        # users hitting the old bookmark still receive a working app. After
        # decommission, set ``frontend_legacy_domain`` to None in
        # ``infrastructure/app.py`` to drop the legacy origin from the list.
        # The Amplify default URL is always included so internal smoke tests
        # and the headless Chromium PDF Lambda (which navigates the SSR
        # Lambda's stable Amplify URL, not the public custom domain) can
        # still make same-origin XHRs through the SSR proxy routes.
        allowed_origins: list[str] = []
        for origin in (canonical_frontend_domain, configured_legacy_domain, amplify_default_url):
            if origin and origin not in allowed_origins:
                allowed_origins.append(origin)

        # Backwards-compat alias kept for existing call sites that take a
        # single ``frontend_domain`` string for user-visible URLs (the
        # Cognito CustomMessage invitation email's accept-invite link, the
        # MCP OAuth CONSENT_BASE_URL the user sees during MCP authorisation).
        # Internal navigation targets like the PDF Lambda's
        # ``FRONTEND_BASE_URL`` use ``amplify_default_url`` instead (set
        # explicitly below) so they don't depend on the user-visible
        # domain's lifecycle.
        frontend_domain = canonical_frontend_domain

        # Phase 2 sequencing guard (rename-janus-to-sc0red-advisory):
        # ``frontend_custom_domain`` becomes the public NEXTAUTH_URL the
        # moment this stack synthesises, which means the Amplify build
        # picks it up on its next build trigger after this CDK deploy.
        # The matching Amplify Console custom-domain attachment + Route 53
        # records are out-of-band ops (this stack does not manage the
        # ``sc0red.com`` hosted zone). Surface that sequencing constraint
        # in the deploy log so an operator running ``cdk deploy`` without
        # the matching console work sees the warning rather than chasing
        # a confusing post-deploy auth failure.
        if configured_custom_domain:
            Annotations.of(self).add_info(
                f"Phase 2 host cutover: ``NEXTAUTH_URL`` will be set to "
                f"``{configured_custom_domain}`` for the ``{environment}`` "
                "Amplify branch. Verify the matching Amplify Console "
                "custom-domain attachment, DNS records, and (if cutting "
                "over) the 301-redirect on the legacy ``janus.sc0red.com`` "
                "host are in place BEFORE Amplify rebuilds against this "
                "stack — otherwise auth flow on the new host will fail "
                "until the domain attachment completes."
            )

        table = create_table(
            self,
            environment=environment,
            removal_policy=config["removal_policy"],
            point_in_time_recovery=bool(config.get("point_in_time_recovery", False)),
        )
        queue, dlq = create_queues(self, environment=environment)
        documents_bucket = create_documents_bucket(
            self,
            environment=environment,
            removal_policy=config["removal_policy"],
            allowed_origins=allowed_origins,
        )
        analytics_log_group = create_analytics_log_group(
            self,
            environment=environment,
            removal_policy=config["removal_policy"],
        )

        bundling = build_bundling_options()

        cognito = CognitoConstruct(
            self,
            "Cognito",
            environment=environment,
            removal_policy=config["removal_policy"],
            bundling=bundling,
            lambda_architecture=lambda_architecture,
            frontend_domain=frontend_domain,
        )

        common_environment = build_common_environment(
            self,
            environment=environment,
            table=table,
            queue=queue,
            documents_bucket=documents_bucket,
            cognito_construct=cognito,
        )

        log_retention_days = config.get("log_retention_days", 7)
        enable_tracing = bool(config.get("enable_monitoring"))

        api_handler = create_lambda(
            self,
            "ApiHandler",
            function_name=f"janus-api-{environment}",
            handler="src.handlers.api_handler_entry.handle_api_event",
            bundling=bundling,
            environment=common_environment,
            timeout_seconds=30,
            memory_size=512,
            architecture=lambda_architecture,
            log_retention_days=log_retention_days,
            enable_tracing=enable_tracing,
        )
        worker_concurrency = config.get("worker_concurrency", 4)
        # Lambda envelope bumped (was 540 s / 1769 MB) so the inlined
        # strategy-map step (``redesign-strategy-map`` Phase 4) has
        # headroom for OpenAI tail-latency retries on top of the base
        # ~30 s analysis. The 900 s timeout is the Lambda max; 2048 MB
        # gives ~1.16 vCPU (above the 1769 MB tier where AWS allocates
        # >1 vCPU) so Pydantic validation + prompt rendering across the
        # decomposed strategy-map chain don't bottleneck on CPU.
        # The analysis-queue ``visibility_timeout`` (in
        # ``stack_resources.create_queues``) MUST be >= this Lambda
        # timeout per the AWS SQS-Lambda event-source-mapping contract;
        # the queue is configured at 1080 s for the same ~20 % buffer.
        worker_handler = create_lambda(
            self,
            "WorkerHandler",
            function_name=f"janus-worker-{environment}",
            handler="src.handlers.worker_handler_entry.handle_worker_event",
            bundling=bundling,
            environment=common_environment,
            timeout_seconds=900,
            memory_size=2048,
            architecture=lambda_architecture,
            log_retention_days=log_retention_days,
            enable_tracing=enable_tracing,
            reserved_concurrency=worker_concurrency,
        )

        table.grant_read_write_data(api_handler)
        queue.grant_send_messages(api_handler)
        table.grant_read_write_data(worker_handler)
        queue.grant_consume_messages(worker_handler)
        documents_bucket.grant_read_write(api_handler)
        cognito.grant_admin_actions(api_handler)
        analytics_log_group.grant_write(api_handler)
        api_handler.add_environment("ANALYTICS_LOG_GROUP", analytics_log_group.log_group_name)

        api = create_api(
            self,
            environment=environment,
            config=config,
            handler=api_handler,
            allowed_origins=allowed_origins,
        )

        # PDF render Lambda — Node.js + headless Chromium. The API Lambda
        # invokes it via boto3 from `handle_render_pdf` to produce the
        # binary PDF that backs the Export PDF button. Construct also
        # provisions the per-environment HMAC secret used by the URL
        # tokens that authorise navigation to /print/{analysisId}.
        pdf_render = PdfRenderConstruct(
            self,
            "PdfRender",
            environment=environment,
            config=config,
            # The Lambda's async mode performs conditional UpdateItem on
            # the assessment record's PDF_EXPORT sub-row. Construct grants
            # `dynamodb:UpdateItem` on this table + passes its name as
            # `ASSESSMENT_TABLE` env to the Lambda.
            assessment_table=table,
        )
        pdf_render.grant_invoke(api_handler)
        pdf_render.token_secret.grant_read(api_handler)
        pdf_render.internal_api_key.grant_read(api_handler)
        # API Lambda mints 60-second presigned download URLs against the
        # exports bucket from `handle_post_export` when a cached PDF is
        # found. Read-only grant is sufficient — only the PDF Lambda
        # writes (via the bucket's grant_put in PdfRenderConstruct).
        pdf_render.exports_bucket.grant_read(api_handler)
        api_handler.add_environment(
            "PDF_EXPORTS_BUCKET", pdf_render.exports_bucket.bucket_name
        )
        # The async POST handler signs a fresh URL token + passes the
        # frontend base URL to the PDF Lambda so its headless browser
        # can navigate ``<frontend_base_url>/print/<id>?t=<token>``.
        # MUST be the Amplify default URL (not the sc0red Advisory custom
        # domain): the PDF Lambda navigates from inside AWS and the
        # Amplify default URL is the most stable target — it resolves
        # immediately on stack creation, doesn't depend on the user-side
        # AWS Console domain attachment, and stays valid after a legacy
        # host is decommissioned. Amplify routes the canonical custom
        # domain through the same SSR Lambda, so the headless browser
        # would see identical content either way; we pin to the
        # Amplify default for lifecycle independence. Empty string
        # outside Amplify-managed environments is fine — the handler
        # fails fast at the env-var read.
        pdf_navigation_url = amplify_default_url or frontend_domain
        api_handler.add_environment("FRONTEND_BASE_URL", pdf_navigation_url)
        api_handler.add_environment(
            "PDF_TOKEN_SECRET_ARN", pdf_render.token_secret.secret_arn
        )
        # API Lambda gets the ARNs and resolves at runtime via Secrets
        # Manager (handlers cache the value module-level, so the round-
        # trip is one-per-cold-start). This keeps the cleartext out of
        # `lambda:GetFunctionConfiguration`'s reach.
        api_handler.add_environment(
            "PDF_RENDER_LAMBDA_ARN", pdf_render.function.function_arn
        )
        api_handler.add_environment(
            "INTERNAL_API_KEY_ARN", pdf_render.internal_api_key.secret_arn
        )
        # Amplify SSR Lambda STILL gets the cleartext — its IAM role is
        # auto-generated by Amplify and doesn't have Secrets Manager
        # access by default. Threading a custom compute role to add the
        # permission is its own scope, tracked as a follow-up.
        #
        # `unsafe_unwrap()` is required because CDK refuses to synthesize
        # a `SecretValue` into a plain CloudFormation property without
        # explicit acknowledgement that we accept the cleartext-exposure
        # risk. The trade-off is documented in the secret-rotation
        # runbook: anyone with Amplify console access can read these
        # values via the branch env-var UI. The Python + Node.js Lambdas
        # use the ARN + runtime resolution path instead, so the
        # `lambda:GetFunctionConfiguration` blast radius is closed.
        pdf_token_secret_value = pdf_render.token_secret.secret_value.unsafe_unwrap()
        internal_api_key_value = pdf_render.internal_api_key.secret_value.unsafe_unwrap()

        # Phase 2: Create Amplify branch now that API URL exists
        if amplify:
            nextauth_secret = os.environ.get("NEXTAUTH_SECRET", "")
            if not nextauth_secret and self._environment != "development":
                message = "NEXTAUTH_SECRET must be set for Amplify frontend"
                raise ValueError(message)
            amplify.create_branch(
                api_url=api.url,
                nextauth_secret=nextauth_secret,
                cognito_user_pool_id=cognito.user_pool_id,
                cognito_client_id=cognito.app_client_id,
                pdf_token_secret=pdf_token_secret_value,
                internal_api_key=internal_api_key_value,
                canonical_url=canonical_frontend_domain,
            )

        _mcp = MCPConstruct(
            self,
            "MCP",
            environment=environment,
            bundling=bundling,
            lambda_architecture=lambda_architecture,
            table=table,
            api_url=api.url,
            cognito_user_pool_id=cognito.user_pool_id,
            cognito_client_id=cognito.app_client_id,
            frontend_domain=frontend_domain,
        )

        worker_handler.add_event_source(
            lambda_event_sources.SqsEventSource(
                queue,
                batch_size=1,
                report_batch_item_failures=True,
            )
        )

        observability = ObservabilityConstruct(
            self, "Observability",
            environment=environment, config=config, dlq=dlq,
        )
        worker_handler.add_environment("APPSYNC_ENDPOINT", observability.appsync_url)
        worker_handler.add_environment("APPSYNC_API_KEY", observability.appsync_api_key)
        api_handler.add_environment("APPSYNC_ENDPOINT", observability.appsync_url)
        api_handler.add_environment("APPSYNC_API_KEY", observability.appsync_api_key)

        # ── Step Functions for portfolio batch coordination ──────────
        batch_coordinator = StepFunctionsConstruct(
            self,
            "BatchCoordinator",
            environment=environment,
            bundling=bundling,
            lambda_architecture=lambda_architecture,
            worker_lambda=worker_handler,
            table_name=table.table_name,
            appsync_endpoint=observability.appsync_url,
            appsync_api_key=observability.appsync_api_key,
        )
        batch_coordinator.grant_table_access(table)
        batch_coordinator.grant_start_execution(api_handler)

        # Auto-configure wave_size from worker concurrency — single source of truth
        api_handler.add_environment("PORTFOLIO_STATE_MACHINE_ARN", batch_coordinator.state_machine_arn)
        api_handler.add_environment("WAVE_SIZE", str(worker_concurrency))

        CfnOutput(self, "ApiUrl", value=api.url, description=f"API Gateway URL — {environment}")
        CfnOutput(self, "TableName", value=table.table_name)
        CfnOutput(self, "QueueUrl", value=queue.queue_url)
        CfnOutput(self, "DlqUrl", value=dlq.queue_url)
        CfnOutput(self, "BucketName", value=documents_bucket.bucket_name)
        CfnOutput(self, "ApiLambdaName", value=api_handler.function_name)
        CfnOutput(self, "WorkerLambdaName", value=worker_handler.function_name)
        CfnOutput(self, "AnalyticsLogGroup", value=analytics_log_group.log_group_name)

    # ── Amplify ─────────────────────────────────────────────────────────────────

    def _create_amplify(self) -> AmplifyConstruct | None:
        """Phase 1: create Amplify app (if configured) for the default domain."""
        amplify_branch = self._config.get("amplify_branch")
        if not amplify_branch:
            return None

        github_token = os.environ.get("AMPLIFY_GITHUB_TOKEN", "")
        if not github_token:
            message = "AMPLIFY_GITHUB_TOKEN must be set when amplify_branch is configured"
            raise ValueError(message)

        return AmplifyConstruct(
            self,
            "Amplify",
            environment=self._environment,
            github_token=github_token,
            repository=self._config["github_repository"],
            branch_name=amplify_branch,
        )
