"""Find + optionally delete orphan scans (scans with zero linked companies).

Why this exists:
    Before the bulk-delete-cascade-race fix landed, the frontend's bulk
    delete fired N parallel `DELETE /api/analysis/{id}` requests. Each
    request ran the cascade-to-scan check independently; when peer
    requests' unlinks hadn't yet committed at read time, multiple
    requests could each conclude "the scan still has companies" and
    none would delete it. Result: scan records with `total_companies > 0`
    but zero remaining `COMPANY#*` link items — orphans that surface in
    Recent Scans on the dashboard and lead to empty portfolio pages
    when clicked.

    The race itself is fixed by the bulk-delete endpoint that ships in
    the same PR. This script cleans up the orphans created by the old
    code path. Safe to re-run; idempotent.

Modes:
    Default: dry-run. Lists candidate orphan scans without deleting.
    --commit: actually deletes the orphans (and any leftover link
              records, defensively).

Filters:
    --org-id ORG  : only inspect scans for the given org. Without this,
                    inspects every scan in the table.

Output:
    For each orphan scan the script prints one line:
        <scan_id> <created_at> <type> <source_url> <link_count>=0

    On --commit, also prints:
        DELETED <scan_id>

Required environment:
    DYNAMODB_TABLE   — full table name (e.g. janus-development)
    AWS_REGION       — defaults to us-east-1
    AWS_ENDPOINT_URL — set to LocalStack URL for local testing

Run from the backend dir:
    python scripts/cleanup_orphan_scans.py                  # dry-run, all orgs
    python scripts/cleanup_orphan_scans.py --org-id org-123 # dry-run, one org
    python scripts/cleanup_orphan_scans.py --commit         # delete

The script is dry-run by default specifically to avoid the "I copy-
pasted from a runbook and dropped production scans" failure mode.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any

# Mirror the sqs_worker.py path-insert so `from src.…` resolves when run
# without `pip install .` in the local venv.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.repositories.dynamodb.provider import DynamoDBStorageProvider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def find_orphan_scans(
    storage: DynamoDBStorageProvider,
    org_id: str,
) -> list[dict[str, Any]]:
    """Return every scan whose linked companies no longer exist.

    Two orphan flavours are detected:

    1. **No-links orphans** — scan record exists but `get_scan_companies`
       returns []. These are the canonical bulk-delete-cascade-race
       leftovers (links unlinked, scan record never garbage-collected).

    2. **Stale-links orphans** — `get_scan_companies` returns N link
       items, but every linked `company_id` resolves to a missing
       company record. This happens when a code path deleted the
       company entity but never called `unlink_company` (legacy data
       corruption, or pre-fix delete paths that skipped the unlink).
       Functionally equivalent to a no-links orphan — the dashboard
       still displays the scan and View Portfolio loads empty — but
       the prior cleanup logic missed them.

    Requiring an org filter is intentional — without one the function
    would have to fall back to a table scan (no global index for
    "every scan everywhere"), and runaway production cleanups are too
    easy to launch by accident. The CLI guards `--org-id` as required.
    """
    scan_repo = storage.create_scan_repository()
    company_repo = storage.create_company_repository()
    scans = scan_repo.find_recent_by_org(org_id, limit=None)
    logger.info("scanning %d scans for org_id=%s", len(scans), org_id)

    orphans: list[dict[str, Any]] = []
    for scan in scans:
        scan_id = scan.get("id", "")
        if not scan_id:
            logger.warning("scan record without id, skipping: %r", scan)
            continue

        links = scan_repo.get_scan_companies(scan_id)
        if not links:
            scan["_orphan_kind"] = "no_links"
            orphans.append(scan)
            continue

        # Stale-links case: links exist, but do the companies they point
        # at? Use BatchGetItem (CLAUDE.md DynamoDB pattern) to resolve in
        # one call. If every linked company is gone, treat as orphan.
        link_company_ids = [link["company_id"] for link in links if link.get("company_id")]
        if not link_company_ids:
            # Defensive: links exist but none have a company_id field —
            # shouldn't happen with current writes, but if it does the
            # links are useless. Treat as no-links orphan.
            scan["_orphan_kind"] = "no_links"
            orphans.append(scan)
            continue

        existing_companies = company_repo.get_by_ids(link_company_ids)
        existing_ids = {company["id"] for company in existing_companies if company.get("id")}
        missing = [cid for cid in link_company_ids if cid not in existing_ids]
        if len(missing) == len(link_company_ids):
            # All linked companies are gone — orphan.
            scan["_orphan_kind"] = "stale_links"
            scan["_stale_link_count"] = len(missing)
            orphans.append(scan)

    return orphans


def report_orphan(scan: dict[str, Any]) -> None:
    """Print a one-line summary of an orphan scan."""
    kind = scan.get("_orphan_kind", "no_links")
    suffix = ""
    if kind == "stale_links":
        suffix = f"  (stale_links={scan.get('_stale_link_count', 0)})"
    print(
        f"{scan.get('id', '?'):40s}  "
        f"{scan.get('created_at', '?'):28s}  "
        f"{scan.get('type', '?'):12s}  "
        f"{kind:12s}  "
        f"{scan.get('source_url', '?')}{suffix}"
    )


def delete_orphan(storage: DynamoDBStorageProvider, scan: dict[str, Any]) -> None:
    """Delete the scan metadata + (defensively) any stale link records."""
    scan_repo = storage.create_scan_repository()
    scan_id = scan["id"]

    # Defensive sweep — if any orphan link items survived the bug
    # (shouldn't happen, but cheap insurance), drop them too.
    scan_repo.delete_all_company_links(scan_id)
    scan_repo.delete(scan_id)
    print(f"DELETED {scan_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--org-id",
        required=True,
        help="Org id to clean up. Required to prevent unbounded scans.",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Actually delete orphan scans. Default: dry-run.",
    )
    args = parser.parse_args()

    storage = DynamoDBStorageProvider()
    orphans = find_orphan_scans(storage, args.org_id)

    if not orphans:
        print(f"No orphan scans found for org {args.org_id}.")
        return 0

    print(f"\nFound {len(orphans)} orphan scan(s) for org {args.org_id}:\n")
    print(f"  {'scan_id':40s}  {'created_at':28s}  {'type':12s}  {'kind':12s}  source_url")
    print(f"  {'-' * 40}  {'-' * 28}  {'-' * 12}  {'-' * 12}  ----------")
    for scan in orphans:
        print("  ", end="")
        report_orphan(scan)

    if not args.commit:
        print("\nDry-run mode. Re-run with --commit to delete these scans.")
        return 0

    print(f"\nDeleting {len(orphans)} orphan scan(s)...")
    for scan in orphans:
        delete_orphan(storage, scan)
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
