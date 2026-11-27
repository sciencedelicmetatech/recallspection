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

# Mandate + Notary surface. Previously missing, so mandate had nowhere to live.
# Keep anchor exports untouched. Add only the new surface.
from recallspection.mandate import Mandate
from recallspection.notary import MachineNotary
from recallspection.client import NotaryClient
from recallspection.store import ExactStore, NotaryStore

__version__ = "18.0.0"

__all__ = [
    # existing anchor surface, unchanged
    "AnchorRecord",
    "RemoteAnchorS3",
    "anchor_root",
    "audit_export",
    "compute_merkle_root",
    # new mandate / notary surface
    "Mandate",
    "MachineNotary",
    "NotaryClient",
    "ExactStore",
    "NotaryStore",
    "__version__",
]
