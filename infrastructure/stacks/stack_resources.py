"""Top-level AWS resources owned by the Janus stack.

These are module-level helpers (not a Construct) so resources remain
parented to the stack — their logical IDs (``JanusTable``,
``AnalysisQueue``, ``DocumentsBucket``, etc.) must stay byte-identical
to the pre-split layout. Wrapping them in a sub-Construct would change
their CloudFormation paths and force a redeploy.
"""

from __future__ import annotations

from typing import Any

from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sqs as sqs
from constructs import Construct


def create_table(
    scope: Construct,
    *,
    environment: str,
    removal_policy: RemovalPolicy,
    point_in_time_recovery: bool,
) -> dynamodb.Table:
    """Create the single-table DynamoDB design with 4 GSIs."""
    table = dynamodb.Table(
        scope,
        "JanusTable",
        table_name=f"janus-{environment}",
        partition_key=dynamodb.Attribute(name="pk", type=dynamodb.AttributeType.STRING),
        sort_key=dynamodb.Attribute(name="sk", type=dynamodb.AttributeType.STRING),
        billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        removal_policy=removal_policy,
        point_in_time_recovery=point_in_time_recovery,
        encryption=dynamodb.TableEncryption.AWS_MANAGED,
        # Soft-delete recovery (see openspec change `soft-delete-recovery`):
        # tombstoned items carry a `ttl` epoch-seconds attribute set to
        # `deleted_at + 90 days`. DynamoDB TTL hard-evicts the row after
        # that window so we don't accumulate dead records forever.
        # The attribute name MUST match `_tombstones.TTL_FIELD`.
        time_to_live_attribute="ttl",
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


def create_queues(
    scope: Construct,
    *,
    environment: str,
) -> tuple[sqs.Queue, sqs.Queue]:
    """Create the analysis SQS queue + its dead-letter queue."""
    dlq = sqs.Queue(
        scope,
        "AnalysisDLQ",
        queue_name=f"janus-analysis-dlq-{environment}",
        retention_period=Duration.days(14),
    )
    queue = sqs.Queue(
        scope,
        "AnalysisQueue",
        queue_name=f"janus-analysis-queue-{environment}",
        visibility_timeout=Duration.seconds(600),
        retention_period=Duration.days(1),
        dead_letter_queue=sqs.DeadLetterQueue(queue=dlq, max_receive_count=20),
    )
    return queue, dlq


def create_analytics_log_group(
    scope: Construct,
    *,
    environment: str,
    removal_policy: RemovalPolicy,
) -> logs.LogGroup:
    """Create the dedicated log group the API Lambda writes CTA analytics into.

    Isolated from the API Lambda's own log group so Logs Insights funnel
    queries never have to filter operational log noise. 90-day retention
    matches the design (see
    ``openspec/changes/opportunities-cta-analytics/design.md``).
    """
    return logs.LogGroup(
        scope,
        "AnalyticsEventsLogGroup",
        log_group_name=f"/janus/{environment}/analytics-events",
        retention=logs.RetentionDays.THREE_MONTHS,
        removal_policy=removal_policy,
    )


def create_documents_bucket(
    scope: Construct,
    *,
    environment: str,
    removal_policy: RemovalPolicy,
    frontend_domain: str,
) -> s3.Bucket:
    """Create the documents bucket (for customer uploads) with CORS."""
    return s3.Bucket(
        scope,
        "DocumentsBucket",
        removal_policy=removal_policy,
        auto_delete_objects=environment == "development",
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


def create_api(
    scope: Construct,
    *,
    environment: str,
    config: dict[str, Any],
    handler: lambda_.Function,
    frontend_domain: str,
) -> apigw.LambdaRestApi:
    """Create the API Gateway that fronts the API Lambda.

    Fails fast at synth time for non-development environments that do
    not supply an explicit ``FRONTEND_DOMAIN`` (or Amplify-derived
    domain) — a permissive ``*`` CORS policy in staging/production is a
    security regression we refuse to paper over.
    """
    if frontend_domain:
        cors_origins = [frontend_domain]
    elif environment == "development":
        cors_origins = apigw.Cors.ALL_ORIGINS
    else:
        message = (
            f"FRONTEND_DOMAIN must be set for environment '{environment}'. "
            "Example: https://development.d1234abcdef.amplifyapp.com"
        )
        raise ValueError(message)

    return apigw.LambdaRestApi(
        scope,
        "ApiEndpoint",
        handler=handler,
        rest_api_name=f"janus-api-{environment}",
        description=f"Janus PE Risk Assessment API — {environment}",
        default_cors_preflight_options=apigw.CorsOptions(
            allow_origins=cors_origins,
            allow_methods=apigw.Cors.ALL_METHODS,
            allow_headers=["Content-Type", "Authorization"],
        ),
        deploy_options=apigw.StageOptions(
            stage_name=environment,
            throttling_rate_limit=config["api_rate_limit"],
            throttling_burst_limit=config["api_burst_limit"],
            logging_level=(
                apigw.MethodLoggingLevel.INFO
                if config.get("enable_monitoring")
                else apigw.MethodLoggingLevel.OFF
            ),
            metrics_enabled=bool(config.get("enable_monitoring")),
            tracing_enabled=bool(config.get("enable_monitoring")),
        ),
    )
