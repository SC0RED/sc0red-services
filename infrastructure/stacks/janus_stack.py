"""Janus CDK stack — DynamoDB, SQS, Lambda (API + Worker), API Gateway, Cognito."""

import os
from typing import Any

from aws_cdk import CfnOutput, Stack
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
        frontend_domain = amplify.branch_url if amplify else os.environ.get("FRONTEND_DOMAIN", "")

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
            frontend_domain=frontend_domain,
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
        worker_handler = create_lambda(
            self,
            "WorkerHandler",
            function_name=f"janus-worker-{environment}",
            handler="src.handlers.worker_handler_entry.handle_worker_event",
            bundling=bundling,
            environment=common_environment,
            timeout_seconds=540,
            memory_size=1769,
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
            frontend_domain=frontend_domain,
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
            frontend_base_url=frontend_domain,
        )
        pdf_render.grant_invoke(api_handler)
        pdf_render.token_secret.grant_read(api_handler)
        api_handler.add_environment(
            "PDF_RENDER_LAMBDA_ARN", pdf_render.function.function_arn
        )
        api_handler.add_environment(
            "PDF_TOKEN_SECRET", pdf_render.token_secret.secret_value.to_string()
        )

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
