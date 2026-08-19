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
        # Account 484719706337 is still in the SES sandbox, where SES would
        # refuse every unverified recipient. Cognito's own sender is worse for
        # deliverability but at least reaches everyone. See SPE-2150.
        "cognito_ses_email_sender": False,
    },
    "staging": {
        "removal_policy": cdk.RemovalPolicy.SNAPSHOT,
        "log_retention_days": 30,
        "enable_monitoring": True,
        "point_in_time_recovery": False,
        # arm64 (Graviton) — validated on staging first before testing/production
        # are flipped. The asset hash is architecture-aware (see
        # lambda_factory.build_backend_code) so the bundle is rebuilt for arm64
        # rather than reusing the prior x86_64 zip, which broke the #449 attempt.
        "lambda_architecture": "arm64",
        "api_rate_limit": 50,
        "api_burst_limit": 100,
        "github_repository": "https://github.com/SC0RED/sc0red-services",
        "amplify_branch": "development",
        # Branded MCP endpoint (mcp-custom-domain change). The certificate is
        # requested out-of-band via CLI and referenced by ARN: CloudFront only
        # accepts us-east-1 certs, and a CDK-managed DNS-validated cert would
        # pause the CI deploy waiting for the cross-account validation record
        # (DNS lives in the production account's Route 53; records are added
        # manually there, per the Amplify-domain precedent).
        "mcp_domain": "mcp.dev.services.sc0red.ai",
        "mcp_certificate_arn": (
            "arn:aws:acm:us-east-1:484719706337:certificate/"
            "b2a6308a-bb34-45e7-965c-b88f4689c969"
        ),
        # Shares account 484719706337 with development — still SES-sandboxed.
        "cognito_ses_email_sender": False,
    },
    "testing": {
        "removal_policy": cdk.RemovalPolicy.SNAPSHOT,
        "log_retention_days": 30,
        "enable_monitoring": True,
        "point_in_time_recovery": False,
        # arm64 (Graviton) — promoted from staging after staging was validated
        # healthy on arm64 (#451). The arch-aware asset hash + pinned bundle
        # platform make the flip safe; production stays x86_64 until testing bakes.
        "lambda_architecture": "arm64",
        "api_rate_limit": 50,
        "api_burst_limit": 100,
        "github_repository": "https://github.com/SC0RED/sc0red-services",
        "amplify_branch": "testing",
        # Branded MCP endpoint (mcp-custom-domain). Cert requested out-of-band in
        # the testing account, us-east-1 (CloudFront requires us-east-1 regardless
        # of the testing stack's region); validation + the CNAME -> CloudFront
        # record live in the production account's Route 53.
        "mcp_domain": "mcp.test.services.sc0red.ai",
        "mcp_certificate_arn": (
            "arn:aws:acm:us-east-1:205293249227:certificate/"
            "66937018-f060-4eb3-9202-36f9457e53f3"
        ),
        # Account 205293249227 has SES production access and a DKIM-verified
        # sc0red.com identity in us-east-2, so auth email sends as sc0red.
        "cognito_ses_email_sender": True,
    },
    "production": {
        "removal_policy": cdk.RemovalPolicy.RETAIN,
        "log_retention_days": 90,
        "enable_monitoring": True,
        "point_in_time_recovery": True,
        # arm64 (Graviton) — promoted after staging and testing both ran healthy
        # on arm64. The arch-aware asset hash + pinned bundle platform (#451) are
        # already live on production (dormant on x86), so this is just the flip.
        "lambda_architecture": "arm64",
        "api_rate_limit": 100,
        "api_burst_limit": 200,
        "github_repository": "https://github.com/SC0RED/sc0red-services",
        "amplify_branch": "production",
        # Branded MCP endpoint (mcp-custom-domain). Cert requested out-of-band in
        # the production account, us-east-1 (CloudFront requires us-east-1
        # regardless of the production stack's region); validation + the CNAME ->
        # CloudFront record live in the production account's Route 53.
        "mcp_domain": "mcp.services.sc0red.ai",
        "mcp_certificate_arn": (
            "arn:aws:acm:us-east-1:950743373172:certificate/"
            "5cb75da8-e14e-4b72-90ef-70ad0c843555"
        ),
        # Account 950743373172 has SES production access (case 178396220500234)
        # and a DKIM-verified sc0red.com identity in us-east-2. This is the fix
        # for SPE-2150 — the Cognito sender was being spam-filtered.
        "cognito_ses_email_sender": True,
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
