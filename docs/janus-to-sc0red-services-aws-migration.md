# janus → sc0red-services AWS Migration Plan

**Status:** Drafted 2026-05-19, targeting Thursday 2026-05-21 cutover.
**Owner:** Engineering Team (Production Approver gates prod stage).

The repo and code identifiers have already been renamed (see commit `72e294b refactor: rename Janus to sc0red Services`). This document covers the AWS-side migration: standing up new `sc0red-services-{env}` resources, moving data over from the existing `janus-{env}` resources, and cutting traffic over from `janus.sc0red.ai` to `services.sc0red.ai`.

---

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Approach | Fresh stack, parallel run, one-shot cutover | Cleaner than rename-in-place (CloudFormation can't rename most resource types). Old stack stays warm until verified. |
| Data migration timing | Offline window (~15 min) on cutover day | DynamoDB writes are infrequent enough that a brief read-only window beats dual-write complexity for a 2-day project. |
| Cognito users | Re-create via invitation flow | LowCount (`<50` users across envs); cleaner than User Pool import. Users get a "re-verify your email" notice. |
| S3 documents | Copy via `s3 sync` | Static reports are immutable; one-shot copy is safe. |
| DNS | Add `services.sc0red.ai` first, keep `janus.sc0red.ai` as a permanent 301 → services for 30 days | Email links and bookmarks won't break overnight. |
| Old resources | Retain for 14 days post-cutover, then teardown | Recovery window if migration surfaces issues. |

---

## Resources being replaced

Mapping from old (current) to new (post-rename CDK output) names.

| Resource type | Old name | New name |
|---|---|---|
| CloudFormation Stack | `Janus-{env}` | `Sc0redServices-{env}` |
| DynamoDB Table | `janus-{env}` | `sc0red-services-{env}` |
| Lambda — API | `janus-api-{env}` | `sc0red-services-api-{env}` |
| Lambda — Worker | `janus-worker-{env}` | `sc0red-services-worker-{env}` |
| Lambda — Cognito custom message | `janus-cognito-custom-message-{env}` | `sc0red-services-cognito-custom-message-{env}` |
| API Gateway | `janus-api-{env}` | `sc0red-services-api-{env}` |
| SQS Queue | `janus-analysis-queue-{env}` | `sc0red-services-analysis-queue-{env}` |
| SQS DLQ | `janus-analysis-dlq-{env}` | `sc0red-services-analysis-dlq-{env}` |
| S3 Bucket | `janus-documents-{env}` | `sc0red-services-documents-{env}` |
| Cognito User Pool | `janus-users-{env}` | `sc0red-services-users-{env}` |
| Cognito App Client | `janus-web-{env}` | `sc0red-services-web-{env}` |
| Amplify App | `janus-frontend-{env}` | `sc0red-services-frontend-{env}` |
| AppSync API | `janus-progress-{env}` | `sc0red-services-progress-{env}` |
| CloudWatch Log Group | `/aws/lambda/janus-*` | `/aws/lambda/sc0red-services-*` |
| Custom domain | `janus.sc0red.ai` | `services.sc0red.ai` |

---

## Migration sequence

### Phase 0 — Pre-flight (before cutover day)

Run in each environment in this order: `development` → `testing` → `production`. Don't proceed to next env until previous is verified end-to-end.

1. **Stand up the new CDK stack alongside the old one.** Both `Janus-{env}` and `Sc0redServices-{env}` exist in parallel. The new stack creates empty `sc0red-services-*` resources. No traffic is routed to it yet.
   ```bash
   cd infrastructure
   CDK_ENVIRONMENT={env} AWS_PROFILE=sc0red-{env} uv run cdk deploy Sc0redServices-{env}
   ```
2. **Smoke-test the new stack in isolation.** Hit the new API Gateway URL directly with a test JWT, write a synthetic DynamoDB record, run a single-company analysis through the new worker Lambda, verify the document lands in the new S3 bucket. Use `scripts/e2e-test.sh` pointed at the new API URL.
3. **Provision the DNS record `services.sc0red.ai`** in Route53 pointing at the new Amplify branch. TTL 60s to keep cutover nimble.

### Phase 1 — Cutover day (Thursday 2026-05-21)

**Coordinated maintenance window. Estimated time: 30 min including verification.**

1. **Communicate downtime** to the small user base (Slack #services-launch + status banner on `janus.sc0red.ai`).
2. **Stop the old worker Lambda from picking up new SQS messages.** Set `janus-worker-{env}` reserved concurrency to 0. Drain the old `janus-analysis-queue-{env}` (wait for `ApproximateNumberOfMessagesNotVisible` to reach 0). This makes the system read-only.
3. **Snapshot the old DynamoDB table.** `aws dynamodb create-backup --table-name janus-{env} --backup-name pre-migration-{timestamp}`.
4. **Copy DynamoDB data** from `janus-{env}` to `sc0red-services-{env}`:
   - Use AWS Data Pipeline OR a one-shot Python script that `Scan`s the source table with `Limit=25` pagination and `BatchWriteItem`s into the target. ~`O(N)` rows, batched 25 at a time, should run under 5 min for the current row count.
   - Verify item count: `aws dynamodb describe-table --table-name {old,new}` and compare `ItemCount` (note: ItemCount is updated every ~6h, so also do `aws dynamodb scan --select COUNT` on both).
5. **Copy S3 documents:** `aws s3 sync s3://janus-documents-{env}/ s3://sc0red-services-documents-{env}/`.
6. **Migrate Cognito users:**
   - Export users from `janus-users-{env}`: `aws cognito-idp list-users --user-pool-id {old}` → CSV.
   - For each user, call `AdminCreateUser` on `sc0red-services-users-{env}` with `MessageAction=SUPPRESS` (don't email yet).
   - Send a custom "your sc0red Services account is ready, please reset your password" email via the new pool's invitation flow.
   - Anyone mid-session in the old app will be logged out (different JWT issuer, intentional).
7. **Flip DNS:** Update Amplify domain association so `services.sc0red.ai` points at `sc0red-services-frontend-{env}` Amplify branch. Add a permanent 301 redirect from `janus.sc0red.ai/*` → `services.sc0red.ai/*` at the CloudFront layer.
8. **Run the production smoke suite** against `services.sc0red.ai`: sign up, run an analysis, view the report, sign out.

### Phase 2 — Verification (cutover day + 24 hours)

- Watch CloudWatch for any 5xx on the new API Gateway.
- Check that DLQ depth on the new SQS DLQ stays at 0.
- Spot-check 5 random users — confirm their password-reset emails arrived and they can log in.
- Run analysis history queries to verify migrated DynamoDB records are reachable from the new app.

### Phase 3 — Cleanup (cutover + 14 days)

- Tear down the old CDK stack: `cdk destroy Janus-{env}`.
- Manually delete retained resources: old DynamoDB table (after final snapshot), old S3 bucket (after lifecycle policy purge), old Cognito User Pool, old Amplify app.
- Remove the 301 redirect at CloudFront once analytics show negligible traffic on `janus.sc0red.ai`.

---

## Rollback

If Phase 1 verification fails before the DNS flip in step 7, roll back by reversing only what was done: restore reserved concurrency on the old worker, point users back at `janus.sc0red.ai`. No data is lost — the old table is untouched.

If failure surfaces *after* DNS flip:
- Re-flip DNS back to old Amplify branch (the old stack is still running).
- Any DynamoDB writes that landed in the new table during the window need to be reconciled back to the old table — write a one-shot Python script using the same scan/batch-write approach in reverse, scoped to records with `created_at >= cutover_timestamp`.
- Affected users may need to log in again on the old domain.

---

## Open questions to confirm before Phase 1

1. **User count and notification copy.** How many users are in each env's Cognito pool? Do we want a 24h heads-up email or just the password-reset prompt? (Recommend: 24h heads-up to PE-firm primary contacts only.)
2. **Email branding for password-reset.** The new Cognito custom-message Lambda will use the renamed templates from `backend/src/handlers/templates/invitation_email.html` (already updated to say "sc0red Services"). Final visual review needed before sending mass email.
3. **CloudFront / 301 setup.** Is there an existing CloudFront distribution in front of `janus.sc0red.ai`, or does Amplify own the cert end-to-end? Determines where the 301 redirect rule lives.
4. **`sc0red-dev` / `sc0red-test` / `sc0red-prod` IAM permissions.** Confirm the role used by GitHub Actions has CreateUser / SetUserPassword permissions on the new Cognito pool.

---

## Estimated effort

| Phase | Time | Risk |
|---|---|---|
| Phase 0 (per env) | 30 min deploy + 30 min smoke | Low |
| Phase 1 (cutover day, per env) | 30 min | Medium — coordination & DNS propagation |
| Phase 2 (verify) | rolling 24h | Low |
| Phase 3 (cleanup) | 30 min | Low — purely destructive |

Total wall-clock for `development` → `testing` → `production`: ~3 hours of active work plus the 24h verification dwell between envs.
