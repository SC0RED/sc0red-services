"""Janus CDK stack — DynamoDB, SQS, Lambda (API + Worker), API Gateway, Cognito."""

import os
from typing import Any

import aws_cdk as cdk
from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as lambda_event_sources
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sqs as sqs
from constructs import Construct

from stacks.amplify_construct import AmplifyConstruct
from stacks.cognito_construct import CognitoConstruct
from stacks.observability_construct import ObservabilityConstruct

_LOG_RETENTION_MAP: dict[int, logs.RetentionDays] = {
    7: logs.RetentionDays.ONE_WEEK,
    30: logs.RetentionDays.ONE_MONTH,
    90: logs.RetentionDays.THREE_MONTHS,
}


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
        self._lambda_architecture = (
            lambda_.Architecture.ARM_64 if arch_value == "arm64" else lambda_.Architecture.X86_64
        )

        # Phase 1: Create Amplify app early to get default_domain for CORS
        amplify = self._create_amplify_app()
        frontend_domain = self._resolve_frontend_domain(amplify)

        table = self._create_table()
        queue, dlq = self._create_queues()
        documents_bucket = self._create_documents_bucket(frontend_domain)

        bundling = self._build_bundling_options()

        cognito = self._create_cognito(bundling, frontend_domain)

        common_environment = self._build_common_environment(
            table, queue, documents_bucket, cognito
        )

        api_handler = self._create_lambda(
            "ApiHandler",
            function_name=f"janus-api-{environment}",
            handler="src.handlers.api_handler_entry.handle_api_event",
            bundling=bundling, environment=common_environment,
            timeout_seconds=30, memory_size=512,
        )
        worker_handler = self._create_lambda(
            "WorkerHandler",
            function_name=f"janus-worker-{environment}",
            handler="src.handlers.worker_handler_entry.handle_worker_event",
            bundling=bundling, environment=common_environment,
            timeout_seconds=540, memory_size=1769, reserved_concurrency=5,
        )

        table.grant_read_write_data(api_handler)
        queue.grant_send_messages(api_handler)
        table.grant_read_write_data(worker_handler)
        queue.grant_consume_messages(worker_handler)
        documents_bucket.grant_read_write(api_handler)
        cognito.grant_admin_actions(api_handler)

        api = self._create_api(api_handler, frontend_domain)

        # Phase 2: Create Amplify branch now that API URL exists
        if amplify:
            amplify.create_branch(
                api_url=api.url,
                cognito_user_pool_id=cognito.user_pool_id,
                cognito_client_id=cognito.app_client_id,
            )

        worker_handler.add_event_source(
            lambda_event_sources.SqsEventSource(queue, batch_size=1)
        )

        observability = ObservabilityConstruct(
            self, "Observability",
            environment=environment, config=config, dlq=dlq,
        )
        worker_handler.add_environment("APPSYNC_ENDPOINT", observability.appsync_url)
        worker_handler.add_environment("APPSYNC_API_KEY", observability.appsync_api_key)
        api_handler.add_environment("APPSYNC_ENDPOINT", observability.appsync_url)
        api_handler.add_environment("APPSYNC_API_KEY", observability.appsync_api_key)

        CfnOutput(self, "ApiUrl", value=api.url, description=f"API Gateway URL — {environment}")
        CfnOutput(self, "TableName", value=table.table_name)
        CfnOutput(self, "QueueUrl", value=queue.queue_url)
        CfnOutput(self, "DlqUrl", value=dlq.queue_url)
        CfnOutput(self, "BucketName", value=documents_bucket.bucket_name)
        CfnOutput(self, "ApiLambdaName", value=api_handler.function_name)
        CfnOutput(self, "WorkerLambdaName", value=worker_handler.function_name)

    # ── Amplify ─────────────────────────────────────────────────────────────────

    def _create_amplify_app(self) -> AmplifyConstruct | None:
        """Phase 1: create the Amplify app (if enabled) for the default domain."""
        if not self._config.get("enable_amplify"):
            return None

        nextauth_secret = os.environ.get("NEXTAUTH_SECRET", "")
        github_token = os.environ.get("AMPLIFY_GITHUB_TOKEN", "")

        if not github_token:
            message = "AMPLIFY_GITHUB_TOKEN must be set when enable_amplify is True"
            raise ValueError(message)

        return AmplifyConstruct(
            self,
            "Amplify",
            environment=self._environment,
            nextauth_secret=nextauth_secret,
            github_token=github_token,
            repository=self._config["github_repository"],
            branch_name=self._config["amplify_branch"],
        )

    def _resolve_frontend_domain(self, amplify: AmplifyConstruct | None) -> str:
        """Resolve the frontend domain from Amplify or FRONTEND_DOMAIN env var."""
        if amplify:
            return amplify.branch_url
        return os.environ.get("FRONTEND_DOMAIN", "")

    # ── DynamoDB ──────────────────────────────────────────────────────────────

    def _create_table(self) -> dynamodb.Table:
        table = dynamodb.Table(
            self,
            "JanusTable",
            table_name=f"janus-{self._environment}",
            partition_key=dynamodb.Attribute(name="pk", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="sk", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=self._config["removal_policy"],
            point_in_time_recovery=bool(self._config.get("point_in_time_recovery", False)),
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
        )

        for i in range(1, 5):
            table.add_global_secondary_index(
                index_name=f"GSI{i}",
                partition_key=dynamodb.Attribute(
                    name=f"GSI{i}PK", type=dynamodb.AttributeType.STRING
                ),
                sort_key=dynamodb.Attribute(
                    name=f"GSI{i}SK", type=dynamodb.AttributeType.STRING
                ),
                projection_type=dynamodb.ProjectionType.ALL,
            )

        return table

    # ── SQS ───────────────────────────────────────────────────────────────────

    def _create_queues(self) -> tuple[sqs.Queue, sqs.Queue]:
        dlq = sqs.Queue(
            self,
            "AnalysisDLQ",
            queue_name=f"janus-analysis-dlq-{self._environment}",
            retention_period=Duration.days(14),
        )
        queue = sqs.Queue(
            self,
            "AnalysisQueue",
            queue_name=f"janus-analysis-queue-{self._environment}",
            visibility_timeout=Duration.seconds(600),
            retention_period=Duration.days(1),
            dead_letter_queue=sqs.DeadLetterQueue(queue=dlq, max_receive_count=3),
        )
        return queue, dlq

    # ── S3 ───────────────────────────────────────────────────────────────────

    def _create_documents_bucket(self, frontend_domain: str) -> s3.Bucket:

        bucket = s3.Bucket(
            self,
            "DocumentsBucket",
            bucket_name=f"janus-documents-{self._environment}",
            removal_policy=self._config["removal_policy"],
            auto_delete_objects=self._environment == "development",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            lifecycle_rules=[s3.LifecycleRule(expiration=Duration.days(90))],
            cors=[
                s3.CorsRule(
                    allowed_methods=[s3.HttpMethods.PUT],
                    allowed_origins=[frontend_domain] if frontend_domain else ["*"],
                    allowed_headers=["*"],
                    max_age=300,
                )
            ],
        )
        return bucket

    # ── Cognito ─────────────────────────────────────────────────────────────────

    def _create_cognito(
        self,
        bundling: cdk.BundlingOptions,
        frontend_domain: str,
    ) -> CognitoConstruct:
        """Create the Cognito User Pool, App Client, and Custom Message Lambda."""
        return CognitoConstruct(
            self,
            "Cognito",
            environment=self._environment,
            removal_policy=self._config["removal_policy"],
            bundling=bundling,
            lambda_architecture=self._lambda_architecture,
            frontend_domain=frontend_domain,
        )

    # ── Shared helpers ─────────────────────────────────────────────────────────

    def _build_bundling_options(self) -> cdk.BundlingOptions:
        """Build the Docker bundling config shared by both Lambdas."""
        deploy_key_b64 = os.environ.get("DEPLOY_KEY_B64", "")

        return cdk.BundlingOptions(
            image=cdk.DockerImage.from_registry("python:3.12-slim"),
            user="root",
            environment={"DEPLOY_KEY_B64": deploy_key_b64},
            command=[
                "bash",
                "-c",
                " && ".join([
                    "apt-get update -qq && apt-get install -y -qq git openssh-client",
                    (
                        'if [ -n "$DEPLOY_KEY_B64" ]; then'
                        " mkdir -p ~/.ssh"
                        ' && echo "$DEPLOY_KEY_B64" | base64 -d | tr -d "\\r" > ~/.ssh/id_rsa'
                        " && echo >> ~/.ssh/id_rsa"
                        " && chmod 600 ~/.ssh/id_rsa"
                        " && ssh-keyscan -H github.com >> ~/.ssh/known_hosts 2>/dev/null"
                        ' && git config --global url."git@github.com:".insteadOf "https://github.com/";'
                        " fi"
                    ),
                    "pip install --no-cache-dir . -t /asset-output -q",
                ]),
            ],
        )

    def _build_common_environment(
        self,
        table: dynamodb.Table,
        queue: sqs.Queue,
        documents_bucket: s3.Bucket,
        cognito_construct: CognitoConstruct,
    ) -> dict[str, str]:
        """Build the environment variables shared by both Lambdas."""
        nextauth_secret = os.environ.get("NEXTAUTH_SECRET", "")
        if not nextauth_secret:
            if self._environment == "development":
                nextauth_secret = "dev-secret-minimum-32-characters-long"
            else:
                message = (
                    f"NEXTAUTH_SECRET must be set for environment '{self._environment}'. "
                    "A deployment with a default dev secret is a security risk."
                )
                raise ValueError(message)

        region = self.region or os.environ.get("AWS_REGION", "us-east-1")

        return {
            "DYNAMODB_TABLE": table.table_name,
            "ANALYSIS_QUEUE_URL": queue.queue_url,
            "DOCUMENTS_BUCKET": documents_bucket.bucket_name,
            "STAGE": self._environment,
            "NEXTAUTH_SECRET": nextauth_secret,
            "COGNITO_USER_POOL_ID": cognito_construct.user_pool_id,
            "COGNITO_CLIENT_ID": cognito_construct.app_client_id,
            "COGNITO_REGION": region,
            "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", "sk-placeholder"),
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
            "AI_PROVIDER": os.environ.get("AI_PROVIDER", "anthropic"),
        }

    # ── Lambdas ──────────────────────────────────────────────────────────────

    def _create_lambda(
        self,
        construct_id: str,
        *,
        function_name: str,
        handler: str,
        bundling: cdk.BundlingOptions,
        environment: dict[str, str],
        timeout_seconds: int,
        memory_size: int,
        reserved_concurrency: int | None = None,
    ) -> lambda_.Function:
        """Create a Lambda function with log group and tracing."""
        log_group = logs.LogGroup(
            self,
            f"{construct_id}Logs",
            log_group_name=f"/aws/lambda/{function_name}",
            retention=_LOG_RETENTION_MAP.get(
                self._config.get("log_retention_days", 7), logs.RetentionDays.ONE_WEEK
            ),
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        return lambda_.Function(
            self,
            construct_id,
            function_name=function_name,
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=self._lambda_architecture,
            handler=handler,
            code=lambda_.Code.from_asset("../backend", bundling=bundling),
            timeout=Duration.seconds(timeout_seconds),
            memory_size=memory_size,
            reserved_concurrent_executions=reserved_concurrency,
            log_group=log_group,
            environment=environment,
            tracing=(
                lambda_.Tracing.ACTIVE
                if self._config.get("enable_monitoring")
                else lambda_.Tracing.DISABLED
            ),
        )

    # ── API Gateway ───────────────────────────────────────────────────────────

    def _create_api(self, handler: lambda_.Function, frontend_domain: str) -> apigw.LambdaRestApi:

        if frontend_domain:
            cors_origins = [frontend_domain]
        elif self._environment == "development":
            cors_origins = apigw.Cors.ALL_ORIGINS
        else:
            message = (
                f"FRONTEND_DOMAIN must be set for environment '{self._environment}'. "
                "Example: https://janus.vercel.app"
            )
            raise ValueError(message)

        api = apigw.LambdaRestApi(
            self,
            "ApiEndpoint",
            handler=handler,
            rest_api_name=f"janus-api-{self._environment}",
            description=f"Janus PE Risk Assessment API — {self._environment}",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=cors_origins,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"],
            ),
            deploy_options=apigw.StageOptions(
                stage_name=self._environment,
                throttling_rate_limit=self._config["api_rate_limit"],
                throttling_burst_limit=self._config["api_burst_limit"],
                logging_level=(
                    apigw.MethodLoggingLevel.INFO
                    if self._config.get("enable_monitoring")
                    else apigw.MethodLoggingLevel.OFF
                ),
                metrics_enabled=bool(self._config.get("enable_monitoring")),
                tracing_enabled=bool(self._config.get("enable_monitoring")),
            ),
        )

        return api

