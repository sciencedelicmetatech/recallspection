"""
recallspection.anchor - S3 Object Lock anchor for the transparency log.

The transparency log proves records have not been modified. It does not prove
that a whole authentic file has not been replaced with an earlier authentic
file. That requires an external witness.

This module publishes the Merkle root of the transparency log to S3 with
Object Lock in COMPLIANCE mode. Even the bucket owner cannot delete or modify
the anchor before the retain-until date.

Zero hard dependency on boto3 - it is imported lazily inside the client
property. Install with: pip install recallspection[anchor]
"""

from __future__ import annotations

import hashlib
import json
import os
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _sha3(data: bytes) -> bytes:
    return hashlib.sha3_256(data).digest()


def compute_merkle_root(log_path):
    """
    Compute the Merkle root of the transparency log.

    Each non-empty line is a leaf. Leaves are SHA3-256 hashed, combined
    pairwise, with the last node duplicated on odd levels.

    Returns the root as a hex string prefixed with 0x.
    """
    path = Path(log_path)
    if not path.exists():
        raise FileNotFoundError("Transparency log not found: " + str(path))

    leaves = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                leaves.append(line.encode("utf-8"))

    if not leaves:
        return "0x" + _sha3(b"").hex()

    level = [_sha3(leaf) for leaf in leaves]
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        level = [_sha3(level[i] + level[i + 1]) for i in range(0, len(level), 2)]
    return "0x" + level[0].hex()


@dataclass
class AnchorRecord:
    root: str
    anchored_at: str
    retain_until: str
    s3_bucket: str
    s3_key: str
    s3_region: str
    log_entry_count: int
    max_version: int
    mode: str = "COMPLIANCE"

    def to_dict(self):
        return asdict(self)

    def to_json(self):
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


class RemoteAnchorS3:
    """
    S3 Object Lock anchor with COMPLIANCE mode.

    The bucket MUST be created with Object Lock enabled. It cannot be added
    later. Retention is set per-object at PUT time.
    """

    def __init__(
        self,
        bucket,
        region="us-east-1",
        retention_days=30,
        prefix="anchors/",
        client=None,
    ):
        self.bucket = bucket
        self.region = region
        self.retention_days = retention_days
        self.prefix = (prefix.rstrip("/") + "/") if prefix else ""
        self._client = client

    @property
    def client(self):
        if self._client is not None:
            return self._client
        try:
            import boto3
        except ImportError as e:
            raise ImportError(
                "boto3 is required for S3 anchoring. "
                "Install with: pip install recallspection[anchor]"
            ) from e
        self._client = boto3.client("s3", region_name=self.region)
        return self._client

    def anchor(self, log_path, max_version=0):
        root = compute_merkle_root(log_path)
        return self.anchor_root(root, max_version=max_version, log_path=log_path)

    def anchor_root(self, root, max_version=0, log_path=None):
        now = datetime.now(timezone.utc)
        retain_until = now + timedelta(days=self.retention_days)
        key = self.prefix + root + ".json"

        count = 0
        if log_path is not None and Path(log_path).exists():
            with Path(log_path).open("r", encoding="utf-8") as f:
                count = sum(1 for line in f if line.strip())

        body = AnchorRecord(
            root=root,
            anchored_at=now.isoformat(),
            retain_until=retain_until.isoformat(),
            s3_bucket=self.bucket,
            s3_key=key,
            s3_region=self.region,
            log_entry_count=count,
            max_version=max_version,
        )

        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body.to_json().encode("utf-8"),
            ContentType="application/json",
            ObjectLockMode="COMPLIANCE",
            ObjectLockRetainUntilDate=retain_until,
        )
        return body

    def get_retention(self, root):
        key = self.prefix + root + ".json"
        resp = self.client.get_object_retention(Bucket=self.bucket, Key=key)
        retention = resp.get("Retention", {}) or {}
        retain_until = retention.get("RetainUntilDate")
        if hasattr(retain_until, "isoformat"):
            retain_until = retain_until.isoformat()
        return {
            "mode": retention.get("Mode"),
            "retain_until": retain_until,
        }

    def get_latest(self):
        resp = self.client.list_objects_v2(Bucket=self.bucket, Prefix=self.prefix)
        contents = resp.get("Contents", []) or []
        if not contents:
            return None
        latest = max(contents, key=lambda x: x["LastModified"])
        obj = self.client.get_object(Bucket=self.bucket, Key=latest["Key"])
        data = json.loads(obj["Body"].read().decode("utf-8"))
        return AnchorRecord(**data)

    def verify(self, root):
        key = self.prefix + root + ".json"
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            retention = self.get_retention(root)
            return {
                "local_valid": True,
                "s3_locked": retention["mode"] == "COMPLIANCE",
                "compliance": retention["mode"],
                "retain_until": retention["retain_until"],
            }
        except Exception as e:
            return {
                "local_valid": False,
                "s3_locked": False,
                "compliance": None,
                "retain_until": None,
                "error": str(e),
            }


