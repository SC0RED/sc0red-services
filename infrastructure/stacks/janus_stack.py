"""Janus CDK stack — DynamoDB, SQS, Lambda (API + Worker), API Gateway, Cognito."""

import os
from typing import Any

import aws_cdk as cdk
from aws_cdk import CfnOutput, Duration, Expiration, Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_appsync as appsync
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as cloudwatch_actions
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as lambda_event_sources
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as sns_subscriptions
from aws_cdk import aws_sqs as sqs
from constructs import Construct

from stacks.cognito_construct import CognitoConstruct

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

        table = self._create_table()
        queue, dlq = self._create_queues()
        documents_bucket = self._create_documents_bucket()

        bundling = self._build_bundling_options()

        cognito = self._create_cognito(table, bundling)

        common_environment = self._build_common_environment(
            table, queue, documents_bucket, cognito
        )

        api_handler = self._create_api_lambda(table, queue, bundling, common_environment)
        worker_handler = self._create_worker_lambda(table, queue, bundling, common_environment)

        documents_bucket.grant_read_write(api_handler)
        cognito.grant_admin_actions(api_handler)

        api = self._create_api(api_handler)

        worker_handler.add_event_source(
            lambda_event_sources.SqsEventSource(queue, batch_size=1)
        )

        appsync_url, appsync_api_key = self._create_appsync_api()
        worker_handler.add_environment("APPSYNC_ENDPOINT", appsync_url)
        worker_handler.add_environment("APPSYNC_API_KEY", appsync_api_key)
        api_handler.add_environment("APPSYNC_ENDPOINT", appsync_url)
        api_handler.add_environment("APPSYNC_API_KEY", appsync_api_key)

        self._create_monitoring(dlq)

        CfnOutput(self, "ApiUrl", value=api.url, description=f"API Gateway URL — {environment}")
        CfnOutput(self, "TableName", value=table.table_name)
        CfnOutput(self, "QueueUrl", value=queue.queue_url)
        CfnOutput(self, "DlqUrl", value=dlq.queue_url)
        CfnOutput(self, "BucketName", value=documents_bucket.bucket_name)
        CfnOutput(self, "ApiLambdaName", value=api_handler.function_name)
        CfnOutput(self, "WorkerLambdaName", value=worker_handler.function_name)
        CfnOutput(self, "AppSyncUrl", value=appsync_url, description="AppSync GraphQL URL")
        CfnOutput(self, "AppSyncApiKey", value=appsync_api_key, description="AppSync API key")

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

    def _create_documents_bucket(self) -> s3.Bucket:
        frontend_domain = os.environ.get("FRONTEND_DOMAIN", "")

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
        table: dynamodb.Table,
        bundling: cdk.BundlingOptions,
    ) -> CognitoConstruct:
        """Create the Cognito User Pool, App Client, and Migration Lambda."""
        frontend_domain = os.environ.get("FRONTEND_DOMAIN", "")

        return CognitoConstruct(
            self,
            "Cognito",
            environment=self._environment,
            removal_policy=self._config["removal_policy"],
            table=table,
            bundling=bundling,
            lambda_architecture=self._lambda_architecture,
            frontend_domain=frontend_domain,
        )

    # ── Shared helpers ─────────────────────────────────────────────────────────

    def _build_bundling_options(self) -> cdk.BundlingOptions:
        """Build the Docker bundling config shared by both Lambdas.

        TODO: Extract the inline bash command to infrastructure/scripts/bundle.sh
        for readability and testability. The script should cd /asset-input before
        running pip install, since CDK mounts the asset source there.
        """
        # Note: GH_TOKEN and DEPLOY_KEY_B64 are visible in Docker layer history.
        # This is acceptable because the bundling container is ephemeral and the
        # layers are never pushed to a registry — they exist only during cdk deploy.
        gh_token = os.environ.get("GH_TOKEN", "")
        deploy_key_b64 = os.environ.get("DEPLOY_KEY_B64", "")

        return cdk.BundlingOptions(
            image=cdk.DockerImage.from_registry("python:3.12-slim"),
            user="root",
            environment={"DEPLOY_KEY_B64": deploy_key_b64, "GH_TOKEN": gh_token},
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
                        ' elif [ -n "$GH_TOKEN" ]; then'
                        ' git config --global url."https://x-access-token:${GH_TOKEN}@github.com/".insteadOf "https://github.com/";'
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

    # ── Lambda (API) ───────────────────────────────────────────────────────────

    def _create_api_lambda(
        self,
        table: dynamodb.Table,
        queue: sqs.Queue,
        bundling: cdk.BundlingOptions,
        environment: dict[str, str],
    ) -> lambda_.Function:
        """Create the API Gateway-facing Lambda (fast reads/writes, 30s timeout)."""
        log_group = logs.LogGroup(
            self,
            "ApiHandlerLogs",
            log_group_name=f"/aws/lambda/janus-api-{self._environment}",
            retention=_LOG_RETENTION_MAP.get(
                self._config.get("log_retention_days", 7), logs.RetentionDays.ONE_WEEK
            ),
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        handler = lambda_.Function(
            self,
            "ApiHandler",
            function_name=f"janus-api-{self._environment}",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=self._lambda_architecture,
            handler="src.handlers.api_handler_entry.handle_api_event",
            code=lambda_.Code.from_asset("../backend", bundling=bundling),
            timeout=Duration.seconds(30),
            memory_size=512,
            log_group=log_group,
            environment=environment,
            tracing=(
                lambda_.Tracing.ACTIVE
                if self._config.get("enable_monitoring")
                else lambda_.Tracing.DISABLED
            ),
        )

        table.grant_read_write_data(handler)
        queue.grant_send_messages(handler)

        return handler

    # ── Lambda (Worker) ────────────────────────────────────────────────────────

    def _create_worker_lambda(
        self,
        table: dynamodb.Table,
        queue: sqs.Queue,
        bundling: cdk.BundlingOptions,
        environment: dict[str, str],
    ) -> lambda_.Function:
        """Create the SQS worker Lambda (long-running AI pipeline, 540s timeout)."""
        log_group = logs.LogGroup(
            self,
            "WorkerHandlerLogs",
            log_group_name=f"/aws/lambda/janus-worker-{self._environment}",
            retention=_LOG_RETENTION_MAP.get(
                self._config.get("log_retention_days", 7), logs.RetentionDays.ONE_WEEK
            ),
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        handler = lambda_.Function(
            self,
            "WorkerHandler",
            function_name=f"janus-worker-{self._environment}",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=self._lambda_architecture,
            handler="src.handlers.worker_handler_entry.handle_worker_event",
            code=lambda_.Code.from_asset("../backend", bundling=bundling),
            timeout=Duration.seconds(540),
            memory_size=1769,
            reserved_concurrent_executions=5,
            log_group=log_group,
            environment=environment,
            tracing=(
                lambda_.Tracing.ACTIVE
                if self._config.get("enable_monitoring")
                else lambda_.Tracing.DISABLED
            ),
        )

        table.grant_read_write_data(handler)
        queue.grant_consume_messages(handler)

        return handler

    # ── API Gateway ───────────────────────────────────────────────────────────

    def _create_api(self, handler: lambda_.Function) -> apigw.LambdaRestApi:
        frontend_domain = os.environ.get("FRONTEND_DOMAIN", "")

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

    # ── AppSync (real-time progress) ─────────────────────────────────────────

    def _create_appsync_api(self) -> tuple[str, str]:
        """Create an AppSync GraphQL API for real-time scan progress subscriptions.

        Returns a tuple of (graphql_url, api_key_value) for use as Lambda env vars.
        """
        graphql_api = appsync.GraphqlApi(
            self,
            "ProgressApi",
            name=f"janus-progress-{self._environment}",
            definition=appsync.Definition.from_file(
                os.path.join(os.path.dirname(__file__), "..", "schema.graphql")
            ),
            authorization_config=appsync.AuthorizationConfig(
                default_authorization=appsync.AuthorizationMode(
                    authorization_type=appsync.AuthorizationType.API_KEY,
                    api_key_config=appsync.ApiKeyConfig(
                        name="progress-key",
                        expires=Expiration.after(Duration.days(365)),
                    ),
                )
            ),
            log_config=appsync.LogConfig(
                field_log_level=appsync.FieldLogLevel.ERROR,
            ),
        )

        none_datasource = graphql_api.add_none_data_source(
            "NoneDataSource",
            description="Pass-through data source for subscription mutations",
        )

        none_datasource.create_resolver(
            "PublishProgressResolver",
            type_name="Mutation",
            field_name="publishProgress",
            request_mapping_template=appsync.MappingTemplate.from_string(
                '{"version": "2017-02-28", "payload": $util.toJson($context.arguments.input)}'
            ),
            response_mapping_template=appsync.MappingTemplate.from_string(
                "$util.toJson($context.result)"
            ),
        )

        api_key = graphql_api.api_key
        if api_key is None:
            raise RuntimeError("AppSync API key was not created — check authorization config")

        return graphql_api.graphql_url, api_key

    # ── Monitoring ───────────────────────────────────────────────────────────

    def _create_monitoring(self, dlq: sqs.Queue) -> None:
        """Create DLQ alarm and SNS alert topic (staging + production only)."""
        if not self._config.get("enable_monitoring"):
            return

        alert_topic = sns.Topic(
            self,
            "AlertTopic",
            topic_name=f"janus-alerts-{self._environment}",
            display_name=f"Janus Alerts — {self._environment}",
        )

        dlq_alarm = cloudwatch.Alarm(
            self,
            "DlqAlarm",
            metric=dlq.metric_approximate_number_of_messages_visible(
                period=Duration.minutes(1),
                statistic="Maximum",
            ),
            threshold=0,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            evaluation_periods=1,
            alarm_name=f"janus-dlq-messages-{self._environment}",
            alarm_description=(
                f"Messages in DLQ for Janus {self._environment}. "
                "Pipeline failures exceeded 3 retries."
            ),
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        dlq_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alert_topic))
        dlq_alarm.add_ok_action(cloudwatch_actions.SnsAction(alert_topic))

        alert_email = os.environ.get("ALERT_EMAIL", "")
        if alert_email:
            alert_topic.add_subscription(
                sns_subscriptions.EmailSubscription(alert_email)
            )

        CfnOutput(
            self,
            "AlertTopicArn",
            value=alert_topic.topic_arn,
            description="SNS topic for DLQ and operational alerts",
        )
