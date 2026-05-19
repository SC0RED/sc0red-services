"""AWS Amplify Hosting construct for sc0red Services frontend.

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
            name=f"sc0red-services-frontend-{environment}",
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
        pdf_token_secret: str,
        internal_api_key: str,
    ) -> None:
        """Phase 2: create the branch after API Gateway exists.

        `pdf_token_secret` and `internal_api_key` are server-side env vars
        consumed by the Next.js Lambda runtime (the `/api/export/pdf/[id]`
        token-mint flow and the `/print/[id]` server component, respectively).
        Both MUST agree with the same env vars on the API Lambda — they
        come from the same Secrets Manager secret in `sc0red_services_stack.py`.

        `FRONTEND_BASE_URL` is the public origin the headless Chromium
        Lambda navigates to (`${BASE}/print/{id}?t=...`). On Amplify SSR
        the Next.js process binds to `localhost:3000` internally, so
        `req.nextUrl.origin` returns the wrong URL — we have to set this
        explicitly. Value is the Amplify-default branch URL (Amplify
        routes the custom domain `dev.sc0red-services.sc0red.com` to the same
        SSR Lambda, so headless navigation against either works).
        """
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
                amplify.CfnBranch.EnvironmentVariableProperty(
                    name="PDF_TOKEN_SECRET",
                    value=pdf_token_secret,
                ),
                amplify.CfnBranch.EnvironmentVariableProperty(
                    name="INTERNAL_API_KEY",
                    value=internal_api_key,
                ),
                amplify.CfnBranch.EnvironmentVariableProperty(
                    name="FRONTEND_BASE_URL",
                    value=self.branch_url,
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
                                # Amplify branch env vars are NOT exposed to
                                # the Next.js SSR Lambda runtime by default —
                                # they're only available at build time. The
                                # workaround is to write them to
                                # `.env.production` during the build so Next.js
                                # bundles them into the server runtime. The
                                # grep filter MUST cover every server-side env
                                # var the SSR runtime reads. Entries:
                                #   - PDF_TOKEN_SECRET — HMAC signing for the
                                #     /api/export/pdf URL token
                                #   - INTERNAL_API_KEY — auth for the print
                                #     route's call to /api/internal/analysis
                                #   - FRONTEND_BASE_URL — public origin the
                                #     PDF render Lambda navigates to (without
                                #     this, `req.nextUrl.origin` falls to
                                #     `localhost:3000` on Amplify SSR)
                                "commands": [
                                    "env | grep -E '^(NEXTAUTH_|BACKEND_URL|NEXT_PUBLIC_|PDF_TOKEN_SECRET|INTERNAL_API_KEY|FRONTEND_BASE_URL)' >> .env.production",
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
