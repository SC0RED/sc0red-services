# janus → sc0red-services Migration — TESTING environment

**Status:** ✅ Completed 2026-06-03. `https://test.services.sc0red.ai` live, login + migrated data verified.

**Companion docs:**
- `docs/janus-to-sc0red-services-aws-migration.md` — the original staging/development runbook this is modelled on.
- `docs/cognito-migration-plan.md` — background on the Cognito auth model (SDK direct-auth, custom attrs).

This document records exactly what was run for the **testing** environment, so it doubles as the proven template for **production** (see the production-prep section at the end).

---

## Key environment facts (testing differs from dev/staging)

| Fact | Development / staging | **Testing** |
|---|---|---|
| AWS region | `us-east-1` | **`us-east-2`** |
| CFN stack | `Sc0redServices-staging` | `Sc0redServices-testing` |
| Git branch (Amplify) | `development` | `testing` |
| Custom domain | `dev.services.sc0red.ai` | `test.services.sc0red.ai` |
| Amplify app (new) | `d1nl9cuus9o0d0` | `d2ea1ehyg2tsuh` (`sc0red-services-frontend-testing`) |
| Amplify app (old janus) | — | `d88lh5h7xvpuh` (`janus-frontend-testing`, parked on `test.janus.sc0red.com`) |
| DynamoDB (old → new) | `janus-staging` → `sc0red-services-staging` | `janus-testing` → `sc0red-services-testing` |
| Cognito pool (old → new) | — | `janus-users-testing` (`us-east-2_dzJMNAORt`) → `sc0red-services-users-testing` (`us-east-2_ISxHArxbP`) |
| Documents bucket (old → new) | — | `janus-testing-documentsbucket9ec9deb9-xa6jnangvxs5` → `sc0redservices-testing-documentsbucket9ec9deb9-bcdq2e9fprk5` |

**Cross-account topology (3 separate AWS accounts):**
- **Testing account** (us-east-2) — owns the new stack, DynamoDB, Cognito, Amplify app.
- **Development account** (us-east-1) — owns the dev/staging stack. Used here only as the *reference* for "what correct config looks like."
- **Production account** — owns the `sc0red.ai` Route53 zone (`Z09084993URU8UB4L1L26`). All DNS records for `*.services.sc0red.ai` are created here.

**`AWS_REGION` gotcha:** every command below targets `us-east-2`. The helper scripts (`repair_cognito_attrs.py`) read region from the `AWS_REGION` env var and **default to `us-east-1`** — always `export AWS_REGION=us-east-2` first or they silently hit the wrong region and report "not found."

---

## Pre-flight verification (read-only)

Confirm the starting state before mutating anything:

```bash
export AWS_REGION=us-east-2

# New DynamoDB table empty, old table has the data:
aws dynamodb scan --table-name janus-testing --select COUNT --region us-east-2 --query 'Count' --output text          # → sums to 2070
aws dynamodb scan --table-name sc0red-services-testing --select COUNT --region us-east-2 --query 'Count' --output text  # → 0

# Old pool has the real users, new pool is empty:
aws cognito-idp list-users --user-pool-id us-east-2_dzJMNAORt --region us-east-2 \
  --query 'Users[].{email:Attributes[?Name==`email`].Value|[0],status:UserStatus}' --output table
```

(DynamoDB `--select COUNT` paginates at 1 MB — the output is one Count per page; **sum them**. Testing had 8 pages summing to 2070.)

---

## Step 1 — DynamoDB copy (2070 items)

The migration script requires a named `--profile`. If you're on exported STS env-var creds, bridge them into a profile first:

```bash
aws configure set aws_access_key_id     "$AWS_ACCESS_KEY_ID"     --profile testing-migration
aws configure set aws_secret_access_key "$AWS_SECRET_ACCESS_KEY" --profile testing-migration
aws configure set aws_session_token     "$AWS_SESSION_TOKEN"     --profile testing-migration
aws configure set region us-east-2 --profile testing-migration
```

Dry-run, then real copy, then verify equality:

```bash
python3 scripts/migrate_dynamodb.py --src-table janus-testing --dst-table sc0red-services-testing \
  --profile testing-migration --region us-east-2 --dry-run

python3 scripts/migrate_dynamodb.py --src-table janus-testing --dst-table sc0red-services-testing \
  --profile testing-migration --region us-east-2

aws dynamodb scan --table-name janus-testing --select COUNT --region us-east-2 --query 'Count' --output text          # sum = 2070
aws dynamodb scan --table-name sc0red-services-testing --select COUNT --region us-east-2 --query 'Count' --output text  # sum = 2070
```

