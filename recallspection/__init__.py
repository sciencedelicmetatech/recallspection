"""
recallspection — tamper-evident exact memory for autonomous AI agents.
"""

from recallspection.anchor import (
    AnchorRecord,
    RemoteAnchorS3,
    anchor_root,
    audit_export,
    compute_merkle_root,
)

__version__ = "18.0.0"

__all__ = [
    "AnchorRecord",
    "RemoteAnchorS3",
    "anchor_root",
    "audit_export",
    "compute_merkle_root",
    "__version__",
]