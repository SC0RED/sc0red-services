"""AWS Amplify Hosting construct for Janus frontend.

Two-phase construct to resolve the circular dependency between Amplify and
API Gateway: Phase 1 creates the App (gives us the domain), Phase 2 creates
the Branch (needs the API URL).

Uses access_token (GitHub PAT) for repository access. The PAT is passed at
CDK deploy time via AMPLIFY_GITHUB_TOKEN env var.
"""

from __future__ import annotations

import json

import aws_cdk as cdk
from aws_cdk import CfnOutput
from aws_cdk import aws_amplify as amplify
from aws_cdk import aws_iam as iam
from constructs import Construct


class AmplifyConstruct(Construct):
    """Amplify Hosting app for the Next.js frontend."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        environment: str,
        github_token: str,
        repository: str,
        branch_name: str,
    ) -> None:
        super().__init__(scope, construct_id)

        self._environment = environment
        self._branch_name = branch_name

        role = self._create_service_role()

        self._app = amplify.CfnApp(
            self,
            "App",
            name=f"janus-frontend-{environment}",
            repository=repository,
            access_token=github_token,
            platform="WEB_COMPUTE",
            iam_service_role=role.role_arn,
            build_spec=self._build_spec(),
            environment_variables=[
                amplify.CfnApp.EnvironmentVariableProperty(
                    name="_CUSTOM_IMAGE",
                    value="amplify:al2023",
                ),
                amplify.CfnApp.EnvironmentVariableProperty(
                    name="AMPLIFY_MONOREPO_APP_ROOT",
                    value="frontend",
                ),
            ],
        )

        CfnOutput(
            cdk.Stack.of(self),
            "AmplifyAppId",
            value=self._app.attr_app_id,
            description="Amplify App ID",
        )

    @property
    def default_domain(self) -> str:
        """Amplify default domain (e.g. d1234abcdef.amplifyapp.com)."""
        return self._app.attr_default_domain

    @property
    def branch_url(self) -> str:
        """Full URL for the configured branch."""
        return f"https://{self._branch_name}.{self._app.attr_default_domain}"

    def create_branch(
        self,
        *,
        api_url: str,
        nextauth_secret: str,
        cognito_user_pool_id: str,
        cognito_client_id: str,
    ) -> None:
        """Phase 2: create the branch after API Gateway exists."""
        branch = amplify.CfnBranch(
            self,
            "Branch",
            app_id=self._app.attr_app_id,
            branch_name=self._branch_name,
            enable_auto_build=True,
            framework="Next.js - SSR",
            stage="PRODUCTION",
            environment_variables=[
                amplify.CfnBranch.EnvironmentVariableProperty(
                    name="BACKEND_URL",
                    value=api_url,
                ),
                amplify.CfnBranch.EnvironmentVariableProperty(
                    name="NEXTAUTH_SECRET",
                    value=nextauth_secret,
                ),
                amplify.CfnBranch.EnvironmentVariableProperty(
                    name="NEXTAUTH_URL",
                    value=self.branch_url,
                ),
                amplify.CfnBranch.EnvironmentVariableProperty(
                    name="NEXT_PUBLIC_COGNITO_USER_POOL_ID",
                    value=cognito_user_pool_id,
                ),
                amplify.CfnBranch.EnvironmentVariableProperty(
                    name="NEXT_PUBLIC_COGNITO_CLIENT_ID",
                    value=cognito_client_id,
                ),
            ],
        )

        branch.add_dependency(self._app)

        CfnOutput(
            cdk.Stack.of(self),
            "AmplifyBranchUrl",
            value=self.branch_url,
            description=f"Amplify frontend URL — {self._environment}",
        )

    # ── Private helpers ────────────────────────────────────────────────

    def _create_service_role(self) -> iam.Role:
        return iam.Role(
            self,
            "ServiceRole",
            assumed_by=iam.ServicePrincipal("amplify.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AdministratorAccess-Amplify"
                ),
            ],
        )

    @staticmethod
    def _build_spec() -> str:
        spec = {
            "version": 1,
            "applications": [
                {
                    "appRoot": "frontend",
                    "frontend": {
                        "phases": {
                            "preBuild": {
                                "commands": ["npm ci --legacy-peer-deps"],
                            },
                            "build": {
                                "commands": [
                                    "env | grep -E '^(BACKEND_URL|NEXT_PUBLIC_)' >> .env.production",
                                    "npm run build",
                                ],
                            },
                        },
                        "artifacts": {
                            "baseDirectory": ".next",
                            "files": ["**/*"],
                        },
                        "cache": {
                            "paths": [
                                "node_modules/**/*",
                                ".next/cache/**/*",
                            ],
                        },
                    },
                }
            ],
        }
        return json.dumps(spec)
