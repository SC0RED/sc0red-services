# janus → sc0red-services AWS Migration Plan

**Status:** Drafted 2026-05-19. Customer-facing rebrand already live at https://services.sc0red.ai/ via a custom-domain bolt-on against the existing `janus-frontend-staging` Amplify app. The remaining work is migrating the underlying AWS resources to the renamed CDK definitions.

**Owner:** Engineering Team.

---

## Reality check (verified 2026-05-19)

The earlier draft of this plan assumed dev / testing / production environments and a phased rollout. **Only one environment is actually deployed**:

| Fact | Value |
|---|---|
| Deployed environments | `staging` only (no `development`, no `testing`, no `production` CFN stacks exist) |
| AWS account / region | `sc0red-dev` (484719706337), `us-east-1` |
| CFN stack | `Janus-staging` |
| DynamoDB table | `janus-staging`: **1,432 items, 4.7 MB** |
| Cognito pool | `janus-users-staging` (`us-east-1_QVnt9HTwO`): **2 users** — vedratna.velani@sc0red.com (CONFIRMED), zack.walmer@sc0red.com (FORCE_CHANGE_PASSWORD) |
| Amplify app | `janus-frontend-staging` (`d3s20952i7opqs`), branch `development` |
| Current API | `https://2r4vvvgech.execute-api.us-east-1.amazonaws.com/staging/` |
| Current frontend URLs | `https://development.d3s20952i7opqs.amplifyapp.com` and `https://services.sc0red.ai/` (CNAME added 2026-05-19) |
| Custom domain status | `services.sc0red.ai` AVAILABLE on Amplify, cert validated via cross-account DNS in `sc0red-prod` Route53 |
| GHA deploy role | `GitHubActionsDeployRole` (484719706337) — `AdministratorAccess`. Trust: `repo:SC0RED/*` wildcard, survives repo rename. |
| Old domain | `janus.sc0red.ai` was NEVER configured — no DNS record exists. No 301 redirect needed. |

**Implication:** The migration is much smaller than the dev → testing → production cadence originally drafted. A single coordinated maintenance window against staging completes the entire rollout.

---

## Resource mapping (Janus-staging → Sc0redServices-staging)

| Resource | Old | New |
|---|---|---|
| CFN Stack | `Janus-staging` | `Sc0redServices-staging` |
| DynamoDB | `janus-staging` | `sc0red-services-staging` |
| Lambda — API | `janus-api-staging` | `sc0red-services-api-staging` |
| Lambda — Worker | `janus-worker-staging` | `sc0red-services-worker-staging` |
| Lambda — Cognito custom message | `janus-cognito-custom-message-staging` | `sc0red-services-cognito-custom-message-staging` |
| Lambda — PDF render | `janus-pdf-render-staging` | `sc0red-services-pdf-render-staging` |
| Lambda — Strategy map worker | `janus-strategy-map-worker-staging` | `sc0red-services-strategy-map-worker-staging` |
| Lambda — MCP | `janus-mcp-staging` | `sc0red-services-mcp-staging` |
| API Gateway | `janus-api-staging` | `sc0red-services-api-staging` |
| SQS Queue | `janus-analysis-queue-staging` | `sc0red-services-analysis-queue-staging` |
| SQS DLQ | `janus-analysis-dlq-staging` | `sc0red-services-analysis-dlq-staging` |
| S3 Bucket | `janus-documents-staging` | `sc0red-services-documents-staging` |
| Cognito Pool | `janus-users-staging` | `sc0red-services-users-staging` |
| Cognito Client | `janus-web-staging` | `sc0red-services-web-staging` |
| Amplify App | `janus-frontend-staging` | `sc0red-services-frontend-staging` |
| AppSync | `janus-progress-staging` | `sc0red-services-progress-staging` |
| Secret | `janus-mcp-signing-key-staging` | `sc0red-services-mcp-signing-key-staging` |

---

## Cutover sequence

Estimated wall-clock: **~30 min including verification.** No team-wide downtime since the only users are the migration's own coordinators.

### Phase 0 — Pre-flight (any time before cutover)

1. **Notify the 2 users** (Vedratna + Zack) on Slack/email: "services.sc0red.ai is being rebuilt against new AWS infrastructure between {start} and {end}. You'll get a password-reset email from Cognito under the new pool — re-set and continue."
2. **Snapshot DynamoDB**: `aws dynamodb create-backup --table-name janus-staging --backup-name pre-rename-$(date +%s) --profile sc0red-dev`.
3. **Dump Cognito users** for re-creation:
   ```bash
   aws --profile sc0red-dev cognito-idp list-users --user-pool-id us-east-1_QVnt9HTwO \
     --query 'Users[].{u:Username,email:Attributes[?Name==`email`].Value|[0],attrs:Attributes}' \
     --output json > /tmp/cognito-users.json
   ```

### Phase 1 — Cutover

