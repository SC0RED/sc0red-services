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

environment_config: dict[str, object] = {
    "development": {
        "removal_policy": cdk.RemovalPolicy.DESTROY,
        "log_retention_days": 7,
        "enable_monitoring": False,
        "point_in_time_recovery": False,
    },
    "staging": {
        "removal_policy": cdk.RemovalPolicy.SNAPSHOT,
        "log_retention_days": 30,
        "enable_monitoring": True,
        "point_in_time_recovery": True,
    },
    "production": {
        "removal_policy": cdk.RemovalPolicy.RETAIN,
        "log_retention_days": 90,
        "enable_monitoring": True,
        "point_in_time_recovery": True,
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
