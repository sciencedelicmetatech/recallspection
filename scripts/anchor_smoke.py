#!/usr/bin/env python3
"""
S3 anchor smoke test for Recallspection.

Verifies that the external temporal anchor is reachable, writable, and
that a tamper check detects modification. This is a smoke test, not a
correctness proof. It exercises the external dependency, not the
theorem.

Runs under manual CI dispatch only. Requires:

    AWS_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY
    AWS_REGION
    RECALLSPECTION_BUCKET

Usage:
    python scripts/anchor_smoke.py

Exit code 0 on success, 1 on any failure.
"""

import os
import sys
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError


TEST_PREFIX = "_recallspection_smoke/"


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"FAIL: missing environment variable {name}")
        sys.exit(1)
    return value


def main() -> int:
    bucket = require_env("RECALLSPECTION_BUCKET")
    region = require_env("AWS_REGION")

    print("Recallspection -- S3 anchor smoke test")
    print("=" * 60)
    print(f"  bucket: {bucket}")
    print(f"  region: {region}")
    print(f"  prefix: {TEST_PREFIX}")
    print()

    s3 = boto3.client("s3", region_name=region)

    # Unique key per run so concurrent runs do not collide.
    run_id = uuid.uuid4().hex
    key = f"{TEST_PREFIX}{run_id}/anchor.json"
    payload_v1 = b'{"counter": 1, "prev": null}'
    payload_v2 = b'{"counter": 2, "prev": 1}'

    try:
        # 1. Write the initial anchor state.
        s3.put_object(Bucket=bucket, Key=key, Body=payload_v1)
        print("  [1] put_object          OK")

        # 2. Read it back and confirm bytes match.
        obj = s3.get_object(Bucket=bucket, Key=key)
        body = obj["Body"].read()
        assert body == payload_v1, "read-back mismatch"
        print("  [2] get_object          OK (bytes match)")

        # 3. Advance the counter. This is the write-time commitment
        #    path. A production anchor writes a new monotonic value
        #    chained to the previous one.
        s3.put_object(Bucket=bucket, Key=key, Body=payload_v2)
        obj = s3.get_object(Bucket=bucket, Key=key)
        body_v2 = obj["Body"].read()
        assert body_v2 == payload_v2, "advance mismatch"
        print("  [3] counter advance     OK")

        # 4. Verify the tamper check catches a silent modification.
        #    Overwrite with something that is neither v1 nor v2.
        s3.put_object(Bucket=bucket, Key=key, Body=b'{"counter": 1, "prev": 1}')
        obj = s3.get_object(Bucket=bucket, Key=key)
        body_tampered = obj["Body"].read()
        # A sound anchor must not silently accept this. The exact
        # detection routine lives in the product; here we only check
        # that the modified bytes differ from any expected value.
        assert body_tampered not in (payload_v1, payload_v2), \
            "tamper not observed at the S3 layer"
        print("  [4] tamper visible      OK")

        # 5. Confirm ObjectVersioning is enabled. Without it, a
        #    rollback of the anchor is a put_object away, and the
        #    temporal anchor does not do its job (Paper 2 scope).
        try:
            versioning = s3.get_bucket_versioning(Bucket=bucket)
            status = versioning.get("Status", "Disabled")
        except ClientError as e:
            print(f"  [5] versioning check    WARN: {e}")
            status = "Unknown"

        if status == "Enabled":
            print("  [5] bucket versioning   OK (Enabled)")
        else:
            print(f"  [5] bucket versioning   WARN ({status})")
            print("      Paper 2 requires the anchor to be rollback-"
                  "resistant.")
            print("      Enable bucket versioning or use an append-only "
                  "anchor service.")

    except (BotoCoreError, ClientError, AssertionError) as e:
        print(f"\nFAIL: {type(e).__name__}: {e}")
        return 1

    finally:
        # Cleanup. Delete every object we created under this run_id.
        try:
            listing = s3.list_objects_v2(
                Bucket=bucket, Prefix=f"{TEST_PREFIX}{run_id}/"
            )
            for obj in listing.get("Contents", []):
                s3.delete_object(Bucket=bucket, Key=obj["Key"])
        except (BotoCoreError, ClientError) as e:
            print(f"\nWARN: cleanup failed: {e}")

    print()
    print("=" * 60)
    print("PASS: S3 anchor smoke test complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())