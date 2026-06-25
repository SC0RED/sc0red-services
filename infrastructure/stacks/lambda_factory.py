"""Lambda plumbing shared by the API and Worker handlers.

Kept as module-level helpers (not a Construct) so resources remain parented
to the stack — the logical IDs (``ApiHandler``, ``WorkerHandler``, etc.)
must stay byte-identical to the pre-split layout. Wrapping them in a
sub-Construct would change their CloudFormation paths and force a
redeploy.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import aws_cdk as cdk
from aws_cdk import Duration
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sqs as sqs
from constructs import Construct

if TYPE_CHECKING:
    # Type-only import: ``build_common_environment`` annotates a
    # ``CognitoConstruct`` parameter but never constructs one. Keeping this under
    # TYPE_CHECKING avoids a circular import now that ``cognito_construct``
    # imports ``build_backend_code`` from this module.
    from stacks.cognito_construct import CognitoConstruct

_LOG_RETENTION_MAP: dict[int, logs.RetentionDays] = {
    7: logs.RetentionDays.ONE_WEEK,
    30: logs.RetentionDays.ONE_MONTH,
    90: logs.RetentionDays.THREE_MONTHS,
}

# Single source of truth for the backend package directory bundled into every
# Python Lambda. Used by both the bundling builder and the asset-hash helper.
_BACKEND_ASSET_PATH = "../backend"


def build_backend_code(
    bundling: cdk.BundlingOptions,
    architecture: lambda_.Architecture,
) -> lambda_.Code:
    """Package ``../backend`` with an architecture-aware asset hash.

    CDK's default ``AssetHashType.SOURCE`` hashes only the source directory, not
    the bundle architecture, and the architecture comes from the build host (the
    runner) rather than any CDK input — so it is invisible to the hash. Flipping
    ``lambda_architecture`` without touching ``backend/`` therefore leaves the
    source hash unchanged, and CDK reuses the previously published (wrong-arch)
    zip, pushing it onto the now-different-arch functions. That is exactly what
    broke the arm64 fleet switch (#449): x86_64 binaries deployed onto arm64
    functions, failing to load at init (``_rust.abi3.so``/LWA adapter).

    Mixing the architecture into the asset hash makes an arch flip republish the
    correct bundle while preserving normal source-change detection. A custom
    ``asset_hash`` (not ``AssetHashType.OUTPUT``) is used so ``cdk synth`` does
    not have to bundle just to compute the hash — bundling stays lazy, at
    deploy/publish time.

    ``architecture.name`` (``arm64``/``x86_64``) is used rather than comparing
    ``Architecture`` instances — jsii ``Architecture`` objects do not implement
    value equality (``Architecture.ARM_64 == Architecture.ARM_64`` is ``False``),
    so an ``==`` check would silently misbehave.
    """
    source_fingerprint = cdk.FileSystem.fingerprint(_BACKEND_ASSET_PATH)
    return lambda_.Code.from_asset(
        _BACKEND_ASSET_PATH,
        bundling=bundling,
        asset_hash=f"{source_fingerprint}-{architecture.name}",
    )


def build_bundling_options(architecture: lambda_.Architecture) -> cdk.BundlingOptions:
    """Build the Docker bundling config shared by the API, worker, and MCP Lambdas.

    Reads ``DEPLOY_KEY_B64`` from the deploy environment and, when set,
    wires git-over-SSH so ``pip install`` can resolve the private
    ``signalfield-core`` dependency.

    ``platform`` is pinned to the target architecture so the bundle is built for
    the Lambda's architecture explicitly, rather than implicitly inheriting the
    build host's architecture. On a matching runner this is a native no-op; it
    guards against a runner/target mismatch silently producing a wrong-arch
    package (see ``build_backend_code``).

    NOTE (temporary coupling — see janus-mcp-server tasks.md 2.5.13): the final
    step copies the MCP Lambda's ``run_mcp.sh`` LWA startup script into the
    asset output. It is inert for the API/worker packages. This MCP-specific
    step lives here only until the LWA-via-layer approach is validated on
    staging; once confirmed, it should move to an MCP-specific bundling variant
    so this shared builder stops carrying MCP knowledge.
    """
    deploy_key_b64 = os.environ.get("DEPLOY_KEY_B64", "")

    return cdk.BundlingOptions(
        image=cdk.DockerImage.from_registry("python:3.12-slim"),
        platform=architecture.docker_platform,
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
                # The MCP Lambda runs under the AWS Lambda Web Adapter with
                # ``handler=run_mcp.sh`` (see mcp_construct.py). ``pip install .``
                # only packages the Python distribution, not loose top-level
                # files, so copy the LWA startup script to the package root and
                # mark it executable. Inert for the API/worker Lambdas — they
                # never reference it.
                "cp run_mcp.sh /asset-output/run_mcp.sh && chmod +x /asset-output/run_mcp.sh",
            ]),
        ],
    )


def build_common_environment(
    scope: Construct,
    *,
    environment: str,
    table: dynamodb.Table,
    queue: sqs.Queue,
    documents_bucket: s3.Bucket,
    cognito_construct: CognitoConstruct,
) -> dict[str, str]:
    """Build the environment variables shared by both Lambdas.

    Analytics env vars are deliberately NOT included here: only the API
    Lambda has ``logs:PutLogEvents`` permission on the analytics log
    group, so putting ``ANALYTICS_LOG_GROUP`` in the worker environment
    would invite a future change to write analytics from the worker and
    get ``AccessDeniedException`` at runtime. Wire API-only config via
    ``add_environment()`` on the API handler instead.
    """
    # Resolve region via the canonical CDK idiom — same pattern as
    # ``mcp_construct.py``. Falls back to the ambient AWS_REGION for
    # local-dev contexts where the stack region isn't set.
    region = cdk.Stack.of(scope).region or os.environ.get("AWS_REGION", "us-east-1")

    return {
        "DYNAMODB_TABLE": table.table_name,
        "ANALYSIS_QUEUE_URL": queue.queue_url,
        "DOCUMENTS_BUCKET": documents_bucket.bucket_name,
        "STAGE": environment,
        "COGNITO_USER_POOL_ID": cognito_construct.user_pool_id,
        "COGNITO_CLIENT_ID": cognito_construct.app_client_id,
        "COGNITO_REGION": region,
        "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", "sk-placeholder"),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
        "AI_PROVIDER": os.environ.get("AI_PROVIDER", "anthropic"),
    }


def create_lambda(
    scope: Construct,
    construct_id: str,
    *,
    function_name: str,
    handler: str,
    bundling: cdk.BundlingOptions,
    environment: dict[str, str],
    timeout_seconds: int,
    memory_size: int,
    architecture: lambda_.Architecture,
    log_retention_days: int,
    enable_tracing: bool,
    reserved_concurrency: int | None = None,
) -> lambda_.Function:
    """Create a Lambda function with its own log group and tracing config.

    ``reserved_concurrency`` is optional — pass ``None`` (default) to
    leave the function with account-wide unreserved concurrency. The
    worker Lambda sets this to cap concurrent analyses; the API Lambda
    leaves it unset to burst freely.
    """
    log_group = logs.LogGroup(
        scope,
        f"{construct_id}Logs",
        log_group_name=f"/aws/lambda/{function_name}",
        retention=_LOG_RETENTION_MAP.get(log_retention_days, logs.RetentionDays.ONE_WEEK),
        removal_policy=cdk.RemovalPolicy.DESTROY,
    )

    return lambda_.Function(
        scope,
        construct_id,
        function_name=function_name,
        runtime=lambda_.Runtime.PYTHON_3_12,
        architecture=architecture,
        handler=handler,
        code=build_backend_code(bundling, architecture),
        timeout=Duration.seconds(timeout_seconds),
        memory_size=memory_size,
        reserved_concurrent_executions=reserved_concurrency,
        log_group=log_group,
        environment=environment,
        tracing=lambda_.Tracing.ACTIVE if enable_tracing else lambda_.Tracing.DISABLED,
    )
