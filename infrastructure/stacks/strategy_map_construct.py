"""On-demand strategy-map worker — dedicated SQS queue + Lambda function.

Per the strategy-map-on-demand spec (decision §2), strategy-map generation
runs on its own queue + Lambda, isolated from the main analysis pipeline so:
  - Strategy-map jobs (one per click, expensive ~55s) don't tune the main
    visibility-timeout against the slowest job, hurting throughput on shorter
    analyses.
  - Per-queue CloudWatch metrics give clean observability for the strategy-
    map workload specifically.
  - A worker crash (OpenAI rate limit, schema regression) is isolated — the
    main analysis worker keeps draining its queue.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import aws_cdk as cdk
from aws_cdk import Duration
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as lambda_event_sources
from aws_cdk import aws_sqs as sqs
from constructs import Construct

from stacks.lambda_factory import create_lambda

if TYPE_CHECKING:
    from aws_cdk import aws_dynamodb as dynamodb


class StrategyMapConstruct(Construct):
    """Provisions the dedicated strategy-map queue + worker Lambda.

    The construct owns:
      - ``janus-strategy-map-queue-{env}`` SQS queue + DLQ + alarm
      - ``janus-strategy-map-worker-{env}`` Lambda function
      - SQS event-source mapping wiring queue → Lambda
      - IAM permissions: read+write the DynamoDB table
      - Env vars: APPSYNC_*, OPENAI_*/ANTHROPIC_*, AWS_ENDPOINT_URL (inherited
        from `common_environment` which the caller passes in)

    Caller is responsible for:
      - Granting the API Lambda `send_messages` on `queue` so the API handler
        can enqueue
      - Passing `STRATEGY_MAP_QUEUE_URL` env var to the API Lambda
      - Granting the worker any cross-construct permissions (Cognito etc.)
        if/when those become needed
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        environment: str,
        bundling: cdk.BundlingOptions,
        common_environment: dict[str, str],
        table: dynamodb.Table,
        lambda_architecture: lambda_.Architecture,
        log_retention_days: int,
        enable_tracing: bool,
        enable_monitoring: bool,
        appsync_endpoint: str,
        appsync_api_key: str,
    ) -> None:
        super().__init__(scope, construct_id)
        self.dlq_alarm: cloudwatch.Alarm | None = None

        # Dead-letter queue: messages land here after maxReceiveCount retries.
        # Retention is 14 days so ops has time to inspect failed messages.
        self.dlq = sqs.Queue(
            self,
            "StrategyMapDLQ",
            queue_name=f"janus-strategy-map-dlq-{environment}",
            retention_period=Duration.days(14),
        )

        # Main queue. Visibility timeout is 720 seconds (12 minutes) — six
        # times the worker Lambda's 120-second timeout, per the AWS recommended
        # SQS-Lambda integration ratio. This ensures a message stays
        # invisible for the full duration the Lambda could be processing it
        # (worst case: full timeout) plus an exponential-backoff buffer for
        # SQS-internal retries. The actual call shape today is ~55s and drops
        # to ~17s after `optimize-strategy-map-latency` Phase 1, so the long
        # visibility window does NOT delay user-visible recovery — it only
        # affects the failure path.
        #
        # Earlier this construct shipped with `visibility_timeout=90` while
        # the Lambda timeout was 120s. AWS rejected the event-source mapping
        # at deploy time with `Queue visibility timeout: 90 seconds is less
        # than Function timeout: 120 seconds`. The minimum for any
        # SQS-Lambda mapping is `>= function_timeout`; we use the recommended
        # 6× multiplier to leave operational headroom.
        self.queue = sqs.Queue(
            self,
            "StrategyMapQueue",
            queue_name=f"janus-strategy-map-queue-{environment}",
            visibility_timeout=Duration.seconds(720),
            retention_period=Duration.days(4),
            # ``max_receive_count`` MUST match
            # ``StrategyMapSQSHandler._MAX_RECEIVE_COUNT`` in
            # ``backend/src/handlers/strategy_map_handler.py``. The
            # worker uses that constant to detect the final retry attempt
            # and run its fail-safe state-clear before SQS routes the
            # message to the DLQ. There is no automated drift guard
            # across the CDK / runtime boundary — change both together.
            dead_letter_queue=sqs.DeadLetterQueue(queue=self.dlq, max_receive_count=3),
        )

        # CloudWatch alarm fires when any message lands in the DLQ — three
        # retries failed and ops needs to look. Gated on ``enable_monitoring``
        # so development / E2E environments don't create alarms with no SNS
        # routing, matching the convention in ``ObservabilityConstruct``.
        if enable_monitoring:
            self.dlq_alarm = cloudwatch.Alarm(
                self,
                "StrategyMapDLQDepth",
                alarm_name=f"janus-strategy-map-dlq-depth-{environment}",
                alarm_description=(
                    "Messages on the strategy-map DLQ — investigate via CloudWatch logs "
                    "for the strategy-map-worker Lambda."
                ),
                metric=self.dlq.metric_approximate_number_of_messages_visible(
                    period=Duration.minutes(1)
                ),
                threshold=1,
                evaluation_periods=1,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            )

        # Worker Lambda — runs `StrategyMapSQSHandler` against incoming
        # messages. Memory + timeout sized for OpenAI's tail-latency shape:
        # the typical 7-call sequence runs in ~55s, but real-world traces
        # have crossed 120s on tail-latency days (initial 120s timeout
        # blew up in production on 2026-05-07 — the user's first dev click
        # timed out at exactly the budget, message went to DLQ, state
        # stuck "generating"). 300s gives ~2.5× margin over the typical
        # call shape and absorbs OpenAI tail latency without leaking
        # messages to the DLQ. Post-`optimize-strategy-map-latency` Phase 1
        # the work drops to ~17s but the headroom stays useful.
        #
        # Queue visibility timeout is 720s (Decision in this construct
        # above), which is ≥ Lambda timeout, satisfying the AWS SQS-Lambda
        # event-source mapping constraint.
        #
        # **Coverage gap — Lambda timeout vs in-process fail-safe**: the
        # ``StrategyMapSQSHandler`` fail-safe state-clear (in
        # ``backend/src/handlers/strategy_map_handler.py``) only runs when
        # a Python exception propagates out of ``_process_message``. A
        # Lambda timeout SIGKILLs the process — no ``except`` block runs.
        # The full coverage chain for the timeout case is: timeout →
        # message reappears after queue visibility expiry → next attempt
        # runs → if it ALSO times out (likely if root cause unfixed),
        # SQS increments ``ApproximateReceiveCount`` → after 3 timeouts
        # the worker would fail-safe IF it survived long enough — which
        # it doesn't, because the timeout fires first. So timeout-only
        # failures still leak to the DLQ with state stuck. The DLQ alarm
        # (above) is the operator-facing signal for this case. A future
        # follow-up could subscribe an EventBridge rule to Lambda
        # timeout events and run a dedicated cleanup Lambda; not in
        # scope for this hotfix.
        worker_environment = dict(common_environment)
        worker_environment["APPSYNC_ENDPOINT"] = appsync_endpoint
        worker_environment["APPSYNC_API_KEY"] = appsync_api_key

        self.worker = create_lambda(
            self,
            "StrategyMapWorker",
            function_name=f"janus-strategy-map-worker-{environment}",
            handler="src.handlers.strategy_map_worker_entry.handle_event",
            bundling=bundling,
            environment=worker_environment,
            timeout_seconds=300,
            memory_size=1024,
            architecture=lambda_architecture,
            log_retention_days=log_retention_days,
            enable_tracing=enable_tracing,
            reserved_concurrency=4,  # bounded; user-clicks shouldn't burst
        )

        # IAM: the worker reads + writes the DynamoDB table (loads assessment
        # data, persists strategy map, clears generation state). It also
        # consumes the queue (event-source mapping below).
        table.grant_read_write_data(self.worker)
        self.queue.grant_consume_messages(self.worker)

        # Event-source mapping. `report_batch_item_failures=True` lets the
        # worker return per-record retry decisions (programming errors retry;
        # domain errors are translated to AppSync `strategy_map_failed` and
        # consumed via the empty `batchItemFailures` list).
        self.worker.add_event_source(
            lambda_event_sources.SqsEventSource(
                self.queue,
                batch_size=1,
                report_batch_item_failures=True,
            )
        )