The script is idempotent (`put_item` overwrites by key) — safe to re-run on any hiccup.

---

## Step 2 — S3 documents

Testing's documents bucket was **empty** (0 objects) — QA analyses ran off URLs, not uploaded files — so nothing was copied. If a future env has documents:

```bash
aws s3 sync \
  s3://janus-testing-documentsbucket9ec9deb9-xa6jnangvxs5/ \
  s3://sc0redservices-testing-documentsbucket9ec9deb9-bcdq2e9fprk5/ \
  --region us-east-2
```

The PDF-exports bucket (`*-testing-pdf-exports`) was deliberately **not** copied — it's a regenerable cache; the async PDF flow re-renders on demand.

---

## Step 3 — Cognito: recreate users in the new pool

Two parts: (a) create each user in the new pool with all three custom attributes set **at create time**, then (b) backfill `cognito_sub` on the migrated DDB records (the new pool issues new `sub` UUIDs).

**Why custom attrs must be set at create time:** the backend auth middleware requires `custom:org_id` on every token (else 401 "Token missing required org_id claim"), and `custom:legacy_user_id` is declared **immutable** in the pool schema — it cannot be backfilled later. Preserving `legacy_user_id` is what keeps the recreated Cognito user lined up with its migrated `USER#` record in DynamoDB.

### 3a — Recreate users (copies attrs across from the old pool)

```bash
export AWS_REGION=us-east-2
OLD_POOL=us-east-2_dzJMNAORt
NEW_POOL=us-east-2_ISxHArxbP

for EMAIL in srilakshmi.krishnamoorthy@sc0red.com vedratna.velani@sc0red.com zack.walmer@sc0red.com; do
  ATTRS=$(aws cognito-idp admin-get-user --user-pool-id "$OLD_POOL" --username "$EMAIL" --region us-east-2 --query 'UserAttributes' --output json)
  ORG_ID=$(echo "$ATTRS" | jq -r '.[]|select(.Name=="custom:org_id").Value')
  ROLE=$(echo "$ATTRS"   | jq -r '.[]|select(.Name=="custom:role").Value')
  LEGACY=$(echo "$ATTRS" | jq -r '.[]|select(.Name=="custom:legacy_user_id").Value')
  aws cognito-idp admin-create-user --user-pool-id "$NEW_POOL" --username "$EMAIL" --region us-east-2 \
    --user-attributes \
      Name=email,Value="$EMAIL" Name=email_verified,Value=true \
      Name=custom:org_id,Value="$ORG_ID" Name=custom:role,Value="$ROLE" Name=custom:legacy_user_id,Value="$LEGACY" \
    --desired-delivery-mediums EMAIL
done
```

Each `admin-create-user` sends a temp-password email. Scope the loop to only the users who need to log in if you don't want all three emailed.

