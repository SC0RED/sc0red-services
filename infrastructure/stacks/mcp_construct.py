"""CDK construct for the sc0red Services MCP (Model Context Protocol) server.

Creates:
- RSA signing key in Secrets Manager (for OAuth JWT tokens)
- Lambda function running the FastMCP ASGI app via uvicorn behind the AWS
  Lambda Web Adapter (LWA) — see design.md Decision 8
- Lambda Function URL for Streamable HTTP transport
- CfnOutput for the MCP server URL
- When ``mcp_domain`` is configured: a CloudFront distribution serving the
  branded hostname (cert by ARN) + CfnOutputs for the DNS CNAME target and
  the branded URL (see the mcp-custom-domain change)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import aws_cdk as cdk
from aws_cdk import CfnOutput, Duration
from aws_cdk import aws_certificatemanager as acm
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import aws_ssm as ssm
from aws_cdk import custom_resources as cr
from constructs import Construct

if TYPE_CHECKING:
    from aws_cdk import aws_dynamodb as dynamodb
    from aws_cdk import aws_sqs as sqs


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
        analysis_queue: sqs.Queue,
        frontend_domain: str = "",
        mcp_domain: str = "",
        mcp_certificate_arn: str = "",
    ) -> None:
        """Initialize MCP construct."""
        super().__init__(scope, construct_id)

        # Fail-fast at synth: the custom domain needs BOTH values (a domain
        # without its us-east-1 cert can't attach to CloudFront; a cert without
        # a domain is dead config).
        if bool(mcp_domain) != bool(mcp_certificate_arn):
            raise ValueError(
                "mcp_domain and mcp_certificate_arn must be configured together "
                f"(got domain={mcp_domain!r}, certificate_arn={mcp_certificate_arn!r})"
            )

        self._environment = environment

        self._frontend_domain = frontend_domain

        signing_key = self._create_signing_key()
        self._add_signing_key_generator(
            signing_key=signing_key,
            bundling=bundling,
            architecture=lambda_architecture,
        )
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
        # MCP write tools dispatch scan work to the analysis queue, exactly like
        # the API Lambda. (Step Functions wiring for multi-company confirms is
        # added by the stack post-construction — the batch coordinator doesn't
        # exist yet when this construct is built.)
        analysis_queue.grant_send_messages(mcp_lambda)
        mcp_lambda.add_environment("ANALYSIS_QUEUE_URL", analysis_queue.queue_url)

        function_url = mcp_lambda.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.NONE,
        )

        # Bug C fix — advertise the real Function URL as the OAuth issuer, via
        # SSM indirection to avoid the CloudFormation circular dependency that a
        # direct ``add_environment("MCP_ISSUER_URL", function_url.url)`` causes
        # (Lambda env → FunctionUrl → Lambda). Instead:
        #   • an SSM parameter holds the Function URL (param → FunctionUrl, one-way)
        #   • the Lambda's env carries only the static parameter NAME (a literal
        #     string — no reference to any resource, so no dependency back to the
        #     FunctionUrl)
        #   • the handler reads the parameter at cold start (see mcp_handler.py)
        # The IAM grant uses a CONSTRUCTED string ARN rather than
        # ``param.grant_read`` so the Lambda's execution role doesn't reference
        # the SSM parameter resource either — that reference would re-introduce
        # the cycle (role → param → FunctionUrl → Lambda).
        issuer_parameter_name = f"/sc0red-services/mcp/{self._environment}/issuer-url"
        ssm.StringParameter(
            self,
            "MCPIssuerUrlParameter",
            parameter_name=issuer_parameter_name,
            string_value=function_url.url,
            description=f"MCP OAuth issuer URL (Function URL) — {self._environment}",
        )
        mcp_lambda.add_environment("MCP_ISSUER_URL_SSM_PARAMETER", issuer_parameter_name)
        stack = cdk.Stack.of(self)
        mcp_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[
                    f"arn:aws:ssm:{stack.region}:{stack.account}:parameter{issuer_parameter_name}"
                ],
            )
        )

        if mcp_domain:
            self._add_custom_domain(
                mcp_lambda=mcp_lambda,
                function_url=function_url,
                domain=mcp_domain,
                certificate_arn=mcp_certificate_arn,
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

    @property
    def lambda_function(self) -> lambda_.Function:
        """The MCP server Lambda — for post-construction grants (Step Functions)."""
        return self._lambda

    def _add_custom_domain(
        self,
        *,
        mcp_lambda: lambda_.Function,
        function_url: lambda_.FunctionUrl,
        domain: str,
        certificate_arn: str,
    ) -> None:
        """Serve + advertise the MCP server on a branded hostname (mcp-custom-domain).

        A CloudFront distribution fronts the WHOLE Function URL — the OAuth and
        discovery endpoints live on the same origin as the ``/mcp`` transport, so
        every path must move together. Setting ``MCP_ISSUER_URL`` (a static
        string — no resource reference, so no Lambda↔FunctionUrl cycle) flips all
        advertised URLs (issuer, token endpoint, RFC 9728 ``resource``,
        ``WWW-Authenticate``) to the branded host; the SSM parameter remains as
        the fallback for environments without a domain.

        The certificate is imported by ARN (requested out-of-band via CLI):
        CloudFront only accepts us-east-1 certs, and a CDK-managed DNS-validated
        cert would pause the deploy waiting for the cross-account validation
        record (DNS lives in the production account's Route 53).
        """
        certificate = acm.Certificate.from_certificate_arn(
            self, "MCPDomainCertificate", certificate_arn
        )
        # The Function URL token is "https://<host>/" — take the host segment.
        function_url_host = cdk.Fn.select(2, cdk.Fn.split("/", function_url.url))
        distribution = cloudfront.Distribution(
            self,
            "MCPDistribution",
            comment=f"sc0red-services MCP — {self._environment}",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.HttpOrigin(function_url_host),
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                # Every request is dynamic + bearer-authenticated.
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                # Function URLs route by their own Host header — forwarding the
                # viewer Host would break the origin. This managed policy
                # forwards everything else (including Authorization).
                origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            domain_names=[domain],
            certificate=certificate,
        )
        mcp_lambda.add_environment("MCP_ISSUER_URL", f"https://{domain}")

        CfnOutput(
            cdk.Stack.of(self),
            "MCPCloudFrontDomain",
            value=distribution.distribution_domain_name,
            description=(
                f"CNAME target for {domain} (add in the production account's Route 53)"
            ),
        )
        CfnOutput(
            cdk.Stack.of(self),
            "MCPCustomDomainUrl",
            value=f"https://{domain}/mcp",
            description=f"Branded MCP endpoint — {self._environment}",
        )

    def _create_signing_key(self) -> secretsmanager.Secret:
        """Create the RSA signing-key secret for OAuth JWT tokens.

        Created with a placeholder body; the ``SigningKeyGenerator`` custom
        resource (see ``_add_signing_key_generator``) populates it with a real
        RSA keypair at deploy time (Bug X), so no manual ``put-secret-value`` is
        needed per environment.
        """
        return secretsmanager.Secret(
            self,
            "OAuthSigningKey",
            secret_name=f"sc0red-services-mcp-signing-key-{self._environment}",
            description="RSA keypair for signing MCP OAuth JWT tokens (auto-populated on deploy)",
            # NOTE: this generate_secret_string MUST stay byte-for-byte as
            # originally deployed. CloudFormation regenerates the secret VALUE on
            # ANY change to GenerateSecretString — which would wipe staging's
            # hand-populated key before the SigningKeyGenerator idempotency check
            # runs, invalidating live tokens. The "auto-populated" context lives
            # in `description` (metadata-only, safe to change).
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

    def _add_signing_key_generator(
        self,
        *,
        signing_key: secretsmanager.Secret,
        bundling: cdk.BundlingOptions,
        architecture: lambda_.Architecture,
    ) -> None:
        """Populate the signing-key secret with an RSA keypair at deploy time (Bug X).

        A custom-resource Lambda generates the keypair on first deploy and writes
        it into the secret, so each environment self-populates instead of needing
        a manual ``put-secret-value``. The handler is idempotent
        (``signing_key_provider.handle``): it no-ops when the secret already holds
        a keypair, so a hand-populated key (staging) is preserved and redeploys
        never rotate the key — rotation would invalidate every live access token.
        """
        generator_name = f"sc0red-services-mcp-signing-key-generator-{self._environment}"
        generator_logs = logs.LogGroup(
            self,
            "SigningKeyGeneratorLogs",
            log_group_name=f"/aws/lambda/{generator_name}",
            # Deploy-time-only Lambda — short retention is plenty; explicit so it
            # doesn't default to never-expire like the MCP Lambda's log group.
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )
        generator = lambda_.Function(
            self,
            "SigningKeyGenerator",
            function_name=generator_name,
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=architecture,
            handler="src.mcp.signing_key_provider.handle",
            # Reuses the MCP Lambda's backend bundle (cryptography + token_utils).
            # CDK dedups the identical asset, so this does not re-bundle.
            code=lambda_.Code.from_asset("../backend", bundling=bundling),
            timeout=Duration.seconds(60),
            memory_size=256,
            log_group=generator_logs,
        )
        signing_key.grant_read(generator)
        signing_key.grant_write(generator)

        provider = cr.Provider(self, "SigningKeyProvider", on_event_handler=generator)
        cdk.CustomResource(
            self,
            "SigningKeyPopulate",
            service_token=provider.service_token,
            properties={"SecretArn": signing_key.secret_arn},
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
        function_name = f"sc0red-services-mcp-{self._environment}"

        log_group = logs.LogGroup(
            self,
            "MCPLogs",
            log_group_name=f"/aws/lambda/{function_name}",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        region = cdk.Stack.of(self).region or os.environ.get("AWS_REGION", "us-east-1")

        # AWS Lambda Web Adapter (LWA) layer. LWA runs the FastMCP ASGI app as a
        # real uvicorn server inside the Lambda container, so the ASGI lifespan
        # runs once per cold start (fixing the Mangum run-once 502 — design.md
        # Decision 8). The layer name is architecture-specific.
        lwa_layer_name = (
            "LambdaAdapterLayerArm64"
            if architecture == lambda_.Architecture.ARM_64
            else "LambdaAdapterLayerX86"
        )
        lwa_layer = lambda_.LayerVersion.from_layer_version_arn(
            self,
            "LambdaWebAdapter",
            f"arn:aws:lambda:{region}:753240598075:layer:{lwa_layer_name}:28",
        )

        return lambda_.Function(
            self,
            "MCPHandler",
            function_name=function_name,
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=architecture,
            # LWA managed-runtime contract: the handler is the startup script
            # (``run_mcp.sh`` execs uvicorn), invoked because
            # ``AWS_LAMBDA_EXEC_WRAPPER`` points at LWA's ``/opt/bootstrap``.
            handler="run_mcp.sh",
            code=lambda_.Code.from_asset("../backend", bundling=bundling),
            layers=[lwa_layer],
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
                "CONSENT_BASE_URL": self._frontend_domain or "http://localhost:3000",
                # ── AWS Lambda Web Adapter wiring ────────────────────────────
                "AWS_LAMBDA_EXEC_WRAPPER": "/opt/bootstrap",
                "AWS_LWA_PORT": "8080",
                # The MCP endpoint mounts at /mcp (POST + auth), so point LWA's
                # readiness probe at the dedicated /health route instead.
                "AWS_LWA_READINESS_CHECK_PATH": "/health",
            },
        )
