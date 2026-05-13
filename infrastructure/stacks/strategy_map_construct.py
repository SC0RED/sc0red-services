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
        # Visibility timeout must be >= the worker Lambda timeout per the
        # AWS SQS-Lambda integration contract; AWS rejects the event-source
        # mapping at deploy time otherwise. With the Lambda timeout now at
        # 900 s (Phase 2 + retry-storm headroom, see ``timeout_seconds``
        # below) we set visibility to 1080 s — function timeout plus a
        # ~20 % buffer for SQS-internal handoff. This is well below the
        # historical 6× ratio (which would mandate 5400 s here, absurd)
        # but comfortably above the AWS minimum.
        #
        # Earlier this construct shipped with `visibility_timeout=90` while
        # the Lambda timeout was 120s. AWS rejected the event-source mapping
        # at deploy time with `Queue visibility timeout: 90 seconds is less
        # than Function timeout: 120 seconds`. The minimum for any
        # SQS-Lambda mapping is `>= function_timeout`.
        self.queue = sqs.Queue(
            self,
            "StrategyMapQueue",
            queue_name=f"janus-strategy-map-queue-{environment}",
            visibility_timeout=Duration.seconds(1080),
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
        # messages. Sized to MATCH the analysis-pipeline worker
        # (``janus-worker-{environment}`` in ``stack_resources.create_queues``
        # / ``janus_stack``): the analysis worker had been running the
        # legacy 7-call ``GenerateStrategyMap`` chain successfully as
        # one of its pipeline steps for months — same code path, same
        # call shape, no resource problems. After
        # ``strategy-map-on-demand`` Phase C the step moved into this
        # dedicated worker, but the original construct under-provisioned
        # it (120s timeout / 1024MB memory) and real-world OpenAI tail
        # latency timed out repeatedly on dev (2026-05-07 — first click
        # hit exactly 120s; bumped to 300s in PR #276 and STILL timed
        # out at 5min). The bump kept hitting the same wall because the
        # bottleneck wasn't the timeout — at 1024MB memory the Lambda
        # only gets ~0.6 of a vCPU, slowing every TLS handshake and
        # JSON-parse. 1769MB is the sweet spot where Lambda gives a full
        # vCPU (per AWS docs); the analysis worker has used this for
        # the same workload without issue.
        #
        # Current config (post-Phase-2 + retry-storm headroom):
        #   - ``timeout_seconds=900`` (15 min — Lambda max; allows tail-
        #     latency events from OpenAI retries without timing out the
        #     user-clicked job)
        #   - ``memory_size=2048`` (~1.16 vCPU; slight bump over the
        #     1769 MB analysis-worker baseline for faster Pydantic
        #     validation and prompt rendering)
        #   - ``reserved_concurrency=4`` (bounded; on-demand clicks
        #     shouldn't burst)
        #
        # The 540 s / 1769 MB envelope was adequate for clean-path Phase 2
        # runs (~45 s end-to-end) but a tail-latency event on 2026-05-11
        # IST night saw three companies hit back-to-back OpenAI retries
        # that pushed the worker beyond 540 s. The bump to 900 s / 2048 MB
        # eliminated those timeouts across the 5-company manual-eval
        # batch.
        #
        # Queue visibility timeout is 1080 s, which is > 900 s Lambda
        # timeout, satisfying AWS's SQS-Lambda event-source mapping
        # constraint with a ~20 % buffer.
        #
        # **Coverage gap — Lambda timeout vs in-process fail-safe**: the
        # ``StrategyMapSQSHandler`` fail-safe state-clear (in
        # ``backend/src/handlers/strategy_map_handler.py``) only runs when
        # a Python exception propagates out of ``_process_message``. A
        # Lambda timeout SIGKILLs the process — no ``except`` block runs.
        # The DLQ alarm above is the operator-facing signal for that mode.
        # A future follow-up could subscribe an EventBridge rule to
        # Lambda timeout events and run a dedicated cleanup Lambda.
        worker_environment = dict(common_environment)
        worker_environment["APPSYNC_ENDPOINT"] = appsync_endpoint
        worker_environment["APPSYNC_API_KEY"] = appsync_api_key

        # The decomposed strategy-map generation path is the only path
        # — the legacy monolithic step runners and the
        # ``GENERATE_STRATEGY_MAP_DECOMPOSED`` / ``…_SYNTHESIS`` feature
        # flags were removed end-to-end by the ``redesign-strategy-map``
        # Phase 3 change.

        self.worker = create_lambda(
            self,
            "StrategyMapWorker",
            function_name=f"janus-strategy-map-worker-{environment}",
            handler="src.handlers.strategy_map_worker_entry.handle_event",
            bundling=bundling,
            environment=worker_environment,
            # Timeout = 900 s (15 min, Lambda max). The 540 s envelope was
            # adequate for clean-path runs (Phase 2 lands ~45 s end-to-end)
            # but a tail-latency event on 2026-05-11 IST night saw three
            # companies hit back-to-back OpenAI retries that stacked above
            # 540 s on the synthesis singletons. 900 s gives the headroom
            # to absorb retry storms without timing out the user.
            timeout_seconds=900,
            # Memory = 2048 MB. Above the 1769 MB tier so Lambda allocates
            # >1 vCPU (1.16 vCPU equivalent); a small but measurable boost
            # to Python execution of prompt rendering, assembly, and
            # Pydantic validation. Cost ~15 % higher per invocation but
            # invocations are user-clicked and infrequent.
            memory_size=2048,
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