1. **Deploy the renamed CDK stack alongside the old one.** The new stack creates fresh `sc0red-services-*` resources. The old `Janus-staging` stack remains untouched.
   ```bash
   cd infrastructure
   CDK_ENVIRONMENT=staging \
   AMPLIFY_GITHUB_TOKEN=$(gh auth token) \
   NEXTAUTH_SECRET=$(openssl rand -base64 32) \
   AWS_PROFILE=sc0red-dev \
   uv run cdk deploy Sc0redServices-staging
   ```
   (~5–10 min on first deploy due to Lambda Docker bundling.)

2. **Stop the old worker from accepting new SQS messages.**
   ```bash
   aws --profile sc0red-dev lambda put-function-concurrency \
     --function-name janus-worker-staging --reserved-concurrent-executions 0
   ```
   Drain the old queue (wait until `ApproximateNumberOfMessages` and `ApproximateNumberOfMessagesNotVisible` both hit 0).

3. **Copy DynamoDB items** (1,432 items, runs in seconds):
   ```bash
   python3 scripts/migrate_dynamodb.py \
     --src-table janus-staging \
     --dst-table sc0red-services-staging \
     --profile sc0red-dev
   ```
   *(Script to be written — straight `Scan` with `Limit=25` + `BatchWriteItem` loop. ~50 lines.)* Verify: `aws dynamodb scan --select COUNT` on both tables should match.

4. **Copy S3 documents**:
   ```bash
   aws --profile sc0red-dev s3 sync \
     s3://janus-documents-staging/ s3://sc0red-services-documents-staging/
   ```

5. **Re-create the 2 Cognito users in the new pool.** Pull the new pool ID from CFN outputs, then:
   ```bash
   for email in vedratna.velani@sc0red.com zack.walmer@sc0red.com; do
     aws --profile sc0red-dev cognito-idp admin-create-user \
       --user-pool-id <NEW_POOL_ID> \
       --username "$email" \
       --user-attributes Name=email,Value="$email" Name=email_verified,Value=true \
       --desired-delivery-mediums EMAIL
   done
   ```
   Cognito sends each user a "your sc0red Services account is ready" email using the renamed custom-message Lambda template.

6. **Re-point `services.sc0red.ai` at the new Amplify app.** The new CDK stack creates `sc0red-services-frontend-staging` Amplify app with its own `*.amplifyapp.com` URL. Move the custom domain:
   - Remove the domain association from `janus-frontend-staging`: `aws amplify delete-domain-association --app-id d3s20952i7opqs --domain-name services.sc0red.ai`
   - Add it to the new app: `aws amplify create-domain-association --app-id <NEW_APP_ID> --domain-name services.sc0red.ai --sub-domain-settings prefix=,branchName=development`
   - Update the Route53 CNAME in `sc0red-prod` (zone `Z09084993URU8UB4L1L26`) to point at the new app's CloudFront target.
   - Cert re-validation takes ~5 min.

7. **Smoke test** at `services.sc0red.ai`: log in as one of the migrated users, run a test analysis, verify previous reports are visible.

### Phase 2 — Verification (24h dwell)

- Watch CloudWatch for any 5xx on the new API Gateway.
- Confirm DLQ depth on the new SQS DLQ stays at 0.
- Verify analysis history and document references resolve correctly from the new DynamoDB.

### Phase 3 — Cleanup (14 days post-cutover)

```bash
AWS_PROFILE=sc0red-dev uv run cdk destroy Janus-staging
```

Then manually delete:
- DynamoDB table `janus-staging` (RemovalPolicy=SNAPSHOT means CFN takes a final snapshot)
- S3 bucket `janus-documents-staging` (if not auto-deleted)
- Cognito User Pool `janus-users-staging`
- Any orphaned log groups under `/aws/lambda/janus-*`

---

## Rollback

The old `Janus-staging` stack is untouched throughout Phase 1. If verification fails:

- Re-point `services.sc0red.ai` back at the old Amplify branch (one Route53 record change + one Amplify domain association swap, ~5 min including DNS propagation).
- Restore old worker concurrency: `aws lambda put-function-concurrency --function-name janus-worker-staging --reserved-concurrent-executions <orig>` (or `delete-function-concurrency` to remove the limit).
- Any new items written to `sc0red-services-staging` during the window can be reconciled later via the same script run in reverse, scoped by `created_at >= cutover_timestamp`.

No data is at risk in the rollback scenario because the old stack stays warm.

---

## Open items (small, confirm before firing Phase 1)

- **Write the DynamoDB migration script** — `scripts/migrate_dynamodb.py`. 50ish lines, no surprises. Should accept `--dry-run` and `--limit` for testing.
- **Confirm the new Amplify app picks up the right Next.js build.** The repo rename broke the existing app's webhook; the new app needs the same fix during initial deploy (or in the Amplify console post-deploy).
- **Decide cutover timing.** Original target was Thursday 2026-05-21 but the rebrand is already live at services.sc0red.ai pointing at old infrastructure; the AWS-side migration could happen any time without external customer impact.
