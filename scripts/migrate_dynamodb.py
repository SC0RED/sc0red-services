#!/usr/bin/env python3
"""Copy every item from a source DynamoDB table to a destination DynamoDB table.

Used for the janus-{env} -> sc0red-services-{env} migration. The destination
table must already exist with a compatible schema (this script does not create
or alter tables).

Usage:
    python3 scripts/migrate_dynamodb.py \\
        --src-table janus-staging \\
        --dst-table sc0red-services-staging \\
        --profile sc0red-dev \\
        [--dry-run] [--limit N]
"""
from __future__ import annotations

import argparse
import sys
import time

import boto3


def migrate(
    src_table: str,
    dst_table: str,
    profile: str,
    region: str,
    dry_run: bool,
    limit: int | None,
) -> int:
    session = boto3.Session(profile_name=profile, region_name=region)
    dynamodb = session.resource("dynamodb")
    src = dynamodb.Table(src_table)
    dst = dynamodb.Table(dst_table)

    print(f"source:      {src_table} ({src.item_count} items reported by DescribeTable)")
    print(f"destination: {dst_table} ({dst.item_count} items reported by DescribeTable)")
    if dry_run:
        print("DRY RUN — no writes will be performed.")
    print()

    total_scanned = 0
    total_written = 0
    start = time.monotonic()
    last_evaluated_key: dict | None = None

    while True:
        scan_kwargs: dict = {}
        if last_evaluated_key:
            scan_kwargs["ExclusiveStartKey"] = last_evaluated_key
        response = src.scan(**scan_kwargs)
        items = response.get("Items", [])
        total_scanned += len(items)

        if not dry_run and items:
            with dst.batch_writer() as batch:
                for item in items:
                    batch.put_item(Item=item)
            total_written += len(items)

        last_evaluated_key = response.get("LastEvaluatedKey")
        elapsed = time.monotonic() - start
        print(f"  scanned={total_scanned}  written={total_written}  elapsed={elapsed:.1f}s")

        if last_evaluated_key is None:
            break
        if limit is not None and total_scanned >= limit:
            print(f"  stopped at --limit {limit}")
            break

    print()
    print(f"DONE — scanned {total_scanned}, wrote {total_written} in {time.monotonic() - start:.1f}s")
    if not dry_run:
        dst.reload()
        print(f"destination ItemCount now (cached, may be stale): {dst.item_count}")
        print("Run a Select=COUNT scan on both tables to verify exact equality.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--src-table", required=True)
    parser.add_argument("--dst-table", required=True)
    parser.add_argument("--profile", required=True, help="AWS profile name")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--dry-run", action="store_true", help="Scan only, don't write")
    parser.add_argument("--limit", type=int, default=None, help="Stop after N items scanned")
    args = parser.parse_args()

    return migrate(
        src_table=args.src_table,
        dst_table=args.dst_table,
        profile=args.profile,
        region=args.region,
        dry_run=args.dry_run,
        limit=args.limit,
    )


if __name__ == "__main__":
    sys.exit(main())
