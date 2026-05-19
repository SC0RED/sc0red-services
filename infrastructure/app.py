#!/usr/bin/env python3
"""CDK application entry point for Janus."""

import os
from datetime import UTC, datetime

import aws_cdk as cdk

from stacks.janus_stack import JanusStack

app = cdk.App()

environment = (
    app.node.try_get_context("environment")
    or os.environ.get("CDK_ENVIRONMENT")
    or "development"
)

account = (
    app.node.try_get_context("account")
    or os.environ.get("CDK_DEFAULT_ACCOUNT")
    or os.environ.get("AWS_ACCOUNT_ID")
    or "000000000000"  # LocalStack default
)

region = (
    app.node.try_get_context("region")
    or os.environ.get("CDK_DEFAULT_REGION")
    or os.environ.get("AWS_REGION")
    or "us-east-1"
)

# Phase 2 host cutover (rename-janus-to-sc0red-advisory):
#
# - ``frontend_custom_domain`` is the canonical sc0red Advisory hostname that
#   each environment SHOULD serve at after the Amplify Console custom-domain
#   attachment + Route 53 records land. Used for NEXTAUTH_URL, FRONTEND_BASE_URL
#   (the print Lambda's navigation target), CONSENT_BASE_URL (MCP), and the
#   invitation-email FRONTEND_DOMAIN. Set to ``None`` when no custom domain is
#   attached yet — code falls back to the Amplify default URL.
# - ``frontend_legacy_domain`` is the previous ``*.janus.sc0red.com`` host that
#   stays accepted by CORS during the 90-day dual-serve window (see
#   ``openspec/changes/rename-janus-to-sc0red-advisory/proposal.md`` §10). Set
#   to ``None`` once the legacy host is decommissioned. Testing has no legacy
#   custom host (``testing.janus.sc0red.com`` was never attached) so it stays
#   ``None`` from day one.
environment_config: dict[str, object] = {
    "development": {
        "removal_policy": cdk.RemovalPolicy.DESTROY,
        "log_retention_days": 7,
        "enable_monitoring": False,
        "point_in_time_recovery": False,
        "lambda_architecture": "arm64",
        "api_rate_limit": 50,
        "api_burst_limit": 100,
        "frontend_custom_domain": None,
        "frontend_legacy_domain": None,
    },
    "staging": {
        "removal_policy": cdk.RemovalPolicy.SNAPSHOT,
        "log_retention_days": 30,
        "enable_monitoring": True,
        "point_in_time_recovery": False,
        "lambda_architecture": "x86_64",
        "api_rate_limit": 50,
        "api_burst_limit": 100,
        "github_repository": "https://github.com/SC0RED/janus",
        "amplify_branch": "development",
        "frontend_custom_domain": "https://dev.advisory.sc0red.com",
        "frontend_legacy_domain": "https://dev.janus.sc0red.com",
    },
    "testing": {
        "removal_policy": cdk.RemovalPolicy.SNAPSHOT,
        "log_retention_days": 30,
        "enable_monitoring": True,
        "point_in_time_recovery": False,
        "lambda_architecture": "x86_64",
        "api_rate_limit": 50,
        "api_burst_limit": 100,
        "github_repository": "https://github.com/SC0RED/janus",
        "amplify_branch": "testing",
        "frontend_custom_domain": "https://testing.advisory.sc0red.com",
        "frontend_legacy_domain": None,
    },
    "production": {
        "removal_policy": cdk.RemovalPolicy.RETAIN,
        "log_retention_days": 90,
        "enable_monitoring": True,
        "point_in_time_recovery": True,
        "lambda_architecture": "x86_64",
        "api_rate_limit": 100,
        "api_burst_limit": 200,
        "github_repository": "https://github.com/SC0RED/janus",
        "amplify_branch": "production",
        "frontend_custom_domain": "https://advisory.sc0red.com",
        "frontend_legacy_domain": "https://janus.sc0red.com",
    },
}

config = environment_config.get(environment, environment_config["development"])

JanusStack(
    app,
    f"Janus-{environment}",
    env=cdk.Environment(account=account, region=region),
    environment=environment,
    config=config,
)

# Tags are skipped for development (LocalStack v3 has a bug propagating stack tags
# to EventSourceMapping resources). Tags are applied for staging/production only.
if environment != "development":
    cdk.Tags.of(app).add("Project", "Janus")
    cdk.Tags.of(app).add("ManagedBy", "CDK")
    cdk.Tags.of(app).add("Environment", environment)
    cdk.Tags.of(app).add("DeployedAt", datetime.now(UTC).isoformat())

app.synth()
