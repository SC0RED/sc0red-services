"""CDK construct for the Janus MCP (Model Context Protocol) server.

Creates:
- RSA signing key in Secrets Manager (for OAuth JWT tokens)
- Lambda function running the FastMCP server via Mangum
- Lambda Function URL for Streamable HTTP transport
- CfnOutput for the MCP server URL
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import aws_cdk as cdk
from aws_cdk import CfnOutput, Duration
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

if TYPE_CHECKING:
    from aws_cdk import aws_dynamodb as dynamodb


class MCPConstruct(Construct):
    """MCP server infrastructure: Lambda + Function URL + OAuth signing key."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        environment: str,
        bundling: cdk.BundlingOptions,
        lambda_architecture: lambda_.Architecture,
        table: dynamodb.Table,
        api_url: str,
        cognito_user_pool_id: str,
        cognito_client_id: str,
        frontend_domain: str = "",
    ) -> None:
        """Initialize MCP construct."""
        super().__init__(scope, construct_id)

        self._environment = environment

        self._frontend_domain = frontend_domain

        signing_key = self._create_signing_key()
        mcp_lambda = self._create_lambda(
            bundling=bundling,
            architecture=lambda_architecture,
            table=table,
            api_url=api_url,
            signing_key=signing_key,
            cognito_user_pool_id=cognito_user_pool_id,
            cognito_client_id=cognito_client_id,
        )

        table.grant_read_write_data(mcp_lambda)
        signing_key.grant_read(mcp_lambda)

        function_url = mcp_lambda.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.NONE,
        )

        # Wire the Function URL back as issuer so OAuth metadata is correct
        mcp_lambda.add_environment("MCP_ISSUER_URL", function_url.url)
        mcp_lambda.add_environment(
            "CONSENT_BASE_URL", frontend_domain if frontend_domain else f"http://localhost:3000"
        )

        self._function_url = function_url.url
        self._lambda = mcp_lambda

        CfnOutput(
            scope,
            "MCPServerUrl",
            value=function_url.url,
            description=f"MCP Server URL — {environment}",
        )

    @property
    def function_url(self) -> str:
        """The Lambda Function URL for the MCP server."""
        return self._function_url

    def _create_signing_key(self) -> secretsmanager.Secret:
        """Create or reference the RSA signing key for OAuth JWT tokens."""
        return secretsmanager.Secret(
            self,
            "OAuthSigningKey",
            secret_name=f"janus-mcp-signing-key-{self._environment}",
            description="RSA private key for signing MCP OAuth JWT tokens",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                generate_string_key="placeholder",
                secret_string_template='{"note": "Replace with RSA private key via CLI"}',
            ),
            removal_policy=(
                cdk.RemovalPolicy.DESTROY
                if self._environment == "development"
                else cdk.RemovalPolicy.RETAIN
            ),
        )

    def _create_lambda(
        self,
        *,
        bundling: cdk.BundlingOptions,
        architecture: lambda_.Architecture,
        table: dynamodb.Table,
        api_url: str,
        signing_key: secretsmanager.Secret,
        cognito_user_pool_id: str,
        cognito_client_id: str,
    ) -> lambda_.Function:
        """Create the MCP server Lambda function."""
        function_name = f"janus-mcp-{self._environment}"

        log_group = logs.LogGroup(
            self,
            "MCPLogs",
            log_group_name=f"/aws/lambda/{function_name}",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        region = cdk.Stack.of(self).region or os.environ.get("AWS_REGION", "us-east-1")

        return lambda_.Function(
            self,
            "MCPHandler",
            function_name=function_name,
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=architecture,
            handler="src.mcp.mcp_handler.handle_event",
            code=lambda_.Code.from_asset("../backend", bundling=bundling),
            timeout=Duration.seconds(900),
            memory_size=512,
            log_group=log_group,
            environment={
                "DYNAMODB_TABLE": table.table_name,
                "API_URL": api_url,
                "OAUTH_SIGNING_KEY_SECRET_ARN": signing_key.secret_arn,
                "COGNITO_USER_POOL_ID": cognito_user_pool_id,
                "COGNITO_CLIENT_ID": cognito_client_id,
                "COGNITO_REGION": region,
                "STAGE": self._environment,
            },
        )