Verify every user got all three custom attrs (the original staging runbook's #1 bug was omitting them):

```bash
for EMAIL in srilakshmi.krishnamoorthy@sc0red.com vedratna.velani@sc0red.com zack.walmer@sc0red.com; do
  echo "=== $EMAIL ==="
  aws cognito-idp admin-get-user --user-pool-id "$NEW_POOL" --username "$EMAIL" --region us-east-2 \
    --query 'UserAttributes[?starts_with(Name,`custom:`)]' --output table
done
```

### 3b — Backfill `cognito_sub` on the DDB records

`scripts/repair_cognito_attrs.py` reads each DDB user record, fetches the new pool's `sub`, re-asserts the mutable attrs, and rewrites `cognito_sub` + `GSI5PK` only if they differ. Uses env-var creds directly (no `--profile`); reads region from `AWS_REGION`.

```bash
export AWS_REGION=us-east-2
python3 scripts/repair_cognito_attrs.py \
  --user-pool-id us-east-2_ISxHArxbP --table sc0red-services-testing \
  --email srilakshmi.krishnamoorthy@sc0red.com --email vedratna.velani@sc0red.com --email zack.walmer@sc0red.com \
  --dry-run
# Confirm in the dry-run: each record's `id` == the legacy_user_id, and old cognito_sub ≠ new sub.
# Then drop --dry-run. Expect "Repaired 3/3 users."
```

---

## Step 4 — Custom domain (cross-account)

The new Amplify app had no domain; `test.services.sc0red.ai` was brand-new (the old janus app was parked on `test.janus.sc0red.com`, left untouched). This mirrors dev's pattern exactly: standalone domain, empty prefix → branch.

### 4a — Create the association (TESTING account)

```bash
aws amplify create-domain-association \
  --app-id d2ea1ehyg2tsuh --region us-east-2 \
  --domain-name test.services.sc0red.ai \
  --sub-domain-settings '[{"prefix":"","branchName":"testing"}]'
```

### 4b — Get the DNS records (poll until `certRecord` is populated)

```bash
aws amplify get-domain-association --app-id d2ea1ehyg2tsuh --region us-east-2 \
  --domain-name test.services.sc0red.ai \
  --query 'domainAssociation.{status:domainStatus,certRecord:certificateVerificationDNSRecord,subs:subDomains[].dnsRecord}' --output json
```

Yields two CNAMEs (testing run's actual values shown for reference — yours will differ for the cert token):
- Cert validation: `_04dc491dbc26f883533cfc587652a0bf.test.services.sc0red.ai. CNAME _6f1cdd9d76d08eb6437c0d16a4755262.jkddzztszm.acm-validations.aws.`
- Domain: `test.services.sc0red.ai. CNAME d19q6ue9c24xpa.cloudfront.net.` (empty prefix → record name = the domain)

### 4c — Create both records in the sc0red.ai zone (PRODUCTION account)

```bash
cat > /tmp/test-domain-records.json << 'EOF'
{
  "Comment": "test.services.sc0red.ai -> Amplify testing app d2ea1ehyg2tsuh",
  "Changes": [
    { "Action": "UPSERT", "ResourceRecordSet": {
        "Name": "<CERT_VALIDATION_NAME>", "Type": "CNAME", "TTL": 300,
        "ResourceRecords": [{"Value": "<CERT_VALIDATION_VALUE>"}] } },
    { "Action": "UPSERT", "ResourceRecordSet": {
        "Name": "test.services.sc0red.ai.", "Type": "CNAME", "TTL": 300,
        "ResourceRecords": [{"Value": "d19q6ue9c24xpa.cloudfront.net."}] } }
  ]
}
EOF
aws route53 change-resource-record-sets --hosted-zone-id Z09084993URU8UB4L1L26 --change-batch file:///tmp/test-domain-records.json
```

### 4d — Verify live

```bash
# Amplify status (us-east-2): wait for AVAILABLE. NOTE: subDomains[].verified often
# stays `false` even when live — it's a known lagging flag. Trust dig/curl, not that flag.
aws amplify get-domain-association --app-id d2ea1ehyg2tsuh --region us-east-2 \
  --domain-name test.services.sc0red.ai --query 'domainAssociation.domainStatus' --output text

dig +short test.services.sc0red.ai                                              # → d19q6ue9c24xpa.cloudfront.net + IPs
curl -sS -o /dev/null -w "HTTP %{http_code}  TLS:%{ssl_verify_result}\n" https://test.services.sc0red.ai/   # → HTTP 200  TLS:0
```

---

## Config parity check — why no CDK redeploy was needed

Testing's API + Cognito config looked "wrong" at first glance, but is **identical to the working dev env**, so it's correct by definition:

| | Dev (works at dev.services.sc0red.ai) | Testing |
|---|---|---|
| `FRONTEND_DOMAIN` | `null` | `null` |
| `FRONTEND_BASE_URL` | `…development.…amplifyapp.com` | `…testing.…amplifyapp.com` |
| Cognito `CallbackURLs` | `["https://example.com"]` | `["https://example.com"]` |

- **Callbacks are irrelevant** — the app authenticates via the Cognito SDK direct flow (`USER_PASSWORD_AUTH`), not the Hosted-UI redirect. `CallbackURLs` are never consulted.
- **CORS isn't blocked** — frontend → backend calls go through same-origin Next.js routes, not cross-origin to the API Gateway.

**Known cosmetic deferral:** `FRONTEND_BASE_URL` = amplifyapp URL means password-reset / invitation emails link to the amplifyapp domain rather than `test.services.sc0red.ai`. Dev has the identical behaviour and it's been accepted. If clean custom-domain email links are ever wanted, update `FRONTEND_BASE_URL` on **both** dev and testing (CDK config change → branch + PR).

---

## Smoke test (the real "done" signal)

1. `https://test.services.sc0red.ai/login`
2. Log in as a migrated user with the temp password from the `admin-create-user` email → set new password at the `NEW_PASSWORD_REQUIRED` challenge.
3. Confirm the dashboard loads with the migrated analyses (2070 DDB items).
4. Open one analysis — confirm it renders.

Testing: **verified working 2026-06-03.**

---

## Rollback

The old `janus-testing` stack/table/pool/bucket are untouched throughout — they remain as a live backup. To roll back:
- Re-point nothing — `test.services.sc0red.ai` is a *new* domain; simply deleting the Amplify domain association + the two Route53 CNAMEs removes it with zero impact on the old env (which was on `test.janus.sc0red.com`).
- New items written to `sc0red-services-testing` after cutover can be reconciled later if needed.

---

## Production — already migrated (verified 2026-06-03)

**Production did NOT need a migration.** A pre-flight check (read-only) on 2026-06-03 found it was fully migrated during the original cutover (`Sc0redServices-production` stack last updated 2026-05-21) and has been **live, serving real customers**, ever since.

> ⚠️ **Critical lesson — always run the DynamoDB count check before any copy.** The testing playbook's step 1 (`migrate_dynamodb.py janus-X → sc0red-services-X`) is a blind `Scan` + `BatchWriteItem` overwrite. For production the *new* table already had **more** items than the *old* one (2034 vs 1970 — it's the live table with post-cutover writes). Running the copy would have **overwritten ~64 newer live customer records with stale backup data** — a data-loss incident. Pre-flight verification (Phase P0) is mandatory for any environment that might already be live.

### Verified production state (us-east-2, production account)

| Aspect | Finding | Action |
|---|---|---|
| CFN stack | `Sc0redServices-production` — `UPDATE_COMPLETE`, last updated 2026-05-21 | none |
| DynamoDB | `sc0red-services-production` is **live**: 2034 items vs old `janus-production` 1970 (new has +64 post-cutover writes) | **DO NOT COPY** — the new table is the source of truth |
| S3 documents | both `…documents…` buckets empty (0 objects) | none |
| Domain | `services.sc0red.ai` → new app `d3bhonqxtgzqm8`, `production` branch, `AVAILABLE`. Old app `d33liguumhvbzt` has **no** domain associations. | none |
| API config | `FRONTEND_DOMAIN=null`, `FRONTEND_BASE_URL=…production.…amplifyapp.com` — identical to the working dev pattern | none (no redeploy) |
| Cognito — customers | New pool `sc0red-services-users-production` (`us-east-2_jwlYvrWQ3`) holds **2 real external customers** — `william.bert@gmail.com`, `bjarne@bluejam.io` — both with complete custom attrs (`org_id`/`role`/`legacy_user_id`). Fully functional. | none |
| Cognito — internal | Old pool `janus-users-production` (`us-east-2_mRcaKKPFs`) holds 4 internal `@sc0red.com` users (chris.creel, srilakshmi, vedratna, zack). **None are in the new pool.** | see decision below |

### Open decision: internal-user production access

The 4 internal `@sc0red.com` users exist only in the OLD pool. Production is the customer environment; the internal team works in dev/testing. Whether the internal users need to *log into production* (e.g. for support/admin) is a product decision:

- **If not needed** → production is complete as-is.
- **If needed** → recreate only the named internal users in the new pool using Step 3's recipe (admin-create-user with custom attrs at create time + `repair_cognito_attrs.py` for the `cognito_sub` backfill), scoped to those users. Because the new pool is **live**, coordinate the temp-password emails (Phase 0 notification) rather than firing them ad hoc.

**Status as of 2026-06-03:** decision pending. Production functioning normally for its 2 customers regardless.

### If a future environment genuinely needs a fresh migration

For any environment where the new table is confirmed empty (like testing was), follow steps 1–4 above with that env's region/account/resource names. Always:
1. Run the Phase P0 read-only pre-flight first (counts, user lists, domain, config).
2. Snapshot the source table before any write: `aws dynamodb create-backup --table-name <src> --backup-name pre-rename-<env>-<ts> --region <region>`.
3. Treat any environment with existing users as carrying real data — notify before the temp-password blast.
