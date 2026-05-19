#!/usr/bin/env python3
"""CDK application entry point for sc0red Services."""

import os
from datetime import UTC, datetime

import aws_cdk as cdk

from stacks.sc0red_services_stack import Sc0redServicesStack

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

environment_config: dict[str, object] = {
    "development": {
        "removal_policy": cdk.RemovalPolicy.DESTROY,
        "log_retention_days": 7,
        "enable_monitoring": False,
        "point_in_time_recovery": False,
        "lambda_architecture": "arm64",
        "api_rate_limit": 50,
        "api_burst_limit": 100,
    },
    "staging": {
        "removal_policy": cdk.RemovalPolicy.SNAPSHOT,
        "log_retention_days": 30,
        "enable_monitoring": True,
        "point_in_time_recovery": False,
        "lambda_architecture": "x86_64",
        "api_rate_limit": 50,
        "api_burst_limit": 100,
        "github_repository": "https://github.com/SC0RED/sc0red-services",
        "amplify_branch": "development",
    },
    "testing": {
        "removal_policy": cdk.RemovalPolicy.SNAPSHOT,
        "log_retention_days": 30,
        "enable_monitoring": True,
        "point_in_time_recovery": False,
        "lambda_architecture": "x86_64",
        "api_rate_limit": 50,
        "api_burst_limit": 100,
        "github_repository": "https://github.com/SC0RED/sc0red-services",
        "amplify_branch": "testing",
    },
    "production": {
        "removal_policy": cdk.RemovalPolicy.RETAIN,
        "log_retention_days": 90,
        "enable_monitoring": True,
        "point_in_time_recovery": True,
        "lambda_architecture": "x86_64",
        "api_rate_limit": 100,
        "api_burst_limit": 200,
        "github_repository": "https://github.com/SC0RED/sc0red-services",
        "amplify_branch": "production",
    },
}

config = environment_config.get(environment, environment_config["development"])

Sc0redServicesStack(
    app,
    f"Sc0redServices-{environment}",
    env=cdk.Environment(account=account, region=region),
    environment=environment,
    config=config,
)

# Tags are skipped for development (LocalStack v3 has a bug propagating stack tags
# to EventSourceMapping resources). Tags are applied for staging/production only.
if environment != "development":
    cdk.Tags.of(app).add("Project", "sc0red Services")
    cdk.Tags.of(app).add("ManagedBy", "CDK")
    cdk.Tags.of(app).add("Environment", environment)
    cdk.Tags.of(app).add("DeployedAt", datetime.now(UTC).isoformat())

app.synth()
