"""Janus CDK stack — DynamoDB, SQS, Lambda, API Gateway."""

import os
from typing import Any

import aws_cdk as cdk
from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as lambda_event_sources
from aws_cdk import aws_logs as logs
from aws_cdk import aws_sqs as sqs
from constructs import Construct


class JanusStack(Stack):
    """Main stack: DynamoDB table, SQS queue, Lambda handler, API Gateway."""

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

        table = self._create_table()
        queue, dlq = self._create_queues()
        handler = self._create_lambda(table, queue)
        api = self._create_api(handler)

        handler.add_event_source(lambda_event_sources.SqsEventSource(queue, batch_size=1))

        CfnOutput(self, "ApiUrl", value=api.url, description=f"API Gateway URL — {environment}")
        CfnOutput(self, "TableName", value=table.table_name)
        CfnOutput(self, "QueueUrl", value=queue.queue_url)
        CfnOutput(self, "DlqUrl", value=dlq.queue_url)

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
            point_in_time_recovery=False,
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

    # ── Lambda ────────────────────────────────────────────────────────────────

    def _create_lambda(self, table: dynamodb.Table, queue: sqs.Queue) -> lambda_.Function:
        gh_token = os.environ.get("GH_TOKEN", "")
        deploy_key_b64 = os.environ.get("DEPLOY_KEY_B64", "")

        log_group = logs.LogGroup(
            self,
            "ApiHandlerLogs",
            log_group_name=f"/aws/lambda/janus-{self._environment}",
            retention=logs.RetentionDays.THREE_DAYS,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        handler = lambda_.Function(
            self,
            "ApiHandler",
            function_name=f"janus-{self._environment}",
            runtime=lambda_.Runtime.PYTHON_3_12,
            # ARM_64 for local development (Apple Silicon); X86_64 for CI/CD where
            # GitHub Actions runs on x86_64 — native wheels must match execution env.
            architecture=(
                lambda_.Architecture.ARM_64
                if self._environment == "development"
                else lambda_.Architecture.X86_64
            ),
            handler="src.handlers.handler.handle_event",
            code=lambda_.Code.from_asset(
                "../backend",
                bundling=cdk.BundlingOptions(
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
                ),
            ),
            timeout=Duration.seconds(300),
            memory_size=512,
            log_group=log_group,
            environment={
                "DYNAMODB_TABLE": table.table_name,
                "ANALYSIS_QUEUE_URL": queue.queue_url,
                "STAGE": self._environment,
                "NEXTAUTH_SECRET": os.environ.get(
                    "NEXTAUTH_SECRET", "dev-secret-minimum-32-characters-long"
                ),
                "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", "sk-placeholder"),
            },
        )

        table.grant_read_write_data(handler)
        queue.grant_send_messages(handler)
        queue.grant_consume_messages(handler)

        return handler

    # ── API Gateway ───────────────────────────────────────────────────────────

    def _create_api(self, handler: lambda_.Function) -> apigw.LambdaRestApi:
        frontend_domain = os.environ.get("FRONTEND_DOMAIN", "*")

        cors_origins = (
            apigw.Cors.ALL_ORIGINS
            if frontend_domain == "*"
            else [frontend_domain]
        )

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
                logging_level=(
                    apigw.MethodLoggingLevel.INFO
                    if self._config.get("enable_monitoring")
                    else apigw.MethodLoggingLevel.OFF
                ),
                metrics_enabled=bool(self._config.get("enable_monitoring")),
            ),
        )

        return api
