"""Cognito User Pool construct for sc0red Services authentication.

Creates a User Pool with:
- Email-based sign-in with auto-verification
- Custom attributes for multi-tenancy (org_id, role, legacy_user_id)
- Password policy (8+ chars, upper+lower+digits)
- App Client configured for SPA (no secret, USER_PASSWORD_AUTH flow)
- Custom Message Lambda for branded invitation emails
"""

import aws_cdk as cdk
from aws_cdk import CfnOutput, Duration, RemovalPolicy
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from constructs import Construct


class CognitoConstruct(Construct):
    """Cognito User Pool and App Client for sc0red Services authentication."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        environment: str,
        removal_policy: RemovalPolicy,
        bundling: cdk.BundlingOptions,
        lambda_architecture: lambda_.Architecture,
        frontend_domain: str = "",
    ) -> None:
        super().__init__(scope, construct_id)

        self._environment = environment

        custom_message_lambda = self._create_custom_message_lambda(
            bundling, lambda_architecture, removal_policy, frontend_domain
        )
        self._user_pool = self._create_user_pool(
            removal_policy, custom_message_lambda
        )
        self._app_client = self._create_app_client()
        self._create_outputs()

    @property
    def user_pool(self) -> cognito.UserPool:
        """Return the Cognito User Pool."""
        return self._user_pool

    @property
    def user_pool_id(self) -> str:
        """Return the User Pool ID."""
        return self._user_pool.user_pool_id

    @property
    def app_client_id(self) -> str:
        """Return the App Client ID."""
        return self._app_client.user_pool_client_id

    def _create_custom_message_lambda(
        self,
        bundling: cdk.BundlingOptions,
        architecture: lambda_.Architecture,
        removal_policy: RemovalPolicy,
        frontend_domain: str,
    ) -> lambda_.Function:
        """Create the Custom Message Lambda for branded invitation emails."""
        log_group = logs.LogGroup(
            self,
            "CustomMessageLambdaLogs",
            log_group_name=f"/aws/lambda/sc0red-services-cognito-custom-message-{self._environment}",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=removal_policy,
        )

        return lambda_.Function(
            self,
            "CustomMessageLambda",
            function_name=f"sc0red-services-cognito-custom-message-{self._environment}",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=architecture,
            handler="src.handlers.cognito_custom_message.handle_custom_message",
            code=lambda_.Code.from_asset("../backend", bundling=bundling),
            timeout=Duration.seconds(5),
            memory_size=128,
            log_group=log_group,
            environment={
                "FRONTEND_DOMAIN": frontend_domain,
            },
        )

    def _create_user_pool(
        self,
        removal_policy: RemovalPolicy,
        custom_message_lambda: lambda_.Function,
    ) -> cognito.UserPool:
        """Create the Cognito User Pool with custom attributes."""
        pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name=f"sc0red-services-users-{self._environment}",
            # Sign-in configuration
            sign_in_aliases=cognito.SignInAliases(email=True),
            self_sign_up_enabled=True,
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            # Standard attributes
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True),
                fullname=cognito.StandardAttribute(required=False, mutable=True),
            ),
            # Custom attributes for multi-tenancy
            custom_attributes={
                "org_id": cognito.StringAttribute(
                    mutable=True,
                    max_len=36,
                ),
                "role": cognito.StringAttribute(
                    mutable=True,
                    max_len=20,
                ),
                "legacy_user_id": cognito.StringAttribute(
                    mutable=False,
                    max_len=36,
                ),
            },
            # Password policy (matches current bcrypt requirements)
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False,
                temp_password_validity=Duration.days(7),
            ),
            # Account recovery
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            # MFA — off for now, designed for future TOTP enablement
            mfa=cognito.Mfa.OFF,
            # Email configuration — use Cognito default (SES for production later)
            user_verification=cognito.UserVerificationConfig(
                email_subject="sc0red Services — Verify your email",
                email_body="Your sc0red Services verification code is {####}",
                email_style=cognito.VerificationEmailStyle.CODE,
            ),
            # Invitation email is handled by the CustomMessage Lambda trigger
            # (cognito_custom_message.py) for branded HTML emails.
            removal_policy=removal_policy,
            lambda_triggers=cognito.UserPoolTriggers(
                custom_message=custom_message_lambda,
            ),
        )

        return pool

    def _create_app_client(self) -> cognito.UserPoolClient:
        """Create the App Client for the frontend SPA."""
        return self._user_pool.add_client(
            "AppClient",
            user_pool_client_name=f"sc0red-services-web-{self._environment}",
            generate_secret=False,
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
                custom=True,
            ),
            id_token_validity=Duration.hours(8),
            access_token_validity=Duration.hours(8),
            refresh_token_validity=Duration.days(30),
            prevent_user_existence_errors=True,
            read_attributes=cognito.ClientAttributes()
            .with_standard_attributes(
                email=True,
                fullname=True,
            )
            .with_custom_attributes("org_id", "role", "legacy_user_id"),
            write_attributes=cognito.ClientAttributes()
            .with_standard_attributes(
                email=True,
                fullname=True,
            )
            .with_custom_attributes("org_id", "role"),
        )

    def grant_admin_actions(self, handler: lambda_.Function) -> None:
        """Grant a Lambda function permission to call Cognito admin APIs."""
        self._user_pool.grant(
            handler,
            "cognito-idp:AdminCreateUser",
            "cognito-idp:AdminDeleteUser",
            "cognito-idp:AdminSetUserPassword",
            "cognito-idp:AdminUpdateUserAttributes",
            "cognito-idp:AdminGetUser",
        )

    def _create_outputs(self) -> None:
        """Export User Pool and Client IDs as CloudFormation outputs."""
        CfnOutput(
            self,
            "UserPoolId",
            value=self._user_pool.user_pool_id,
            description="Cognito User Pool ID",
        )
        CfnOutput(
            self,
            "UserPoolClientId",
            value=self._app_client.user_pool_client_id,
            description="Cognito App Client ID",
        )
        CfnOutput(
            self,
            "UserPoolProviderUrl",
            value=self._user_pool.user_pool_provider_url,
            description="Cognito User Pool Provider URL (issuer)",
        )