def anchor_root(
    log_path,
    bucket=None,
    region=None,
    retention_days=None,
    max_version=0,
    client=None,
):
    bucket = bucket or os.environ.get("RECALLSPECTION_S3_BUCKET")
    region = region or os.environ.get("RECALLSPECTION_S3_REGION", "us-east-1")
    if retention_days is None:
        retention_days = int(os.environ.get("RECALLSPECTION_S3_RETENTION_DAYS", "30"))

    if not bucket:
        raise ValueError(
            "S3 bucket not configured. "
            "Set RECALLSPECTION_S3_BUCKET or pass bucket=..."
        )

    anchor = RemoteAnchorS3(
        bucket=bucket,
        region=region,
        retention_days=retention_days,
        client=client,
    )
    return anchor.anchor(log_path, max_version=max_version)


def audit_export(log_path, output_path, from_ts=None, to_ts=None, anchor=None):
    log_path = Path(log_path)
    output_path = Path(output_path)

    entries = []
    if log_path.exists():
        with log_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if from_ts:
        from_dt = datetime.fromisoformat(from_ts)
        entries = [e for e in entries if e.get("timestamp", 0) >= from_dt.timestamp()]
    if to_ts:
        to_dt = datetime.fromisoformat(to_ts)
        entries = [e for e in entries if e.get("timestamp", 0) <= to_dt.timestamp()]

    if log_path.exists():
        root = compute_merkle_root(log_path)
    else:
        root = "0x" + _sha3(b"").hex()

    manifest = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "log_path": str(log_path),
        "entry_count": len(entries),
        "merkle_root": root,
        "from": from_ts,
        "to": to_ts,
        "regulation": "EU AI Act Article 12",
        "retention_years": 7,
    }

    proof = {
        "merkle_root": root,
        "root_source": str(log_path),
        "algorithm": "SHA3-256",
        "tree": "binary, duplicate-last-on-odd",
    }

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
        zf.writestr("merkle_proof.json", json.dumps(proof, indent=2, sort_keys=True))
        zf.writestr(
            "log_slice.ndjson",
            "\n".join(json.dumps(e, sort_keys=True) for e in entries),
        )
        if anchor is not None:
            try:
                latest = anchor.get_latest()
                if latest:
                    zf.writestr(
                        "anchor.json",
                        json.dumps(latest.to_dict(), indent=2, sort_keys=True),
                    )
            except Exception as e:
                zf.writestr("anchor_error.txt", "Could not fetch anchor: " + str(e) + "\n")

    return output_path


def _cli():
    import argparse

    parser = argparse.ArgumentParser(prog="recallspection.anchor")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_root = sub.add_parser("root", help="Compute the Merkle root of a log")
    p_root.add_argument("log_path")

    p_anchor = sub.add_parser("anchor", help="Anchor the log root to S3")
    p_anchor.add_argument("log_path")
    p_anchor.add_argument("--bucket", default=None)
    p_anchor.add_argument("--region", default=None)
    p_anchor.add_argument("--retention-days", type=int, default=None)

    p_verify = sub.add_parser("verify", help="Verify a root against S3")
    p_verify.add_argument("root")
    p_verify.add_argument("--bucket", default=None)

    p_export = sub.add_parser("export", help="Export EU AI Act Art. 12 audit zip")
    p_export.add_argument("log_path")
    p_export.add_argument("output_path")
    p_export.add_argument("--from", dest="from_ts", default=None)
    p_export.add_argument("--to", dest="to_ts", default=None)

    args = parser.parse_args()

    if args.cmd == "root":
        print(compute_merkle_root(args.log_path))
        return 0

    if args.cmd == "anchor":
        rec = anchor_root(
            args.log_path,
            bucket=args.bucket,
            region=args.region,
            retention_days=args.retention_days,
        )
        print(json.dumps(rec.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.cmd == "verify":
        bucket = args.bucket or os.environ.get("RECALLSPECTION_S3_BUCKET")
        if not bucket:
            print("RECALLSPECTION_S3_BUCKET not set")
            return 2
        a = RemoteAnchorS3(bucket=bucket)
        print(json.dumps(a.verify(args.root), indent=2, sort_keys=True))
        return 0

    if args.cmd == "export":
        path = audit_export(args.log_path, args.output_path, args.from_ts, args.to_ts)
        print(str(path))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())