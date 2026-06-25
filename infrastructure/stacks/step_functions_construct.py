"""Step Functions construct for portfolio batch coordination.

Creates a state machine that dispatches company analyses in waves,
avoiding SQS poller throttle by using direct Lambda invocation.
"""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import Duration
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as sfn_tasks
from constructs import Construct

from stacks.lambda_factory import build_backend_code


class StepFunctionsConstruct(Construct):
    """Portfolio batch coordinator using Step Functions."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        environment: str,
        bundling: cdk.BundlingOptions,
        lambda_architecture: lambda_.Architecture,
        worker_lambda: lambda_.Function,
        table_name: str,
        log_retention: logs.RetentionDays = logs.RetentionDays.ONE_WEEK,
        appsync_endpoint: str = "",
        appsync_api_key: str = "",
    ) -> None:
        super().__init__(scope, construct_id)

        shared_environment = {
            "DYNAMODB_TABLE": table_name,
            "WORKER_FUNCTION_NAME": worker_lambda.function_name,
            "APPSYNC_ENDPOINT": appsync_endpoint,
            "APPSYNC_API_KEY": appsync_api_key,
        }

        # ── Lambda functions for each state ──────────────────────────

        send_wave_fn = self._create_lambda(
            "SendWave",
            function_name=f"sc0red-services-send-wave-{environment}",
            handler="src.handlers.step_function_entry.handle_send_wave_event",
            bundling=bundling,
            architecture=lambda_architecture,
            environment=shared_environment,
            timeout_seconds=30,
            memory_size=256,
            log_retention=log_retention,
        )
        # send_wave needs to invoke the worker Lambda
        worker_lambda.grant_invoke(send_wave_fn)

        check_wave_fn = self._create_lambda(
            "CheckWave",
            function_name=f"sc0red-services-check-wave-{environment}",
            handler="src.handlers.step_function_entry.handle_check_wave_event",
            bundling=bundling,
            architecture=lambda_architecture,
            environment={"DYNAMODB_TABLE": table_name},
            timeout_seconds=15,
            memory_size=256,
            log_retention=log_retention,
        )

        mark_complete_fn = self._create_lambda(
            "MarkComplete",
            function_name=f"sc0red-services-mark-complete-{environment}",
            handler="src.handlers.step_function_entry.handle_mark_complete_event",
            bundling=bundling,
            architecture=lambda_architecture,
            environment={
                "DYNAMODB_TABLE": table_name,
                "APPSYNC_ENDPOINT": appsync_endpoint,
                "APPSYNC_API_KEY": appsync_api_key,
            },
            timeout_seconds=15,
            memory_size=256,
            log_retention=log_retention,
        )

        # ── State machine definition ─────────────────────────────────

        send_wave_state = sfn_tasks.LambdaInvoke(
            self,
            "SendWaveTask",
            lambda_function=send_wave_fn,
            output_path="$.Payload",
            retry_on_service_exceptions=True,
        )

        wait_state = sfn.Wait(
            self,
            "WaitForWave",
            time=sfn.WaitTime.duration(Duration.seconds(30)),
        )

        check_wave_state = sfn_tasks.LambdaInvoke(
            self,
            "CheckWaveTask",
            lambda_function=check_wave_fn,
            output_path="$.Payload",
            retry_on_service_exceptions=True,
        )

        mark_complete_state = sfn_tasks.LambdaInvoke(
            self,
            "MarkCompleteTask",
            lambda_function=mark_complete_fn,
            output_path="$.Payload",
            retry_on_service_exceptions=True,
        )

        # Choice: is the wave done?
        wave_choice = sfn.Choice(self, "WaveDone?")
        has_remaining = sfn.Choice(self, "MoreCompanies?")

        # Wire the state machine:
        # SendWave → Wait → Check → wave_done?
        #   No  → loop back to Wait (poll again)
        #   Yes → remaining_count > 0?
        #     Yes → loop back to SendWave (next wave)
        #     No  → MarkComplete (all done)
        definition = (
            send_wave_state
            .next(wait_state)
            .next(check_wave_state)
            .next(
                wave_choice
                .when(
                    sfn.Condition.boolean_equals("$.wave_done", False),
                    wait_state,
                )
                .otherwise(
                    has_remaining
                    .when(
                        sfn.Condition.number_greater_than("$.remaining_count", 0),
                        send_wave_state,
                    )
                    .otherwise(mark_complete_state)
                )
            )
        )

        self._check_wave_fn = check_wave_fn
        self._mark_complete_fn = mark_complete_fn

        self._state_machine = sfn.StateMachine(
            self,
            "PortfolioBatchCoordinator",
            state_machine_name=f"sc0red-services-portfolio-batch-{environment}",
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            timeout=Duration.hours(2),
            tracing_enabled=True,
        )

    @property
    def state_machine_arn(self) -> str:
        """ARN of the portfolio batch coordinator state machine."""
        return self._state_machine.state_machine_arn

    def grant_start_execution(self, grantee: iam.IGrantable) -> None:
        """Allow a Lambda to start executions of this state machine."""
        self._state_machine.grant_start_execution(grantee)

    def grant_table_access(self, table: object) -> None:
        """Grant DynamoDB read/write to check-wave and mark-complete Lambdas."""
        table.grant_read_data(self._check_wave_fn)  # type: ignore[union-attr]
        table.grant_read_write_data(self._mark_complete_fn)  # type: ignore[union-attr]

    def _create_lambda(
        self,
        construct_id: str,
        *,
        function_name: str,
        handler: str,
        bundling: cdk.BundlingOptions,
        architecture: lambda_.Architecture,
        environment: dict[str, str],
        timeout_seconds: int,
        memory_size: int,
        log_retention: logs.RetentionDays,
    ) -> lambda_.Function:
        log_group = logs.LogGroup(
            self,
            f"{construct_id}Logs",
            log_group_name=f"/aws/lambda/{function_name}",
            retention=log_retention,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        return lambda_.Function(
            self,
            construct_id,
            function_name=function_name,
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=architecture,
            handler=handler,
            code=build_backend_code(bundling, architecture),
            timeout=Duration.seconds(timeout_seconds),
            memory_size=memory_size,
            environment=environment,
            log_group=log_group,
        )
