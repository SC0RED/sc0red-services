"""AppSync real-time progress API and monitoring alarms for Janus.

Extracted from janus_stack.py to stay under the 400-line file limit.
"""

import os
from pathlib import Path
from typing import Any

import aws_cdk as cdk
from aws_cdk import CfnOutput, Duration, Expiration
from aws_cdk import aws_appsync as appsync
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as cloudwatch_actions
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as sns_subscriptions
from aws_cdk import aws_sqs as sqs
from constructs import Construct


class ObservabilityConstruct(Construct):
    """AppSync progress API and CloudWatch monitoring."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        environment: str,
        config: dict[str, Any],
        dlq: sqs.Queue,
    ) -> None:
        super().__init__(scope, construct_id)

        self._appsync_url, self._appsync_api_key = self._create_appsync_api(
            environment
        )

        self._create_monitoring(environment, config, dlq)

    @property
    def appsync_url(self) -> str:
        """AppSync GraphQL endpoint URL."""
        return self._appsync_url

    @property
    def appsync_api_key(self) -> str:
        """AppSync API key value."""
        return self._appsync_api_key

    def _create_appsync_api(self, environment: str) -> tuple[str, str]:
        """Create an AppSync GraphQL API for real-time scan progress subscriptions."""
        graphql_api = appsync.GraphqlApi(
            self,
            "ProgressApi",
            name=f"janus-progress-{environment}",
            definition=appsync.Definition.from_file(
                str(Path(__file__).parent.parent / "schema.graphql")
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
            raise RuntimeError(
                "AppSync API key was not created — check authorization config"
            )

        stack = cdk.Stack.of(self)
        CfnOutput(
            stack,
            "AppSyncUrl",
            value=graphql_api.graphql_url,
            description="AppSync GraphQL URL",
        )
        CfnOutput(stack, "AppSyncApiKey", value=api_key, description="AppSync API key")

        return graphql_api.graphql_url, api_key

    def _create_monitoring(
        self,
        environment: str,
        config: dict[str, Any],
        dlq: sqs.Queue,
    ) -> None:
        """Create DLQ alarm and SNS alert topic (staging + production only)."""
        if not config.get("enable_monitoring"):
            return

        stack = cdk.Stack.of(self)

        alert_topic = sns.Topic(
            self,
            "AlertTopic",
            display_name=f"Janus Alerts — {environment}",
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
            alarm_description=(
                f"Messages in DLQ for Janus {environment}. "
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
            stack,
            "AlertTopicArn",
            value=alert_topic.topic_arn,
            description="SNS topic for DLQ and operational alerts",
        )
